#!/usr/bin/env python3
"""Regression tests for the worktree-isolation fix.

Bug context: `.optimus/state.json`, `.optimus/stats.json`, `.optimus/sessions/`,
`.optimus/reports/`, and checkpoint markers are gitignored. Git does NOT
propagate ignored files across linked worktrees. Skills that resolve these
paths against `$PWD` (relative path) write to the worktree's isolated copy
when run from a linked worktree. When the worktree is later removed (e.g.,
by `/optimus-done` cleanup), the writes are lost — silent data loss.

Real incident: T-037 in `plugin-br-payments` had wrong status forever,
blocking 3 dependent tasks.

The fix introduces `Protocol: Resolve Main Worktree Path` and prefixes all
`.optimus/` paths with `${MAIN_WORKTREE}` (resolved via
`git worktree list --porcelain`).

These tests fail if any relative `.optimus/` path reappears in AGENTS.md or
any SKILL.md (except inside the documented `# WRONG` example block of the
resolver protocol itself).
"""

from __future__ import annotations

import re
import subprocess
import textwrap
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
AGENTS_MD = REPO_ROOT / "AGENTS.md"


def _read(path: Path) -> str:
    return path.read_text()


def _all_skill_files() -> list[Path]:
    return sorted(REPO_ROOT.glob("*/skills/*/SKILL.md"))


def _strip_inlined_block(content: str) -> str:
    """Return only the body region of a SKILL.md (above INLINE-PROTOCOLS:START)."""
    return content.split("<!-- INLINE-PROTOCOLS:START -->", 1)[0]


def _strip_wrong_example_block(content: str) -> str:
    """Strip the documented `# WRONG (resolves against PWD...)` example block
    from AGENTS.md so the regression detector doesn't flag the intentional
    counter-example inside Protocol: Resolve Main Worktree Path.

    The block is a fenced bash code block that starts with the `# WRONG` comment.
    """
    # The WRONG example is inside a single fenced bash block. Find the comment
    # and strip from the comment's line through the next ``` on its own line.
    lines = content.splitlines()
    out_lines: list[str] = []
    skip = False
    for line in lines:
        if not skip and "# WRONG (resolves against PWD" in line:
            skip = True
            continue
        if skip:
            # Skip until we hit a closing ``` (end of fenced block).
            if line.strip() == "```":
                skip = False
            continue
        out_lines.append(line)
    return "\n".join(out_lines)


# --- Patterns ---

# Bare path assignments (LHS is the variable, RHS starts with .optimus/...)
RELATIVE_PATH_ASSIGN_RE = re.compile(
    r'^\s*(STATE_FILE|STATS_FILE|SESSION_FILE|FETCH_MARKER|REPORT_FILE|REPORT_DIR|CONFIG_FILE)\s*=\s*"\.optimus/',
    re.MULTILINE,
)

# Bare mkdir / rm / find on .optimus paths (excluding gitignore patterns,
# which are project-rooted by convention and stay as-is).
RELATIVE_OPTIMUS_BASH_RE = re.compile(
    r'(?:mkdir\s+-p\s+|find\s+|ls\s+(?:-1t\s+)?|cat\s+|rm\s+-f\s+)(?:"\s*)?\.optimus/'
)

# Migration / rename checkpoint markers as bare paths.
RELATIVE_CHECKPOINT_RE = re.compile(
    r'(?:>|<|\[\s*-f|\bcat)\s*\.optimus/\.(?:migration|rename|last-tasks)'
)


