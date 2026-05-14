.PHONY: test lint check-inline inline-stats sync-plugins sync-claude-commands sync-opencode-commands sync-commands

test:
	python3 -m pytest scripts/ -v

lint:
	python3 -m py_compile scripts/inline-protocols.py
	ruff check scripts/
	shellcheck sync/scripts/sync-user-plugins.sh

check-inline:
	python3 scripts/inline-protocols.py
	@git diff --exit-code -- '*/skills/*/SKILL.md' || (echo "ERROR: SKILL.md files are stale. Run 'python3 scripts/inline-protocols.py' and commit." && exit 1)

# Regenerate per-platform commands directories from SKILL.md sources.
# Run after editing a SKILL.md description or any alias file.
sync-claude-commands:
	python3 scripts/sync-claude-commands.py

sync-opencode-commands:
	python3 scripts/sync-opencode-commands.py

sync-commands: sync-claude-commands sync-opencode-commands

# Phase 1 of issue #34: report on inline-protocol bloat across all SKILLs.
# Doesn't modify any files. Use --no-summarize via `python3 scripts/inline-protocols.py
# --stats-only --no-summarize` for a baseline (all-full-body) measurement.
inline-stats:
	@python3 scripts/inline-protocols.py --stats-only

sync-plugins:
	bash sync/scripts/sync-user-plugins.sh
