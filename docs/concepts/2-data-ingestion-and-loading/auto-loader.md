# Auto Loader

**In plain words:** Auto Loader is a Databricks Structured Streaming source that watches a folder and incrementally loads only the files it hasn't seen yet, inferring or checking their schema as it goes.

**Everyday analogy:** It's a mailroom clerk who only opens envelopes that just arrived, checks each letter matches the expected form, and files anything odd in a "needs review" tray instead of throwing it away.

**Why real teams use it:** It gives incremental, exactly-once file ingestion with built-in schema drift handling, so pipelines don't silently break or lose data when an upstream source changes shape ([docs](https://docs.databricks.com/aws/en/ingestion/cloud-object-storage/auto-loader/), checked 2026-09-27).

**How this repo uses it:** `cloudFiles` reads JSON Lines with pinned `cloudFiles.schemaHints` on key fields and `addNewColumns` schema evolution, writing into the Bronze Delta table ([docs](https://docs.databricks.com/aws/en/ingestion/cloud-object-storage/auto-loader/schema.html), checked 2026-09-27). See [ingest.py](../../../src/fraud_ingest/ingest.py) and [contract.py](../../../src/fraud_ingest/contract.py).

**What was verified:** 2026-09-24, workspace runs V1–V6 (`a6b108c`): a genuinely invalid JSON line still lands as one all-null row, with `_rescued_data` also null (`docs/GAPS.md` §3, V5).

**Key terms:** cloudFiles, schema hints, schema evolution, `_rescued_data`.

**Go deeper:** private study notes (drills, diagrams, traps) live outside the public repo.