class TestAgentsMdMainWorktreeResolver:
    """AGENTS.md must define and use Protocol: Resolve Main Worktree Path."""

    def test_resolver_protocol_exists(self):
        content = _read(AGENTS_MD)
        assert "### Protocol: Resolve Main Worktree Path" in content, (
            "AGENTS.md must define `### Protocol: Resolve Main Worktree Path` — "
            "this is the canonical recipe for resolving .optimus/ paths against "
            "the main worktree (fixes worktree-isolation data loss)."
        )

    def test_resolver_uses_git_worktree_list_porcelain(self):
        content = _read(AGENTS_MD)
        assert "git worktree list --porcelain" in content, (
            "Resolver protocol must use `git worktree list --porcelain` "
            "(machine-readable, stable across git versions). The first "
            "`worktree` line is always the main worktree."
        )

    def test_resolver_documents_wrong_pattern(self):
        content = _read(AGENTS_MD)
        assert "# WRONG" in content and "PWD" in content, (
            "Resolver protocol must include a `# WRONG (resolves against PWD...)` "
            "example showing the broken pattern, so future contributors don't "
            "accidentally regress to relative paths."
        )

    def test_no_relative_optimus_state_paths_outside_wrong_block(self):
        """AGENTS.md must NOT have any STATE_FILE/STATS_FILE/SESSION_FILE/etc.
        relative-path assignment outside the documented WRONG example."""
        content = _strip_wrong_example_block(_read(AGENTS_MD))
        violations = []
        for m in RELATIVE_PATH_ASSIGN_RE.finditer(content):
            line_no = content[: m.start()].count("\n") + 1
            violations.append(f"AGENTS.md:{line_no}: {m.group(0).strip()}")
        assert violations == [], (
            "Found relative .optimus/ path assignments in AGENTS.md (outside "
            "the documented WRONG example block):\n"
            + "\n".join(f"  - {v}" for v in violations)
            + "\n\nFix: prefix with ${MAIN_WORKTREE}/, e.g. "
            'STATE_FILE="${MAIN_WORKTREE}/.optimus/state.json"'
        )

    def test_no_relative_optimus_bash_outside_wrong_block(self):
        """No bare `mkdir -p .optimus/...` / `find .optimus/...` / etc. in
        AGENTS.md outside the documented WRONG example. Gitignore-pattern lines
        (which are project-rooted by convention) are excluded by the regex."""
        content = _strip_wrong_example_block(_read(AGENTS_MD))
        violations = []
        for m in RELATIVE_OPTIMUS_BASH_RE.finditer(content):
            line_no = content[: m.start()].count("\n") + 1
            ctx = content.splitlines()[line_no - 1].strip()
            # Skip gitignore-pattern blocks (where .optimus/ appears as
            # part of a `printf '...' >> .gitignore` heredoc-style payload).
            if ".gitignore" in ctx or "printf" in ctx:
                continue
            violations.append(f"AGENTS.md:{line_no}: {ctx}")
        assert violations == [], (
            "Found relative .optimus/ bash usage in AGENTS.md:\n"
            + "\n".join(f"  - {v}" for v in violations)
        )


class TestSkillBodiesUseMainWorktreePrefix:
    """Every SKILL.md body must prefix .optimus/ paths with ${MAIN_WORKTREE}/.

    Inlined blocks (between INLINE-PROTOCOLS:START/END) are auto-regenerated
    from AGENTS.md and are checked separately by AGENTS.md tests above.
    """

    def test_no_relative_state_paths_in_skill_bodies(self):
        violations = []
        for skill_path in _all_skill_files():
            body = _strip_inlined_block(_read(skill_path))
            for m in RELATIVE_PATH_ASSIGN_RE.finditer(body):
                line_no = body[: m.start()].count("\n") + 1
                rel = skill_path.relative_to(REPO_ROOT)
                violations.append(f"{rel}:{line_no}: {m.group(0).strip()}")
        assert violations == [], (
            "Found relative .optimus/ path assignments in SKILL.md bodies. "
            "These will write to the worktree's isolated copy when the skill "
            "runs from a linked worktree, causing silent data loss:\n"
            + "\n".join(f"  - {v}" for v in violations)
            + "\n\nFix: use ${MAIN_WORKTREE}/.optimus/... after invoking "
            "AGENTS.md Protocol: Resolve Main Worktree Path."
        )

    def test_no_relative_checkpoint_markers_in_skill_bodies(self):
        violations = []
        for skill_path in _all_skill_files():
            body = _strip_inlined_block(_read(skill_path))
            for m in RELATIVE_CHECKPOINT_RE.finditer(body):
                line_no = body[: m.start()].count("\n") + 1
                rel = skill_path.relative_to(REPO_ROOT)
                violations.append(f"{rel}:{line_no}: {m.group(0).strip()}")
        assert violations == [], (
            "Found relative .optimus/.{migration,rename,last-tasks} "
            "checkpoint markers in SKILL.md bodies. Same data-loss risk as "
            "state.json:\n"
            + "\n".join(f"  - {v}" for v in violations)
        )


