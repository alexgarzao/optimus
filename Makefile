.PHONY: test lint check-inline sync-plugins

test:
	python3 -m pytest scripts/test_inline_protocols.py -v

lint:
	python3 -m py_compile scripts/inline-protocols.py

check-inline:
	python3 scripts/inline-protocols.py
	@git diff --exit-code -- '*/skills/*/SKILL.md' || (echo "ERROR: SKILL.md files are stale. Run 'python3 scripts/inline-protocols.py' and commit." && exit 1)

sync-plugins:
	bash help/scripts/sync-user-plugins.sh
