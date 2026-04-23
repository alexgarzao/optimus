.PHONY: test lint check-inline sync-plugins

test:
	python3 -m pytest scripts/test_inline_protocols.py scripts/test_sync_user_plugins.py scripts/test_skill_consistency.py -v

lint:
	python3 -m py_compile scripts/inline-protocols.py
	ruff check scripts/
	shellcheck help/scripts/sync-user-plugins.sh

check-inline:
	python3 scripts/inline-protocols.py
	@git diff --exit-code -- '*/skills/*/SKILL.md' || (echo "ERROR: SKILL.md files are stale. Run 'python3 scripts/inline-protocols.py' and commit." && exit 1)

sync-plugins:
	bash help/scripts/sync-user-plugins.sh