def _run(cmd, cwd=None, env=None):
    """Run a command, capturing both stdout and stderr. Returns (rc, out, err)."""
    result = subprocess.run(
        cmd, cwd=cwd, env=env,
        capture_output=True, text=True, check=False,
    )
    return result.returncode, result.stdout, result.stderr


def _init_repo(path: Path):
    """Initialize a minimal git repo at `path` with a single committed file.

    The committed file is required because `git worktree add` refuses to operate
    on an unborn HEAD (no commits yet).
    """
    path.mkdir(parents=True, exist_ok=True)
    _run(["git", "init", "--initial-branch=main"], cwd=path)
    _run(["git", "config", "user.email", "test@example.com"], cwd=path)
    _run(["git", "config", "user.name", "Test"], cwd=path)
    _run(["git", "config", "commit.gpgsign", "false"], cwd=path)
    (path / "README.md").write_text("# test\n")
    _run(["git", "add", "README.md"], cwd=path)
    _run(["git", "commit", "-m", "initial"], cwd=path)


def _extract_resolver_bash() -> str:
    """Extract the recipe bash block from Protocol: Resolve Main Worktree Path.

    The protocol contains multiple bash blocks (the recipe + RIGHT/WRONG examples).
    This helper returns ONLY the first block, which is the canonical recipe that
    sets `MAIN_WORKTREE` and exits 1 on failure.
    """
    content = AGENTS_MD.read_text()
    marker = "### Protocol: Resolve Main Worktree Path"
    idx = content.find(marker)
    if idx == -1:
        raise RuntimeError("Protocol: Resolve Main Worktree Path missing")
    next_idx = content.find("\n### ", idx + len(marker))
    section = content[idx:next_idx] if next_idx != -1 else content[idx:]
    bash_start = section.find("```bash\n")
    if bash_start == -1:
        raise RuntimeError("No bash block under Resolve Main Worktree Path")
    bash_end = section.find("\n```", bash_start + len("```bash\n"))
    return section[bash_start + len("```bash\n"):bash_end]


