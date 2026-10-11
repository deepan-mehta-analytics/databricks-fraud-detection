# ADR 0009: Batch Scoring with MLflow and Unity Catalog

## Status
Proposed (2026-10-11). Builds on [ADR 0008](0008-silver-on-a-declarative-pipeline.md):
the model reads Silver's clean payments and their past-only features.

## Context
Silver holds clean payments plus 7 features that use earlier hours only. Phase
4 needs a fraud model trained on them, and every new payment needs a risk score
inside the existing ingest job. The constraints:

- Free Edition is serverless-only. Online tables are unsupported, so there is
  no millisecond feature lookup. On serverless, Spark ML runs through Spark
  Connect, with a 100 MB model cap and a 1 GB custom-code memory limit.
- Fraud is rare: about 0.1% of payments, and only TRANSFER and CASH_OUT
  payments are ever fraud.
- Real fraud labels arrive late. Chargebacks take weeks, so a model can't
  learn from the most recent days.
- A real team can only review a fixed number of alerts. A score cut-off (for
  example "> 0.85") doesn't fix the workload, but a budget does.

Measured on `data/paysim.csv` (2026-10-08): the scoring period, hours 337–408,
holds 1,202,642 payments and 822 fraud (about 16,700 payments and 11 fraud per
hour).

## Decision
1. **Batch scoring as a job task, not an endpoint.** A `score` task runs after
   `silver` in `fraud-ingest`. It scores Silver payments from hour 337 onward
   that aren't in the log yet (left anti-join on `transaction_id`), so a rerun
   scores nothing twice.
2. **A review budget of 50 alerts per simulated hour.** Evaluation reports
   precision and recall for the top 50 per hour, and PR-AUC over the whole
   period, against three baselines: a logistic regression, "largest amount
   first", and PaySim's legacy `flagged_by_old_rules`.
3. **Champion/challenger in the Unity Catalog model registry.** `fraud-train`
   (on demand, no schedule) registers a new version of
   `workspace.fraud.fraud_model` with the `@challenger` alias. A person moves
   `@champion` with `06_promote_model`. Scoring always loads `@champion`, so a
   promotion needs no redeploy.
4. **A label-delay setting D.** Training ignores the last D days before the
   cut. The model was trained with D = 3 and D = 0, and both were evaluated on
   the same scoring period, so the delay's cost is measured, not assumed.
5. **Engine: scikit-learn on a sample.** A `HistGradientBoostingClassifier`
   (class-weighted, handles missing values) competes with a standardised
   logistic regression on a time-based comparison window, and the higher
   PR-AUC wins. The fit set keeps all fraud plus a seeded 10% of non-fraud.
   Scores are therefore rankings, not calibrated probabilities. The column is
   named `risk_score` for that reason.
6. **One feature builder** (`build_feature_frame`) for training, scoring and
   evaluation. Scoring runs in pandas chunks of 6 steps through that function,
   not through `spark_udf` (plan ruling P1). The same tested code feeds both
   sides, so training and scoring can't drift apart.
7. **A decision log.** `transaction_risk_scores` stores each score with the
   model name, version, alias, time, and the feature values exactly as the
   model saw them (ruling P4). Later corrections to Silver never rewrite a
   stored decision.
8. **The label never enters scoring.** A CI text guard forbids `fraud_label` in
   the scoring notebook and module. The log's schema was checked in the
   workspace (M4c: 0 answer columns).
9. **The library version lives in the notebooks.** The train, score and
   evaluate notebooks start with `%pip install scikit-learn==1.7.2`. A guard
   stops any run whose scikit-learn major.minor differs from the training
   run's, or whose MLflow is older than 3. A job-level environment pin was
   tried first and silently dropped by the deploy for notebook tasks.

Smaller rulings: the logistic pipeline's imputer keeps all-missing columns
(`keep_empty_features=True`, P3), so the column list can't change between fit
and score. Hours 1–24 stay in training even though their features show little
history (warm-up). This is a decision, not a measurement.

## Consequences
**Positive:**
- The ingest job keeps working before any model exists. With no `@champion`,
  scoring prints "No champion model yet: nothing scored" and succeeds (M3b).
- Every score can be traced to a model version and its exact inputs (M7c).
- The trees beat every baseline at the same budget (M6, below).

**Negative:**
- No real-time scoring. Banks score at payment time from an online feature
  store, which Free Edition can't host.
