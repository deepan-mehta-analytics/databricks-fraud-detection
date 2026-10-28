# dashboards/

The two AI/BI dashboards of Phase 6a, deployed by the bundle
(`resources/fraud_dashboards.yml`) and refreshed by the `refresh_operations`
and `refresh_platform` tasks of `fraud-ingest`.

- `fraud_operations.lvdash.json` — **Fraud operations**, for all three groups:
  what is waiting for review, how the reviews turned out, whether the model is
  still good, and a word list.
- `platform_health.lvdash.json` — **Platform health**, for `fraud_engineers`
  only: job and pipeline minutes, data freshness, rejected rows, a Run
  detail page, and a word list.

Both share one theme and meaning colours (green good, red bad, grey neutral,
always beside a ✓ or ✕), and both support hour sliders, click-to-filter and
drill-through: a run opens Run detail, and a reviews hour opens the model
page through its one-hour picker (ADR 0012).

Both files are **generated**. Edit `src/fraud_monitoring/dashboards.py`, then
run `python scripts/build_dashboards.py`; a test fails if the files and the
code disagree. Both dashboards use viewer credentials (`embed_credentials:
false`), so every viewer sees data under their own data permissions, row
filter and column masks. To try a change in the workspace, import a separate
copy of the file (Dashboards → Import), change it there, export it, and copy
the exported settings into the builder; then delete the copy. Never edit the
deployed dashboard: the next deploy overwrites it.