class TestResolverIntegration:
    """End-to-end tests of the Protocol: Resolve Main Worktree Path bash recipe
    against real git worktrees in tmp_path. These tests catch regressions that
    static-analysis tests can't (e.g., a broken `awk` regex).
    """

    def test_resolver_returns_main_path_from_main_worktree(self, tmp_path: Path):
        """Running the resolver from the main worktree itself returns the main path."""
        repo = tmp_path / "project"
        _init_repo(repo)
        recipe = _extract_resolver_bash()
        probe = recipe + '\necho "RESULT=$MAIN_WORKTREE"\n'
        rc, out, err = _run(["bash", "-c", probe], cwd=repo)
        assert rc == 0, f"Resolver should succeed in main worktree (err={err})"
        # On macOS tmp_path can be /private/var/... while repo path is /var/...
        # Both resolve to the same location; compare via realpath.
        actual = [line.split("=", 1)[1] for line in out.splitlines()
                  if line.startswith("RESULT=")][0]
        assert Path(actual).resolve() == repo.resolve(), (
            f"Expected MAIN_WORKTREE={repo}, got {actual}"
        )

    def test_resolver_returns_main_path_from_linked_worktree(self, tmp_path: Path):
        """Running the resolver from a LINKED worktree must return the MAIN
        worktree's path, not the linked one. This is THE bug the protocol fixes."""
        main = tmp_path / "project"
        _init_repo(main)
        # Create a linked worktree at sibling location.
        linked = tmp_path / "project-linked"
        rc, _, err = _run(
            ["git", "worktree", "add", "-b", "feature", str(linked)],
            cwd=main,
        )
        assert rc == 0, f"git worktree add failed: {err}"

        recipe = _extract_resolver_bash()
        probe = recipe + '\necho "RESULT=$MAIN_WORKTREE"\n'
        # CRITICAL: cwd is the LINKED worktree, not main.
        rc, out, err = _run(["bash", "-c", probe], cwd=linked)
        assert rc == 0, f"Resolver should succeed in linked worktree (err={err})"
        actual = [line.split("=", 1)[1] for line in out.splitlines()
                  if line.startswith("RESULT=")][0]
        # Must resolve to MAIN, not the linked worktree.
        assert Path(actual).resolve() == main.resolve(), (
            f"Resolver returned the LINKED path, defeating the entire fix.\n"
            f"  Expected MAIN_WORKTREE={main}\n"
            f"  Got      MAIN_WORKTREE={actual}\n"
            f"  CWD                    ={linked}"
        )
        assert Path(actual).resolve() != linked.resolve(), (
            "Resolver returned linked path — bug regression"
        )

    def test_resolver_fails_in_non_git_directory(self, tmp_path: Path):
        """Outside any git repo, the resolver must exit 1 with a clear error."""
        non_git = tmp_path / "not-a-repo"
        non_git.mkdir()
        recipe = _extract_resolver_bash()
        rc, out, err = _run(["bash", "-c", recipe], cwd=non_git)
        assert rc != 0, "Resolver should fail outside a git repo"
        assert "not in a git repository" in err.lower() or "main worktree" in err.lower(), (
            f"Expected a clear error about main worktree resolution, got: {err}"
        )

    def test_state_write_from_linked_worktree_lands_in_main(self, tmp_path: Path):
        """End-to-end: a state.json write using ${MAIN_WORKTREE}/.optimus/state.json
        from a linked worktree must create the file at MAIN, not at the linked path.

        This is the canonical regression for the T-037 incident: optimus-done writing
        from a linked worktree, then `git worktree remove` deleting the linked
        worktree, used to drop the state update on the floor.
        """
        main = tmp_path / "project"
        _init_repo(main)
        linked = tmp_path / "project-linked"
        rc, _, err = _run(
            ["git", "worktree", "add", "-b", "feature", str(linked)],
            cwd=main,
        )
        assert rc == 0, f"git worktree add failed: {err}"

        recipe = _extract_resolver_bash()
        # Simulate the State Management protocol's write pattern.
        probe = recipe + textwrap.dedent("""
            mkdir -p "${MAIN_WORKTREE}/.optimus"
            STATE_FILE="${MAIN_WORKTREE}/.optimus/state.json"
            echo '{"T-001": {"status": "DONE"}}' > "$STATE_FILE"
            echo "WROTE=$STATE_FILE"
        """)
        rc, out, err = _run(["bash", "-c", probe], cwd=linked)
        assert rc == 0, f"State write failed (err={err})"

        # Assert the file landed in MAIN, NOT in the linked worktree.
        main_state = main / ".optimus" / "state.json"
        linked_state = linked / ".optimus" / "state.json"
        assert main_state.exists(), (
            f"state.json should exist in main worktree at {main_state} — "
            "this is the file that survives `git worktree remove`."
        )
        assert not linked_state.exists(), (
            f"state.json must NOT exist in the linked worktree at {linked_state}. "
            "The fix MUST route writes through ${MAIN_WORKTREE}/, not relative paths."
        )
        assert "T-001" in main_state.read_text(), "state.json content lost"

    def test_resolver_works_after_worktree_removal(self, tmp_path: Path):
        """After `git worktree remove`, the resolver still works from main —
        confirms the cleanup path documented in optimus-done is consistent
        with the resolver's expectations.
        """
        main = tmp_path / "project"
        _init_repo(main)
        linked = tmp_path / "project-linked"
        _run(["git", "worktree", "add", "-b", "feature", str(linked)], cwd=main)

        # Write state from linked worktree.
        recipe = _extract_resolver_bash()
        probe = recipe + textwrap.dedent("""
            mkdir -p "${MAIN_WORKTREE}/.optimus"
            echo '{"T-001": {"status": "DONE"}}' > "${MAIN_WORKTREE}/.optimus/state.json"
        """)
        rc, _, err = _run(["bash", "-c", probe], cwd=linked)
        assert rc == 0, f"linked-worktree write failed: {err}"

        # Now remove the linked worktree (the T-037 cleanup step).
        rc, _, err = _run(
            ["git", "worktree", "remove", "--force", str(linked)],
            cwd=main,
        )
        assert rc == 0, f"worktree remove failed: {err}"

        # The state.json must still exist in main — survived the worktree removal.
        main_state = main / ".optimus" / "state.json"
        assert main_state.exists(), (
            "state.json was deleted along with the linked worktree — "
            "exactly the T-037 incident this protocol exists to prevent."
        )
        assert "T-001" in main_state.read_text()


