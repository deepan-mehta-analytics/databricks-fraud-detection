# ADR 0002: Group Grants and Native Row and Column Security

## Status
Proposed

## Context
The brief used `GRANT ... TO ROLE business_users` and "row-level security"
through dynamic views. Current Unity Catalog documentation names only users,
service principals and groups as grant targets, and does not document `role`
as a principal type (gap G-06, `docs/GAPS.md`). Reading a table needs
`SELECT` on the table plus `USE CATALOG` and `USE SCHEMA` on its parents.
Row filters (`ALTER TABLE ... SET ROW FILTER fn ON (col)`) and column masks
(`ALTER COLUMN ... SET MASK fn`) are the native mechanisms. Dynamic views are
still supported, and the docs position them for curated, transformed or
joined views.

## Decision
- Grant `USE CATALOG`, `USE SCHEMA` and `SELECT` to groups, never to
  individual users and never to a `role` principal.
- Implement row-level restrictions with row filters, and sensitive-column
  restrictions with column masks, on the Gold tables.
- Use a dynamic view only where a curated or joined view is the point, such
  as an analyst-facing alerts view.
- Keep all DDL and grants in `sql/`, with no workspace identifiers.

## Consequences
**Positive:** governance work uses the documented native mechanisms, which is
also what a reviewer would expect to see in a Unity Catalog project.
**Confirmed 2026-09-22:** a real spike on `workspace.default` (Free Edition
serverless) verified `GRANT USE CATALOG`/`USE SCHEMA`/`SELECT` to a group,
`ALTER TABLE ... SET ROW FILTER`, and `ALTER TABLE ... ALTER COLUMN ...
SET MASK` all work and are actually enforced — a row outside the filter
was excluded entirely, and the masked column returned `REDACTED`. See
`docs/GAPS.md` G-06.
**Negative:** the spike granted to the pre-existing `account users` group,
not a newly created one — whether Free Edition supports *creating* a new
custom group is still unverified. Free Edition's documented "no account
console access" limitation suggests it may not be possible; a
workspace-admin-settings path (Settings → Identity and access → Groups)
hasn't been tried yet and is the next thing to test.

## Alternatives rejected
- **`TO ROLE` grants** — rejected; `role` is not a documented grant target.
- **Dynamic views for all row security** — rejected; still supported, but
  the docs position them for curated views, and native filters are the
  intended row-security mechanism.
