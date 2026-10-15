# Tag-Based Policies (ABAC)

**In plain words:** Instead of attaching a mask to each table one by one, you label sensitive columns with a governed tag (for example `pii = account_name`) and write one policy for a whole schema: "mask every column with this tag, for everyone except these groups". New tables are covered as soon as their columns are tagged.

**Everyday analogy:** Per-table masks are like a guard posted at each filing cabinet. A tag policy is a building rule: "any folder with a red sticker is blacked out for visitors". You just put red stickers on the right folders.

**Why real teams use it:** At scale, someone always forgets to add a mask to a new table. A tag-based policy turns that into "remember to tag", and tags can be applied by automation. Policies can attach to a catalog, schema or table, and support row filters and column masks; DENY policies are in Beta ([ABAC](https://docs.databricks.com/aws/en/data-governance/unity-catalog/abac/), checked 2026-10-11).

**How this repo uses it:** As a probe only. The real tables keep their per-table mask and row filter (see the grants note), because the ABAC docs list mixing both on one table as unsupported. [`sql/52_abac_probe.sql`](../../../sql/52_abac_probe.sql) builds a 5-row scratch table, tags its account column, creates one schema policy (`MATCH COLUMNS has_tag_value('pii', 'account_name')`, `TO account users EXCEPT` the trusted groups), checks it as two users, and removes everything. See [ADR 0011](../../adr/0011-governance-groups-masks-and-external-export.md).

**What was verified:** 2026-10-12, Databricks Free Edition: the Governed Tags page exists (Catalog Explorer → Governed Tags), and a governed tag, a column tag and a schema-level `CREATE POLICY` all worked. On the same query, the owner (an engineer) saw real account names, and a test user in `fraud_managers` saw `REDACTED` in all 5 rows. The scratch table had no mask of its own, so the policy alone did the masking.

**Key terms:** ABAC, governed tag, `CREATE POLICY`, `MATCH COLUMNS`, `has_tag_value()`, `EXCEPT`.

**Go deeper:** private study notes (drills, diagrams, traps) live outside the public repo.
