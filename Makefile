# Honest stub Makefile: only targets that really work are implemented.
# Everything else fails loudly with the phase that will provide it.

.PHONY: help check-hygiene lint test deploy teardown # all targets are commands, not files

# ── Working targets ───────────────────────────────────────────────
help: # list available targets
	@echo "Working:  check-hygiene"
	@echo "Stubbed:  lint test deploy teardown (fail until their phase lands)"

check-hygiene: # fail if a local-only or secret file is tracked by git
	@if git ls-files | grep -vx '\.env\.example' | grep -E '^(\.env|CLAUDE\.md|workflow_status)'; then echo "ERROR: local-only file is tracked"; exit 1; fi
	@echo "hygiene OK"

# ── Stubs (exit 1 so nothing pretends to pass) ────────────────────
lint: # no Python source yet
	@echo "lint: not implemented (Phase 2)"; exit 1

test: # no tests yet
	@echo "test: not implemented (Phase 2)"; exit 1

deploy: # no bundle or jobs yet
	@echo "deploy: not implemented (Phase 6)"; exit 1

teardown: # cloud teardown is a manual step until automated
	@echo "teardown: manual for now. Delete the Confluent cluster and log it in docs/cost-model.md"; exit 1