- Promotion is a manual notebook, not a CI gate. There is no shadow scoring of
  the challenger and no automated, drift-triggered retraining (Phase 6).
- The fit set is sampled. Scores rank payments but are not probabilities.
- MLflow is not pinned. Job tasks got MLflow 3.8.1, while interactive
  notebooks and training got 3.12.0. Loading the 3.12-logged model under 3.8.1
  worked, and the guard only requires MLflow 3 or later.
- The model leans on amount, hour of day and payment type. None of Silver's
  receiver-history features is in the top 5 importances. Hour of day is a
  PaySim artefact: clock hours 0–7 hold 31% of training fraud but 1.2% of
  normal payments (measured from the CSV).
- 18 of the 72 test hours have fewer than 50 payments, all of them fraud, so
  every approach catches those 216 for free. In the 54 full hours the
  champion catches 189 of 606 fraud, against 136 for "largest amount first".

**Checked in real runs (2026-10-08 to 2026-10-11, see `docs/GAPS.md` §5):**
- M1: in a serverless notebook, register → alias → load by alias →
  `createDataFrame` → append all worked (scikit-learn 1.7.2, MLflow 3.12.0).
- M2 (D = 3): fit window 1–216 had 2,797,736 rows; the sampled fit set had
  282,290 rows, 2,437 of them fraud. Comparison window 217–264: 810,804 rows,
  544 fraud. Trees: PR-AUC 0.305, recall@50/hour 0.439. Logistic: 0.098 and
  0.404. The trees were registered as version 1. Run time: 2 min 9 s.
- M3 (D = 0): fit window 1–288 had 3,958,316 rows; the sampled fit set had
  398,765 rows, 3,279 of them fraud. Comparison window 289–336: 826,459 rows,
  488 fraud. Trees: PR-AUC 0.351. The trees were registered as version 2.
- M4: version 1 promoted to `@champion`. The first scoring run scored
  1,205,673 payments (hours 337–417), each ID once, every row from version 1,
  with no answer columns in the log. The stored features equal Silver's.
  Run time: 5 min 3 s for the whole job.
- M5: a rerun scored 0 new payments (8 min 13 s for the whole job).
- M6, on the scoring period (hours 337–408, 822 fraud, 50 alerts per hour):

  | Model | Fraud caught | Precision | Recall | PR-AUC |
  |---|---|---|---|---|
  | Trees, D = 3 (version 1) | 405 | 0.139 | 0.493 | 0.346 |
  | Trees, D = 0 (version 2) | 406 | 0.139 | 0.494 | 0.379 |
  | Logistic, D = 3 | 367 | 0.126 | 0.446 | 0.028 |
  | Largest amount first | 352 | 0.121 | 0.428 | 0.024 |
  | PaySim's old rules (1 flag) | 1 | 1.000 | 0.001 | — |

  The label delay cost 1 caught fraud at the budget, and 0.033 PR-AUC.
- M7: version 2 was promoted, and one drift hour (418) was released. Its 6
  payments were scored by version 2, and version 1's 1,205,673 rows were left
  unchanged.
- M8: `@champion` was moved back to version 1. It ties version 2 at the
  budget, and version 2's PR-AUC edge comes from labels a real team wouldn't
  have yet.

## Alternatives rejected
- **A serving endpoint**: millisecond scoring needs an online feature store,
  and online tables are unsupported on Free Edition. The batch task scores
  each load within the job's run.
- **Spark ML end to end**: Spark Connect's 100 MB model cap and 1 GB memory
  limit on serverless, more quota used, and no gain at 6M rows.
- **AutoML**: Free Edition support is undocumented, and it hides the modelling
  decisions this repo exists to show.
- **Feature Engineering client**: Silver's features are already point-in-time
  per payment, so a join on `transaction_id` is exactly correct. Its
  production benefit, online lookups, isn't available here (G-16).
- **`spark_udf` for prediction**: it would need a second copy of the feature
  logic outside the tested builder (P1).
- **A scheduled retrain (for example nightly at 2 AM)**: no new labels arrive
  in a replay, so a schedule would spend quota for nothing. Retraining is on
  demand.
- **Retraining inside the scoring job**: it couples a slow, quota-heavy step
  to every load, and it skips the human promotion step.
- **A full label feed into scoring**: the score must not depend on the answer.
  Labels are joined only in training and evaluation.
- **A fixed probability cut-off**: sampled scores aren't calibrated, and a
  cut-off doesn't match a review team's capacity.