class TestSkillBodiesUseMainWorktrePrefixForReadsAndAppends:
    """Bodies of SKILL.md files (above INLINE-PROTOCOLS:START), AGENTS.md, and
    `scripts/inline-protocols.py` must NOT contain unprefixed `.optimus/` reads
    nor unprefixed `.gitignore` mutations. These caught the F1 incident
    (worktree-isolation, T-037 — silent state.json data loss).

    Each test method targets one source-class:
      - F1.1a — `local log=".optimus/...` patterns inside helpers.
      - F1.1b — `.gitignore` mutations (`>> .gitignore` and
        `grep -q ... .gitignore`) without `${MAIN_WORKTREE}/` prefix.
      - F1.1c/1d — inline `jq` reads and `[ -f` checks against `.optimus/<file>.json`
        without `${MAIN_WORKTREE}/` prefix.

    Detection skips fenced bash blocks that ARE the documented `# WRONG` example
    of the resolver protocol (see `_strip_wrong_example_block`).
    """

    # `local <var>=".optimus/...` — caught the F1 1a (_optimus_quiet_run helper).
    LOCAL_LOG_OPTIMUS_RE = re.compile(
        r'^\s*local\s+\w+\s*=\s*"\.optimus/',
        re.MULTILINE,
    )
    # `.gitignore` mutations without `${MAIN_WORKTREE}/` (or `$MAIN_WORKTREE/`) prefix.
    # Catches:  printf '...' >> .gitignore   and   grep -q '...' .gitignore
    # Skips:    printf '...' >> "${MAIN_WORKTREE}/.gitignore"
    GITIGNORE_BARE_APPEND_RE = re.compile(
        r'>>\s*(?!"?\$\{?MAIN_WORKTREE)(?:"\s*)?\.gitignore\b',
    )
    GITIGNORE_BARE_GREP_RE = re.compile(
        r'\bgrep\s+-q\b[^\n]*?\s(?!"?\$\{?MAIN_WORKTREE)(?:"\s*)?\.gitignore\b',
    )
    # Inline jq/[ -f reads against bare `.optimus/<file>.json` (no `${MAIN_WORKTREE}/`).
    # Targets the F1 1c (done state.json read) and F1 1d (import config.json read)
    # classes. Excludes:
    #   - LHS assignments (handled by RELATIVE_PATH_ASSIGN_RE)
    #   - lines mentioning `${MAIN_WORKTREE}` already (the `>` redirection target
    #     would still match the read on the same line of mv).
    JQ_READ_BARE_OPTIMUS_RE = re.compile(
        r'(?:\bjq\b[^\n]*?|\[\s+-f\s+|\bcat\s+|\bmv\s+)(?:"\s*)?\.optimus/(?:state|stats|config|sessions|reports)(?:\.json|/)',
    )

    def _scan_targets(self) -> list[tuple[str, str]]:
        """Return [(label, content), ...] for every source we scan.

        - SKILL.md bodies (above INLINE-PROTOCOLS:START)
        - AGENTS.md (full, minus the documented `# WRONG` example)
        - scripts/inline-protocols.py (full)
        """
        targets: list[tuple[str, str]] = []
        for skill_path in _all_skill_files():
            rel = skill_path.relative_to(REPO_ROOT)
            targets.append((str(rel), _strip_inlined_block(_read(skill_path))))
        targets.append(
            ("AGENTS.md", _strip_wrong_example_block(_read(AGENTS_MD)))
        )
        inliner = REPO_ROOT / "scripts" / "inline-protocols.py"
        if inliner.exists():
            targets.append(("scripts/inline-protocols.py", _read(inliner)))
        return targets

    def test_no_local_optimus_log_paths(self):
        """`local log=".optimus/..."` (and similar `local <var>=".optimus/...")
        leaks PWD-relative paths inside helpers (F1 1a — _optimus_quiet_run
        was logging to the linked worktree's .optimus/logs/)."""
        violations: list[str] = []
        for label, content in self._scan_targets():
            for m in self.LOCAL_LOG_OPTIMUS_RE.finditer(content):
                line_no = content[: m.start()].count("\n") + 1
                ctx = content.splitlines()[line_no - 1].strip()
                violations.append(f"{label}:{line_no}: {ctx}")
        assert violations == [], (
            "Found `local <var>=\".optimus/...\"` patterns. These resolve "
            "against PWD and write to the linked-worktree's isolated .optimus/, "
            "losing data on `git worktree remove`:\n"
            + "\n".join(f"  - {v}" for v in violations)
            + "\n\nFix: build the path from ${MAIN_WORKTREE}/.optimus/... after "
            "invoking AGENTS.md Protocol: Resolve Main Worktree Path."
        )

    def test_no_bare_gitignore_mutations(self):
        """`>> .gitignore` and `grep -q ... .gitignore` without
        `${MAIN_WORKTREE}/` prefix (F1 1b — Initialize .optimus Directory and
        Session State were appending to the linked worktree's .gitignore)."""
        violations: list[str] = []
        for label, content in self._scan_targets():
            for regex, kind in (
                (self.GITIGNORE_BARE_APPEND_RE, "append"),
                (self.GITIGNORE_BARE_GREP_RE, "grep"),
            ):
                for m in regex.finditer(content):
                    line_no = content[: m.start()].count("\n") + 1
                    ctx = content.splitlines()[line_no - 1].strip()
                    violations.append(f"{label}:{line_no} [{kind}]: {ctx}")
        assert violations == [], (
            "Found bare `.gitignore` mutations (no ${MAIN_WORKTREE}/ prefix). "
            "When run from a linked worktree, these update only the linked "
            "worktree's .gitignore — the main worktree never gets the "
            "operational-files block:\n"
            + "\n".join(f"  - {v}" for v in violations)
            + "\n\nFix: use \"${MAIN_WORKTREE}/.gitignore\" after invoking "
            "AGENTS.md Protocol: Resolve Main Worktree Path."
        )

    def test_no_inline_optimus_json_reads_without_prefix(self):
        """Inline `jq ... .optimus/<file>.json` and `[ -f .optimus/<file>.json ]`
        reads must use ${MAIN_WORKTREE}/ (F1 1c — done was reading state.json
        from the linked worktree; F1 1d — import was writing config.json to
        the linked worktree)."""
        violations: list[str] = []
        for label, content in self._scan_targets():
            for m in self.JQ_READ_BARE_OPTIMUS_RE.finditer(content):
                line_no = content[: m.start()].count("\n") + 1
                ctx = content.splitlines()[line_no - 1].strip()
                # Skip if the line ALSO uses ${MAIN_WORKTREE} elsewhere (e.g.,
                # `mv "${MAIN_WORKTREE}/.optimus/config.json.tmp" "${MAIN_WORKTREE}/.optimus/config.json"`
                # has only-prefixed references).
                if "${MAIN_WORKTREE}" in ctx or "$MAIN_WORKTREE" in ctx:
                    continue
                violations.append(f"{label}:{line_no}: {ctx}")
        assert violations == [], (
            "Found inline reads against bare `.optimus/<file>.json` paths. "
            "These resolve to the linked worktree's isolated copy, which is "
            "lost on `git worktree remove` (T-037 silent data-loss class):\n"
            + "\n".join(f"  - {v}" for v in violations)
            + "\n\nFix: prefix the path with \"${MAIN_WORKTREE}/\", e.g. "
            "`jq ... \"${MAIN_WORKTREE}/.optimus/state.json\"`."
        )


