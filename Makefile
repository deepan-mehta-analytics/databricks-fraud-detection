# Honest stub Makefile: only targets that really work are implemented.
# Everything else fails loudly with the phase that will provide it.

.PHONY: help check-hygiene lint test deploy teardown # all targets are commands, not files

# ── Working targets ───────────────────────────────────────────────
help: # list available targets
	@echo "Working:  check-hygiene test"
	@echo "Stubbed:  lint deploy teardown (fail until their phase lands)"

check-hygiene: # fail if a local-only or secret file is tracked by git
	@if git ls-files | grep -vx '\.env\.example' | grep -E '^(\.env|CLAUDE\.md|workflow_status)'; then echo "ERROR: local-only file is tracked"; exit 1; fi
	@echo "hygiene OK"

test: # run the local unit tests (no Databricks needed)
	python -m pytest -q

# ── Stubs (exit 1 so nothing pretends to pass) ────────────────────
lint: # Python source exists (src/fraud_ingest); no lint tool is wired up yet
	@echo "lint: not implemented (Phase 2)"; exit 1

deploy: # resources/fraud_ingest_job.yml exists; bundle deploy on Free Edition is unverified (G-11) and user-run only
	@echo "deploy: not implemented (Phase 6)"; exit 1

teardown: # nothing cost-bearing exists since ADR 0007 (Free Edition only); kept as a stub
	@echo "teardown: nothing to tear down (ADR 0007, Free Edition only). Log any future cost-bearing teardown in docs/cost-model.md"; exit 1
