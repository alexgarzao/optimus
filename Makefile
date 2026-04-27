.PHONY: test lint check-inline inline-stats sync-plugins

test:
	python3 -m pytest scripts/ -v

lint:
	python3 -m py_compile scripts/inline-protocols.py
	ruff check scripts/
	shellcheck sync/scripts/sync-user-plugins.sh

check-inline:
	python3 scripts/inline-protocols.py
	@git diff --exit-code -- '*/skills/*/SKILL.md' || (echo "ERROR: SKILL.md files are stale. Run 'python3 scripts/inline-protocols.py' and commit." && exit 1)

# Phase 1 of issue #34: report on inline-protocol bloat across all SKILLs.
# Doesn't modify any files. Use --no-summarize via `python3 scripts/inline-protocols.py
# --stats-only --no-summarize` for a baseline (all-full-body) measurement.
inline-stats:
	@python3 scripts/inline-protocols.py --stats-only

sync-plugins:
	bash sync/scripts/sync-user-plugins.sh
