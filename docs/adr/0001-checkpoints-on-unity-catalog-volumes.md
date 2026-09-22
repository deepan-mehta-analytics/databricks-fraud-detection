# ADR 0001: Streaming Checkpoints on Unity Catalog Volumes

## Status
Proposed

## Context
The original brief placed streaming checkpoints on DBFS. Current Databricks
documentation says both DBFS root and DBFS mounts are deprecated and not
recommended, and that new accounts are provisioned without access to them
(gap G-03, `docs/GAPS.md`). The docs recommend Unity Catalog volumes,
external locations or workspace files instead.

## Decision
Store streaming checkpoints, and any landing files the pipeline needs, in a
Unity Catalog Volume addressed as `/Volumes/<catalog>/<schema>/<volume>/...`.
The path is supplied through the `UC_CHECKPOINT_VOLUME` setting in
`.env.example`, so no workspace-specific path is committed.

## Consequences
**Positive:** uses the supported, governed storage path; access to
checkpoints follows the same Unity Catalog permissions as the tables.
**Confirmed 2026-09-22:** a real spike (Structured Streaming `rate` source,
`Trigger.AvailableNow`, `checkpointLocation` on a `workspace.default.checkpoint_spike`
Volume, run on serverless in a Databricks Free Edition workspace) produced a
normal checkpoint directory (`commits/`, `metadata`, `offsets/`, `sources/`).
Free Edition serverless can write streaming checkpoints to a Volume path.
See `docs/GAPS.md` G-03 and `docs/superpowers/postmortems/2026-09-22-adr-chessboard-premortem.md`.
**Negative:** deleting the Volume deletes the checkpoints, so a stream
restarted afterwards reprocesses from scratch.

## Alternatives rejected
- **DBFS root or mounts** — rejected; deprecated, and not provisioned for new
  accounts.
- **Workspace files** — rejected; listed by the docs as an option for files,
  but not a designed home for checkpoint state, and it would not be governed
  like a Volume.
- **External location** — not pursued; it needs external cloud storage and
  credentials, which adds setup and possible cost. Not evaluated further.