class TestInlineProtocolsInjectsMainWorktree:
    """The propagation script must wire Protocol: Resolve Main Worktree Path
    into any skill that touches .optimus/ files.

    Post-Phase-9 contract (`Protocol: Resolve Main Worktree Path` moved to
    ``<!-- inline-mode: omit -->``): the inliner emits NO heading or stub for
    this protocol. The sync signal is now structural — every skill that
    inlines a state-touching protocol must, somewhere in its authored
    content, prove it consumes the resolver's contract by either:

      (a) referencing the protocol by name (``Protocol: Resolve Main Worktree Path``), OR
      (b) using ``${MAIN_WORKTREE}`` in bash blocks / referenced summaries.

    Either signal demonstrates the skill respects the worktree-isolation
    contract. The test is layout-aware: for skills migrated to the index +
    ``phases/`` layout, the body lives across SKILL.md and every ``.md`` file
    under the skill dir, so the search scope spans the full plugin tree.
    """

    _TRIGGERS = (
        "### Protocol: State Management",
        "### Protocol: Session State",
        "### Protocol: Increment Stage Stats",
        "### Protocol: Initialize .optimus Directory",
        "### Protocol: Divergence Warning",
    )
    _CONSUMER_SIGNALS = (
        "Protocol: Resolve Main Worktree Path",
        "MAIN_WORKTREE",
    )

    @staticmethod
    def _skill_content(skill_path: Path) -> str:
        """Read SKILL.md plus every other .md file in the skill dir.

        Progressive-disclosure skills extract bash blocks and prose into
        ``phases/*.md`` siblings; the consumer-signal check has to follow
        the content there, otherwise migrated skills appear "empty" even
        though they still consume ``${MAIN_WORKTREE}`` exactly as before.
        """
        skill_dir = skill_path.parent
        parts = [skill_path.read_text()]
        for md in sorted(skill_dir.rglob("*.md")):
            if md == skill_path:
                continue
            parts.append(md.read_text())
        return "\n".join(parts)

    def test_state_touching_skills_have_main_worktree_inlined(self):
        """Skills that inline a state-touching protocol must consume the
        main-worktree resolver — either by reference (``Protocol: Resolve
        Main Worktree Path``) or by usage (``${MAIN_WORKTREE}``)."""
        violations = []
        for skill_path in _all_skill_files():
            skill_md_content = skill_path.read_text()
            inlined_start = skill_md_content.find("<!-- INLINE-PROTOCOLS:START -->")
            if inlined_start == -1:
                continue  # skill has no inlined block (e.g., help, sync)
            inlined = skill_md_content[inlined_start:]
            triggered = [t for t in self._TRIGGERS if t in inlined]
            if not triggered:
                continue
            content = self._skill_content(skill_path)
            if not any(sig in content for sig in self._CONSUMER_SIGNALS):
                rel = skill_path.relative_to(REPO_ROOT)
                violations.append(
                    f"{rel}: inlines {triggered} but does not reference "
                    f"the resolver protocol or use ${{MAIN_WORKTREE}} anywhere"
                )
        assert violations == [], (
            "Skills inlining state-touching protocols are not consuming the "
            "main-worktree resolver contract. Either add a body reference to "
            "`AGENTS.md Protocol: Resolve Main Worktree Path` or use "
            "`${MAIN_WORKTREE}/.optimus/...` in bash blocks:\n"
            + "\n".join(f"  - {v}" for v in violations)
        )
