# Choosing an Ingestion Method

**In plain words:** Databricks offers several ways to bring data in — managed connectors, Lakeflow pipelines, Auto Loader, COPY INTO, or a custom client — and the right one depends on the source, volume, frequency, and what the account can actually reach.

**Everyday analogy:** It's picking a delivery method for a package: a courier service if the address is on their route, your own van if it isn't, and never promising overnight shipping to a place with no road access.

**Why real teams use it:** Databricks recommends starting with the most managed layer and dropping down only if it can't reach the source or meet the requirement ([docs](https://docs.databricks.com/aws/en/ingestion/), checked 2026-09-27).

**How this repo uses it:** Kafka was the original plan, but Free Edition's serverless compute cannot resolve untrusted hostnames without identity verification, so Auto Loader over file replay was chosen instead — the only source reachable from inside the workspace. See [ADR 0007](../../adr/0007-file-based-ingest-with-auto-loader.md).

**What was verified:** 2026-09-24, a real egress probe: an untrusted host failed DNS resolution while `pypi.org` connected (`docs/GAPS.md` G-01).

**Key terms:** Auto Loader, Lakeflow Connect, COPY INTO, trusted domains.

**Go deeper:** private study notes (drills, diagrams, traps) live outside the public repo.
