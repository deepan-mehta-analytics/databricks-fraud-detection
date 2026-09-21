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
**Negative:** three things are unverified on Free Edition: whether groups can
be created and managed, whether row filters and column masks run on the
available compute, and the runtime requirements noted in the docs. All three
are checked in the first Phase 5 run, and any failure is recorded in
`docs/GAPS.md`.

## Alternatives rejected
- **`TO ROLE` grants** — rejected; `role` is not a documented grant target.
- **Dynamic views for all row security** — rejected; still supported, but
  the docs position them for curated views, and native filters are the
  intended row-security mechanism.
