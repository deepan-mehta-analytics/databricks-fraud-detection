# dashboards/

The two AI/BI dashboards of Phase 6a, deployed by the bundle
(`resources/fraud_dashboards.yml`) and refreshed by the `refresh_operations`
and `refresh_platform` tasks of `fraud-ingest`.

- `fraud_operations.lvdash.json` — **Fraud operations**, for all three groups:
  what is waiting for review, how the reviews turned out, whether the model is
  still good, and a word list.
- `platform_health.lvdash.json` — **Platform health**, for `fraud_engineers`
  only: job and pipeline minutes, data freshness, rejected rows, and a word list.

Both files are **generated**. Edit `src/fraud_monitoring/dashboards.py`, then
run `python scripts/build_dashboards.py`; a test fails if the files and the
code disagree. Both dashboards use viewer credentials (`embed_credentials:
false`), so every viewer sees data under their own grants, row filter and
column masks. To try a layout change in the workspace, edit a *clone* — an
edit to the deployed copy makes the next deploy fail.
