# Delta Lake, Bronze, and Unity Catalog

**In plain words:** A lakehouse stores data as plain files but manages it like a database — Delta Lake adds reliable, ACID-safe tables on top of those files, and Unity Catalog governs who can see which catalog, schema, table, or volume.

**Everyday analogy:** Delta Lake is a shared spreadsheet that never half-saves, even if two people edit it at once; Unity Catalog is the building's key-card system, deciding which floors and rooms each visitor can enter.

**Why real teams use it:** One platform serves both cheap, flexible raw storage and trusted, access-controlled tables, instead of running a separate lake and warehouse ([docs](https://docs.databricks.com/aws/en/lakehouse/), checked 2026-09-27).

**How this repo uses it:** One Unity Catalog schema (`workspace.fraud`) holds four governed Volumes and a managed Delta Bronze table; checkpoints live on a Volume, not the deprecated DBFS root ([docs](https://docs.databricks.com/aws/en/dbfs/), checked 2026-09-27). See [setup SQL](../../../sql/10_fraud_ingest_setup.sql) and [ADR 0001](../../adr/0001-checkpoints-on-unity-catalog-volumes.md).

**What was verified:** 2026-09-22, a real checkpoint-write spike on Free Edition serverless produced a normal checkpoint directory on a Volume (`docs/GAPS.md` G-03).

**Key terms:** Delta Lake, Unity Catalog, Volume, Bronze table.

**Go deeper:** private study notes (drills, diagrams, traps) live outside the public repo.
