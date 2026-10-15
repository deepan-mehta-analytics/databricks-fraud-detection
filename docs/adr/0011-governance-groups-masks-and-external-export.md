# ADR 0011: Governance with Groups, Masks, a Tag Policy, and an External Export

## Status
Proposed (2026-10-15). Puts [ADR 0002](0002-group-grants-and-native-row-security.md)
into practice on the Gold tables of [ADR 0010](0010-gold-alert-log-and-case-table.md).

## Context
Gold holds customer account names next to fraud verdicts. Three audiences need
different views of it:

- **Engineers** build and run the pipeline and need everything.
- **Reviewers** investigate alerts and need the real account names.
- **Managers** judge outcomes. They need closed cases and totals, not
  identities, and not cases still under investigation.

The constraints:

- ADR 0002's spike (2026-09-22) proved grants, a row filter and a column mask
  on the built-in `account users` group. Free Edition has no account console,
  so it was unknown whether custom groups or a second user could be created.
- The job writes the tables. If its identity were ever masked or filtered, it
  would read and store `REDACTED` for good. The ABAC docs warn about exactly
  this for pipelines.
- `MERGE` into a table with a row filter fails if the filter looks up another
  table, aggregates, or uses a non-deterministic function (documented).
- Free Edition's outbound network is limited to trusted domains (GAPS G-01),
  so external storage might be unreachable.
- This repo is public: no warehouse ID, bucket name, account ID or token may
  be committed.

## Decision
1. **Three groups:** `fraud_engineers`, `fraud_reviewers`, `fraud_managers`.
   Grants always go to groups, never to people. The owner stays a permanent
   member of `fraud_engineers` and never joins `fraud_managers`. Role tests
   use a second test user.
2. **Engineers get one schema-wide grant** (`USE SCHEMA`, `SELECT`, `EXECUTE`
   on `workspace.fraud`), which also covers tables added later. **Reviewers
   and managers get grants table by table**, so a new table stays invisible
   to them until someone decides to share it (least privilege). Reviewers read
   cases but never get `MODIFY`; the job records verdicts (final review M2).
3. **A row filter on `alert_cases`** (`cases_visible`): engineers and reviewers
   see every case, everyone else sees closed cases only. It reads only the
   row's own `status` plus group membership, so `MERGE` keeps working.
4. **A column mask on `sender_account` and `receiver_account`** in both Gold
   tables (`mask_account`): the real value for engineers and reviewers,
   `REDACTED` for everyone else.
5. **Both functions exempt `fraud_engineers`**, and `gold.sql` refuses to run
   unless the job identity is in that group (CI text guards).
6. **`is_account_group_member()`** checks membership, because Free Edition
   creates account-level groups.
7. **Readers get no `EXECUTE`** on the two functions; Unity Catalog evaluates
   them for the reader without it (plan ruling R4).
8. **Tag-based policy (ABAC) as a probe only,** on a 5-row scratch table
   (`sql/52_abac_probe.sql`). The live tables keep their per-table mask and
   filter, because the docs list mixing both on one table as unsupported
   (plan ruling R2).
9. **An external export to Cloudflare R2 was designed but is not wired in.**
   `sql/gold/export.sql` writes closed cases with no account names (data
   minimisation: files outside Unity Catalog can't be masked), and
   `sql/51_export_setup.sql` holds the setup with placeholder paths only.
   Measured: Free Edition can't reach R2, so the `export` task was removed from
   the job (commit `4222ecc`).
10. **All governance SQL is owner-run once** from `sql/50_governance.sql`,
    after the first job run has created the tables.

## Consequences
**Positive:**
- Each audience sees exactly what its job needs, and the rule holds through
  the summary view too (a row filter follows the reader, not the object).
- A team change is a group-membership edit, with no new grants.
- The job can't silently corrupt its own tables under a mask.

**Negative:**
- One person plays every role, helped by one test user.
- The job runs as the owner, not a service principal (Phase 3 add-on).
- The live tables use per-table masks. Tag-based policies were proven only on
  a scratch table.
- No external table exists, so the managed-versus-external comparison is
  explained but not shown with data.
- Plain grants have no `DENY`: access is "nothing unless granted". ABAC `DENY`
  policies are in Beta and were not tried.

**Checked in real runs (2026-10-11 and 2026-10-12, see `docs/GAPS.md` §6):**
- G1: three custom groups were created (Settings → Identity and access →
  Groups → Add new group to account and workspace), and a second user was
  invited and signed in. The SQL warehouse is named "Serverless Starter
  Warehouse", which the bundle lookup found.
- G1 (R2): a serverless notebook could not resolve
  `example.r2.cloudflarestorage.com` (`[Errno -3] Temporary failure in name
  resolution`), while `pypi.org` resolved. No bucket, token or payment method
  was created. G9 (the export check) was therefore dropped.
- G6a: `sql/50_governance.sql` ran. `SHOW GRANTS` listed `USE SCHEMA`,
  `SELECT` and `EXECUTE` for engineers and `USE SCHEMA` for reviewers and
  managers.
- G3b: run B, the first job run after the masks and filter were attached,
  succeeded and changed nothing.
- G6b: the owner saw all 3,154 cases with 0 `REDACTED` names. The view showed
  3,154 visible cases and 262 closed.
- G7: the test user, in no group, was refused at the schema:
  `[INSUFFICIENT_PERMISSIONS] User does not have USE SCHEMA on Schema
  'workspace.fraud'` (SQLSTATE 42501). They could still use the warehouse.
- G7b: added to `fraud_managers`, the test user saw 262 cases, 0 open, 0
  unmasked names. The view counted 262 visible and 262 closed for them.
- G7c: after `REVOKE SELECT ON TABLE … alert_cases FROM fraud_managers`, the
  test user's next query was refused at once (`does not have SELECT on Table`,
  42501). G7d: a `GRANT` restored the count to 262.
- G8: the Governed Tags screen exists on Free Edition (Catalog Explorer →
  Governed Tags). A governed tag `pii` with value `account_name`, a column tag,
  a redact function and a schema-level `CREATE POLICY … MATCH COLUMNS
  has_tag_value('pii', 'account_name')` all worked. On the same 5 rows, the
  owner saw real account names and the test user in `fraud_managers` saw
  `REDACTED` in all 5. The scratch table had no mask of its own. The scratch
  table and function were removed afterwards; the tag was kept.

## Alternatives rejected
- **Dynamic views for privacy (the brief):** row filters and masks protect the
  table itself, wherever it is read from. A view only protects readers who go
  through it.
- **A schema-wide grant for every group:** it would quietly expose each new
  table to managers.
- **Grants to people:** every team change would mean editing grants.
- **Putting the owner in `fraud_managers` for tests:** the job runs as the
  owner and would write masked data.
- **A filter that checks the verdict in another table:** `MERGE` into the
  filtered table would fail.
- **Replacing the live masks with the tag policy now:** mixing both on one
  table is listed as unsupported, and the per-table masks are proven on the
  live data. Swapping them is a follow-up.
- **Exporting account names to R2:** files outside Unity Catalog can't be
  masked.
- **Keeping a failing `export` task in the job:** it would turn every run red
  for a limit that is already measured.
