# Grants, Row Filters, and Column Masks

**In plain words:** Unity Catalog controls access in layers: GRANT decides who can use a catalog, schema, or table at all; a row filter hides entire rows from a user group; a column mask replaces a sensitive column's value for them.

**Everyday analogy:** GRANT is the building pass that lets you into the office; a row filter is a shared folder that only shows you your own team's files; a column mask is a redacted line on a shared document that others can't unblur.

**Why real teams use it:** These are Unity Catalog's documented native mechanisms for access control and fine-grained security, evaluated at query time on every read ([docs](https://docs.databricks.com/aws/en/data-governance/unity-catalog/row-and-column-filters), checked 2026-09-27).

**How this repo uses it:** Grants go to groups, never individual users or a `role` (not a documented principal type) ([docs](https://docs.databricks.com/aws/en/data-governance/unity-catalog/manage-privileges/), checked 2026-09-27). See [ADR 0002](../../adr/0002-group-grants-and-native-row-security.md).

**What was verified:** 2026-09-22, a real spike on `workspace.default`: `GRANT USE CATALOG`/`USE SCHEMA`/`SELECT`, a row filter, and a column mask were all enforced — an excluded row disappeared and a masked column read `REDACTED` (`docs/GAPS.md` G-06).

**Key terms:** GRANT, `USE CATALOG`, row filter, column mask.

**Go deeper:** private study notes (drills, diagrams, traps) live outside the public repo.
