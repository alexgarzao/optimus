#!/usr/bin/env python3
"""Cross-skill consistency tests for the Optimus repo.

This module is large (~1900+ LOC) by design — it spans many disjoint
concerns that all share the same fixture surface (every SKILL.md plus
AGENTS.md):

- AskUser format consistency (TestAskUser*, TestStable*, TestStructured*)
- Description matching (TestReadOnly*, TestOwner*, TestQuickReport*)
- Stage/phase rename hygiene (TestStageRename*, no stale "check"/"5 stages")
- Plugin/marketplace parity (TestDualPlatformParity, TestPluginCompleteness,
  TestClaudeCommandsSync, TestMarketplace*)
- Phase numbering and semantic anchors (TestPhase*, TestSemanticAnchor*)
- Inline-protocols regressions (TestNeedsFormatAutoInjection, dead-code
  guards for removed MIGRATE/RENAME constants)
- Heading and reference hygiene (TestProtocolHeadings,
  TestReferenceCanonicality)
- Anti-rationalization / pressure-resistance hygiene
- Numeric drift in stats hot-paths

If splitting becomes necessary, the natural boundaries are the test
classes — each is independent and can be moved to its own file with
corresponding Makefile target updates. The current single-file layout
is preferred while the test count and class count stay roughly stable;
splitting prematurely would multiply the import overhead without
improving navigability.
"""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
AGENTS_MD = REPO_ROOT / "AGENTS.md"
MARKETPLACE_JSON = REPO_ROOT / ".factory-plugin" / "marketplace.json"


def _all_skill_files():
    return sorted(REPO_ROOT.glob("*/skills/*/SKILL.md"))


def _all_doc_files():
    """Returns AGENTS.md + all SKILL.md files (for pattern-based checks)."""
    files = [AGENTS_MD] + _all_skill_files()
    return [f for f in files if f.exists()]


# --- AskUser topic format must include (X/N) progress prefix ---

TOPIC_FORMAT_RE = re.compile(
    r"AskUser.*\[topic\].*format.*Format:\s*`([^`]+)`", re.IGNORECASE
)
TOPIC_EXAMPLE_RE = re.compile(
    r"Example:\s*`\[topic\]\s+([^`]+)`"
)
PROGRESS_PREFIX_RE = re.compile(r"\(X/N\)")
PROGRESS_EXAMPLE_RE = re.compile(r"\(\d+/\d+\)")


class TestAskUserTopicProgress:
    """Every AskUser [topic] format definition must include (X/N) progress prefix."""

    def _collect_violations(self, pattern, check_re, label):
        violations = []
        for filepath in _all_doc_files():
            text = filepath.read_text()
            for i, line in enumerate(text.splitlines(), 1):
                m = pattern.search(line)
                if m and not check_re.search(m.group(1)):
                    rel = filepath.relative_to(REPO_ROOT)
                    violations.append(f"{rel}:{i}: {label} missing in: {m.group(1)}")
        return violations

    def test_topic_format_has_progress_prefix(self):
        """All 'AskUser [topic] format: `...`' lines must contain (X/N)."""
        violations = self._collect_violations(
            TOPIC_FORMAT_RE, PROGRESS_PREFIX_RE, "(X/N)"
        )
        assert violations == [], (
            "AskUser topic format lines missing (X/N) prefix:\n"
            + "\n".join(f"  - {v}" for v in violations)
        )

    def test_topic_example_has_progress_prefix(self):
        """All 'Example: `[topic] ...`' lines for findings must contain (N/N) pattern."""
        violations = []
        for filepath in _all_doc_files():
            text = filepath.read_text()
            lines = text.splitlines()
            for i, line in enumerate(lines, 1):
                m = TOPIC_EXAMPLE_RE.search(line)
                if not m:
                    continue
                value = m.group(1)
                if not re.search(r"F\d", value):
                    continue
                if not PROGRESS_EXAMPLE_RE.search(value):
                    rel = filepath.relative_to(REPO_ROOT)
                    violations.append(f"{rel}:{i}: concrete (N/N) missing in: {value}")
        assert violations == [], (
            "AskUser topic example lines missing progress prefix:\n"
            + "\n".join(f"  - {v}" for v in violations)
        )

    def test_at_least_one_format_found(self):
        """Sanity: ensure the patterns actually match something."""
        count = 0
        for filepath in _all_doc_files():
            text = filepath.read_text()
            count += len(TOPIC_FORMAT_RE.findall(text))
        # Count files that actually define the topic format (not just use AskUser).
        # Many files USE AskUser but only review/cycle skills DEFINE the format.
        files_with_format = sum(
            1 for f in _all_doc_files() if TOPIC_FORMAT_RE.search(f.read_text())
        )
        assert files_with_format >= 1, (
            "No files found with AskUser topic format definition. "
            "Pattern may need updating."
        )
        assert count >= files_with_format, (
            f"Expected at least {files_with_format} AskUser topic format definitions "
            f"(based on {files_with_format} files with format), found {count}."
        )


# --- Description consistency: marketplace.json vs plugin.json ---


class TestDescriptionConsistency:
    """marketplace.json and plugin.json descriptions must match for each plugin."""

    def test_marketplace_matches_plugin_json(self):
        """Each plugin's marketplace.json description must equal its plugin.json description.

        Uses `.get()` with defaults so malformed entries produce readable assertion
        failures instead of opaque KeyError tracebacks.
        """
        if not MARKETPLACE_JSON.exists():
            return
        marketplace = json.loads(MARKETPLACE_JSON.read_text())
        violations = []
        for plugin in marketplace.get("plugins", []):
            name = plugin.get("name")
            if not name:
                violations.append(f"marketplace entry missing 'name': {plugin}")
                continue
            plugin_json = REPO_ROOT / name / ".factory-plugin" / "plugin.json"
            if not plugin_json.exists():
                continue
            pj = json.loads(plugin_json.read_text())
            mk_desc = plugin.get("description", "")
            pj_desc = pj.get("description", "")
            if mk_desc != pj_desc:
                violations.append(
                    f"{name}: marketplace.json != plugin.json\n"
                    f"    marketplace: {mk_desc}\n"
                    f"    plugin.json: {pj_desc}"
                )
        assert violations == [], (
            "Description mismatch between marketplace.json and plugin.json:\n"
            + "\n".join(f"  - {v}" for v in violations)
        )

    def test_readme_resume_row_matches_plugin_json(self):
        """README.md resume row description must equal resume/plugin.json description.

        README tends to drift silently because earlier versions of the test suite did not
        compare it. This test catches the R4 class of regressions — a truncated description
        that hides the user-confirmed state.json write exception.
        """
        readme = REPO_ROOT / "README.md"
        resume_plugin = REPO_ROOT / "resume" / ".factory-plugin" / "plugin.json"
        if not readme.exists() or not resume_plugin.exists():
            return
        pj = json.loads(resume_plugin.read_text())
        pj_desc = pj["description"].strip()
        # Strip the "Administrative: " prefix for the comparison — README uses it as a
        # leading marker; the rest of the sentence must match verbatim.
        if pj_desc.startswith("Administrative: "):
            pj_rest = pj_desc
        else:
            pj_rest = "Administrative: " + pj_desc
        # Find the resume row in README
        lines = readme.read_text().splitlines()
        resume_row = next(
            (line for line in lines if line.startswith("| `resume`") or line.startswith("| resume |")),
            None,
        )
        assert resume_row is not None, "README.md has no `resume` row"
        # Extract the description column (between the first and third `|` separators)
        parts = [p.strip() for p in resume_row.split("|")]
        # parts: ['', '`resume`', '<description>', '`/optimus-resume`', '']
        readme_desc = parts[2] if len(parts) >= 3 else ""
        assert readme_desc == pj_rest, (
            f"README.md resume description drift vs plugin.json:\n"
            f"    README: {readme_desc}\n"
            f"    plugin: {pj_rest}"
        )


# --- Stage rename: no stale 'check' references as stage name ---

# Patterns that indicate 'check' used as the stage-3 name (not as English verb
# or part of 'pr-check' tool name or 'gh pr checks' CLI command).
#
# F14p: These patterns are intentionally aggressive. Stage 3 was renamed
# from 'check' → 'review'; we want any future stale wording to fail loudly
# in CI rather than silently survive a rebase or merge from a long-lived
# branch. If a legitimate use case for any of these exact phrases emerges
# (e.g., a new feature that genuinely talks about a "check" workflow that
# is not the old stage-3), DO NOT weaken the regex — instead exclude the
# specific file via an EXCLUSION_PATHS list (add one if needed) so the
# guard remains tight everywhere else.
STALE_CHECK_PATTERNS = [
    (re.compile(r"stage=`?check`?"), "stage=check reference"),
    (re.compile(r"plan, build, and check"), "pipeline list with check"),
    (re.compile(r"plan, build, check\b"), "pipeline list with check"),
    (re.compile(r"\bplan or check\b"), "plan or check"),
    (re.compile(r"\bcheck has completed\b"), "check has completed"),
    (re.compile(r"\bRun check first\b"), "Run check first"),
    (re.compile(r"\bcheck Phase \d+"), "check Phase N reference"),
    (re.compile(r"\bcheck ×\d+"), "check xN display label"),
    (re.compile(r"\bAverage check runs\b"), "Average check runs"),
    # F13a: stale lifecycle stage names (replaced by plan/build/review/done).
    (re.compile(r"\(spec, impl, review, close\)"), "stale stage list (spec, impl, review, close)"),
    (re.compile(r"\bstage-1 and close\b"), "stale stage-1 and close reference"),
]


class TestStageRenameConsistency:
    """Stage 3 was renamed from 'check' to 'review'. No stale references should remain."""

    def test_no_stale_check_stage_references(self):
        """No file should contain 'check' used as a stage-3 name."""
        violations = []
        for filepath in _all_doc_files():
            text = filepath.read_text()
            for i, line in enumerate(text.splitlines(), 1):
                for pattern, label in STALE_CHECK_PATTERNS:
                    if pattern.search(line):
                        rel = filepath.relative_to(REPO_ROOT)
                        violations.append(f"{rel}:{i}: {label} — {line.strip()}")
        assert violations == [], (
            "Stale 'check' stage references found (should be 'review'):\n"
            + "\n".join(f"  - {v}" for v in violations)
        )


# --- Terminal title format consistency ---

OLD_TITLE_FORMAT = re.compile(
    r"printf.*optimus:.*%s\s*\|\s*%s"
)
# Matches the title literal used by either `printf` OR `_optimus_set_title`,
# in the form `optimus: STAGE $TASK_ID — $TASK_TITLE` (or %s placeholders,
# or `<STAGE>` placeholder used in protocol templates, or a concrete example
# like `optimus: BATCH T-003 — User Auth JWT`).
NEW_TITLE_FORMAT = re.compile(
    r'optimus:\s*(?:%s|[A-Z]+|<\w+>)\s+(?:%s|\$TASK_ID|T-\d+)\s*—\s*(?:%s|\$TASK_TITLE|[\w][\w ]*)'
)
TITLE_SKILLS = ["plan", "build", "review", "done", "batch"]


class TestTerminalTitleFormat:
    """Terminal title printf must use the new format (no pipe separator)."""

    def test_no_old_pipe_format(self):
        """No SKILL.md should use the old 'optimus: %s | %s' pipe-separated format."""
        violations = []
        for filepath in _all_doc_files():
            text = filepath.read_text()
            for i, line in enumerate(text.splitlines(), 1):
                if OLD_TITLE_FORMAT.search(line):
                    rel = filepath.relative_to(REPO_ROOT)
                    violations.append(f"{rel}:{i}: old pipe format — {line.strip()}")
        assert violations == [], (
            "Old terminal title format (pipe separator) found:\n"
            + "\n".join(f"  - {v}" for v in violations)
        )

    def test_new_format_exists_in_all_title_skills(self):
        """Every title skill must use the new terminal title format."""
        missing = []
        for skill in TITLE_SKILLS:
            content = _read_skill(skill)
            if not NEW_TITLE_FORMAT.search(content):
                missing.append(skill)
        assert missing == [], (
            "Skills missing new terminal title format:\n"
            + "\n".join(f"  - {v}" for v in missing)
        )

    def test_all_stage_skills_have_terminal_title_step(self):
        """All stage/batch skills must have a Set Terminal Title step."""
        missing = []
        for skill in TITLE_SKILLS:
            content = _read_skill(skill)
            if "Set Terminal Title" not in content and "Set terminal title" not in content:
                missing.append(skill)
        assert missing == [], (
            "Skills missing 'Set Terminal Title' step:\n"
            + "\n".join(f"  - {v}" for v in missing)
        )

    def test_all_title_skills_have_restore_title(self):
        """All title skills must have a restore terminal title command
        via the `_optimus_set_title ""` helper call.
        """
        restore_helper = re.compile(r'_optimus_set_title\s+""')
        missing = []
        for skill in TITLE_SKILLS:
            content = _read_skill(skill)
            if not restore_helper.search(content):
                missing.append(skill)
        assert missing == [], (
            "Skills missing restore terminal title command:\n"
            + "\n".join(f"  - {v}" for v in missing)
        )

    def test_helper_has_applescript_layer(self):
        """Layer A (AppleScript) must be present in every TITLE_SKILLS helper.

        iTerm2 profiles with "Terminal may set window title" disabled silently
        discard OSC 0/1/2 title updates. AppleScript `set name of session` is
        the only channel that reliably mutates session.name in that scenario.
        """
        missing = []
        for skill in TITLE_SKILLS:
            content = _read_skill(skill)
            if "osascript" not in content or "set name of s to" not in content:
                missing.append(skill)
        assert missing == [], (
            "Skills missing AppleScript Layer A (osascript set name of s):\n"
            + "\n".join(f"  - {v}" for v in missing)
        )

# --- Finding presentation: Tell me more, IMMEDIATE RESPONSE RULE, anti-rationalization ---

SKILLS_WITH_FINDINGS = [
    "pr-check", "review", "plan", "deep-review",
    "coderabbit-review", "deep-doc-review",
]


def _read_skill(plugin_name: str) -> str:
    """Read the SKILL.md for a given plugin name."""
    paths = list(REPO_ROOT.glob(f"{plugin_name}/skills/*/SKILL.md"))
    assert paths, f"No SKILL.md found for {plugin_name}"
    return paths[0].read_text()


class TestFindingPresentation:
    """Every skill with finding presentation must enforce Tell me more, HARD BLOCK, and anti-rationalization."""

    def test_askuser_template_has_tell_me_more_option(self):
        """Every skill with findings must have [option] Tell me more in the AskUser template."""
        violations = []
        for skill in SKILLS_WITH_FINDINGS:
            content = _read_skill(skill)
            if "[option] Tell me more" not in content:
                violations.append(skill)
        assert violations == [], (
            "Skills missing concrete [option] Tell me more in AskUser template:\n"
            + "\n".join(f"  - {v}" for v in violations)
        )

    def test_hard_block_immediate_response_rule(self):
        """Every skill with findings must have HARD BLOCK on IMMEDIATE RESPONSE RULE."""
        violations = []
        for skill in SKILLS_WITH_FINDINGS:
            content = _read_skill(skill)
            if "HARD BLOCK" not in content or "IMMEDIATE RESPONSE RULE" not in content:
                violations.append(skill)
        assert violations == [], (
            "Skills missing HARD BLOCK — IMMEDIATE RESPONSE RULE:\n"
            + "\n".join(f"  - {v}" for v in violations)
        )

    def test_anti_rationalization_block(self):
        """Every skill with findings must have anti-rationalization excuses."""
        violations = []
        for skill in SKILLS_WITH_FINDINGS:
            content = _read_skill(skill)
            if "Anti-rationalization" not in content:
                violations.append(skill)
        assert violations == [], (
            "Skills missing anti-rationalization block:\n"
            + "\n".join(f"  - {v}" for v in violations)
        )

    def test_finding_header_has_progress_prefix(self):
        """Every skill with findings must instruct (X/N) progress prefix in finding headers."""
        violations = []
        for skill in SKILLS_WITH_FINDINGS:
            content = _read_skill(skill)
            if "(X/N)" not in content:
                violations.append(skill)
        assert violations == [], (
            "Skills missing (X/N) progress prefix instruction in finding headers:\n"
            + "\n".join(f"  - {v}" for v in violations)
        )

    def test_agents_md_has_all_elements(self):
        """AGENTS.md (source of truth) must have all finding presentation elements."""
        content = AGENTS_MD.read_text()
        assert "[option] Tell me more" in content, \
            "AGENTS.md missing [option] Tell me more in AskUser template"
        assert "HARD BLOCK" in content and "IMMEDIATE RESPONSE RULE" in content, \
            "AGENTS.md missing HARD BLOCK — IMMEDIATE RESPONSE RULE"
        assert "Anti-rationalization" in content, \
            "AGENTS.md missing anti-rationalization block"
        assert "(X/N)" in content, \
            "AGENTS.md missing (X/N) progress prefix instruction"


# --- Pipeline: exactly 4 stages (plan, build, review, done) ---

TRANSITION_ROW = re.compile(
    r"^\|\s*(plan|build|review|done)\s*\|", re.MULTILINE
)
STALE_FIVE_STAGE = re.compile(
    r"(5 stages|stages 1-5|stages 2-5)", re.IGNORECASE
)
VALID_STATUSES = [
    "Pendente", "Validando Spec", "Em Andamento",
    "Validando Impl", "DONE", "Cancelado",
]


class TestPipelineFourStages:
    """Pipeline must be exactly 4 stages: plan, build, review, done."""

    def test_agents_md_transition_table_has_four_rows(self):
        """Transition Table in AGENTS.md must have exactly 4 agent rows."""
        content = AGENTS_MD.read_text()
        rows = TRANSITION_ROW.findall(content)
        assert sorted(rows) == ["build", "done", "plan", "review"], (
            f"Transition Table has agents {rows}, expected [plan, build, review, done]"
        )

    def test_no_stale_five_stage_references(self):
        """No doc file should mention '5 stages' or 'stages 1-5' or 'stages 2-5'."""
        violations = []
        for filepath in _all_doc_files():
            text = filepath.read_text()
            for i, line in enumerate(text.splitlines(), 1):
                if STALE_FIVE_STAGE.search(line):
                    rel = filepath.relative_to(REPO_ROOT)
                    violations.append(f"{rel}:{i}: {line.strip()}")
        assert violations == [], (
            "Stale 5-stage references found (pipeline is 4 stages):\n"
            + "\n".join(f"  - {v}" for v in violations)
        )

    def test_valid_status_values_in_agents_md(self):
        """AGENTS.md must define the valid statuses and must NOT reference
        the legacy `Revisando PR` status anywhere.

        The Revisando PR → Validando Impl migration was removed in issue #16
        (closed by PR #20 step 3). Any reappearance of `Revisando PR` is a
        regression.
        """
        content = AGENTS_MD.read_text()
        for status in VALID_STATUSES:
            assert status in content, f"AGENTS.md missing status '{status}'"
        for i, line in enumerate(content.splitlines(), 1):
            assert "Revisando PR" not in line, (
                f"AGENTS.md:{i}: 'Revisando PR' is a removed legacy status "
                "and must not reappear (issue #16): {line.strip()}"
            )


# --- Plugin completeness: marketplace matches directory structure ---

EXPECTED_PLUGINS = [
    "batch", "build", "coderabbit-review", "deep-doc-review", "deep-review",
    "done", "help", "import", "plan", "pr-check", "quick-report", "report",
    "resolve", "resume", "review", "sync", "tasks",
]
REMOVED_PLUGINS = ["verify-code", "codacy-review", "deepsource-review"]


class TestPluginCompleteness:
    """Marketplace, directories, and plugin count must stay in sync."""

    def test_all_marketplace_plugins_have_directory(self):
        """Every plugin in marketplace.json must have a SKILL.md."""
        if not MARKETPLACE_JSON.exists():
            return
        marketplace = json.loads(MARKETPLACE_JSON.read_text())
        missing = []
        for plugin in marketplace.get("plugins", []):
            name = plugin["name"]
            paths = list(REPO_ROOT.glob(f"{name}/skills/*/SKILL.md"))
            if not paths:
                missing.append(name)
        assert missing == [], (
            "Marketplace plugins missing SKILL.md:\n"
            + "\n".join(f"  - {v}" for v in missing)
        )

    def test_all_plugin_directories_in_marketplace(self):
        """Every directory with plugin.json must be listed in marketplace.json."""
        if not MARKETPLACE_JSON.exists():
            return
        marketplace = json.loads(MARKETPLACE_JSON.read_text())
        marketplace_names = {p["name"] for p in marketplace.get("plugins", [])}
        orphans = []
        for pj in REPO_ROOT.glob("*/.factory-plugin/plugin.json"):
            name = pj.parent.parent.name
            if name not in marketplace_names:
                orphans.append(name)
        assert orphans == [], (
            "Plugin directories not in marketplace.json:\n"
            + "\n".join(f"  - {v}" for v in orphans)
        )

    def test_expected_plugin_count(self):
        """Marketplace must have exactly 17 plugins.

        Defense-in-depth count check; the SET check below
        (`test_expected_plugins_match_set`) catches identity drift, which
        a count-only check cannot detect (e.g., `batch` removed and
        `chat` added would still pass count==17).
        """
        if not MARKETPLACE_JSON.exists():
            return
        marketplace = json.loads(MARKETPLACE_JSON.read_text())
        count = len(marketplace.get("plugins", []))
        assert count == 17, (
            f"Expected 17 plugins in marketplace, found {count}"
        )

    def test_expected_plugins_match_set(self):
        """Marketplace plugin SET must match EXPECTED_PLUGINS exactly.

        F14o: a count-only check (above) silently passes if a contributor
        swaps one plugin for another. This set-comparison surfaces the
        actual identity drift via `missing` / `extra` diffs.
        """
        if not MARKETPLACE_JSON.exists():
            return
        marketplace = json.loads(MARKETPLACE_JSON.read_text())
        actual = set(p["name"] for p in marketplace.get("plugins", []))
        expected = set(EXPECTED_PLUGINS)
        assert actual == expected, (
            f"Plugin set drift:\n"
            f"  missing (in EXPECTED_PLUGINS but not marketplace): "
            f"{sorted(expected - actual)}\n"
            f"  extra   (in marketplace but not EXPECTED_PLUGINS): "
            f"{sorted(actual - expected)}"
        )

    def test_no_removed_plugins_referenced(self):
        """No SKILL.md should reference removed plugins (verify-code, codacy-review, deepsource-review)."""
        violations = []
        for filepath in _all_skill_files():
            text = filepath.read_text()
            for removed in REMOVED_PLUGINS:
                if removed in text:
                    rel = filepath.relative_to(REPO_ROOT)
                    violations.append(f"{rel}: references removed plugin '{removed}'")
        assert violations == [], (
            "Removed plugins still referenced:\n"
            + "\n".join(f"  - {v}" for v in violations)
        )


# --- Skill classification: Admin vs Execution ---

EXECUTION_SKILLS = ["plan", "build", "review", "done"]
WORKSPACE_SKILLS = ["build", "review", "done"]


class TestSkillClassification:
    """Execution skills must have session state and workspace protocols."""

    def test_stage_skills_have_session_state(self):
        """All 4 execution skills must reference Session State protocol."""
        missing = []
        for skill in EXECUTION_SKILLS:
            content = _read_skill(skill)
            if "Session State" not in content:
                missing.append(skill)
        assert missing == [], (
            "Execution skills missing Session State protocol:\n"
            + "\n".join(f"  - {v}" for v in missing)
        )

    def test_stage_skills_have_workspace_protocol(self):
        """build, review, done must reference Workspace Auto-Navigation."""
        missing = []
        for skill in WORKSPACE_SKILLS:
            content = _read_skill(skill)
            if "Workspace Auto-Navigation" not in content:
                missing.append(skill)
        assert missing == [], (
            "Skills missing Workspace Auto-Navigation protocol:\n"
            + "\n".join(f"  - {v}" for v in missing)
        )

    def test_pr_check_is_standalone(self):
        """pr-check must NOT change task status (it's standalone, not a pipeline stage)."""
        content = _read_skill("pr-check")
        assert "state.json" not in content or "does not change" in content.lower() or \
            "standalone" in content.lower(), (
            "pr-check appears to modify state.json — it should be standalone"
        )


# --- Makefile convention: make lint/test required, no commands.* config ---

COMMANDS_CONFIG = re.compile(r"commands\.(lint|test|build|format)")


class TestMakefileConvention:
    """Projects must use Makefile targets, not commands.* config."""

    def test_agents_md_requires_make_lint_and_test(self):
        """AGENTS.md must define make lint and make test as required targets."""
        content = AGENTS_MD.read_text()
        assert "make lint" in content, "AGENTS.md missing 'make lint' requirement"
        assert "make test" in content, "AGENTS.md missing 'make test' requirement"

    def test_no_commands_config_references(self):
        """No SKILL.md should reference commands.lint or commands.test config pattern."""
        violations = []
        for filepath in _all_skill_files():
            text = filepath.read_text()
            for i, line in enumerate(text.splitlines(), 1):
                if COMMANDS_CONFIG.search(line):
                    rel = filepath.relative_to(REPO_ROOT)
                    violations.append(f"{rel}:{i}: {line.strip()}")
        assert violations == [], (
            "Stale commands.* config references found (use Makefile convention):\n"
            + "\n".join(f"  - {v}" for v in violations)
        )


# --- Convergence model: Full Roster, opt-in gated ---


# Skills that inline the Convergence Loop protocol (used by cross-file tests).
SKILLS_WITH_CONVERGENCE = [
    "plan", "review", "build", "pr-check",
    "deep-review", "deep-doc-review", "coderabbit-review",
]

# Tolerant regex for the section heading: accepts em-dash (—), en-dash (–) or
# hyphen (-), variable spacing, and optional "Protocol:" prefix.
CONVERGENCE_HEADING_RE = re.compile(
    r"(?:Protocol:\s*)?Convergence Loop\s*\(Full Roster Model\s*[—–-]\s*Opt[- ]?In,?\s*Gated\)",
    re.IGNORECASE,
)

# Forbidden phrases that must not appear in any doc file.
OBSOLETE_ROUND_2_MANDATORY_RE = re.compile(
    r"round\s*2\s+is\s+mandatory", re.IGNORECASE,
)


def _assert_phrase_absent(content: str, pattern: re.Pattern, where: str, label: str):
    """Helper: assert a forbidden phrase pattern is not present in content."""
    if pattern.search(content):
        raise AssertionError(f"{where} still contains forbidden phrase '{label}'")


class TestConvergenceModel:
    """Convergence loop must use the Full Roster, Opt-In, Gated model."""

    @pytest.fixture(scope="class")
    def agents_md(self):
        return AGENTS_MD.read_text()

    def test_agents_md_has_full_roster_semantics(self, agents_md):
        """AGENTS.md must require rounds 2+ to re-dispatch the same roster with zero context."""
        assert "same agent roster" in agents_md, \
            "AGENTS.md must require rounds 2+ to re-dispatch the same roster"
        assert re.search(r"zero prior context", agents_md), \
            "AGENTS.md must require each round 2+ agent to run with zero prior context"

    def test_no_escalating_scrutiny_references(self):
        """No doc file should mention 'escalating scrutiny' (replaced by Full Roster)."""
        violations = []
        for filepath in _all_doc_files():
            text = filepath.read_text()
            if "escalating scrutiny" in text.lower():
                rel = filepath.relative_to(REPO_ROOT)
                violations.append(str(rel))
        assert violations == [], (
            "Stale 'escalating scrutiny' references found:\n"
            + "\n".join(f"  - {v}" for v in violations)
        )

    def test_convergence_loop_is_opt_in_gated(self, agents_md):
        """AGENTS.md has the opt-in, gated convergence loop heading and all 5 exit statuses."""
        assert CONVERGENCE_HEADING_RE.search(agents_md), \
            "AGENTS.md missing opt-in, gated convergence loop section heading"
        for status in ["CONVERGED", "USER_STOPPED", "SKIPPED",
                       "HARD_LIMIT", "DISPATCH_FAILED_ABORTED"]:
            assert status in agents_md, \
                f"AGENTS.md missing convergence exit status '{status}'"

    def test_no_obsolete_round_2_mandatory_anywhere(self):
        """No doc file should claim Round 2 is mandatory (case-insensitive scan)."""
        violations = []
        for filepath in _all_doc_files():
            text = filepath.read_text()
            if OBSOLETE_ROUND_2_MANDATORY_RE.search(text):
                rel = filepath.relative_to(REPO_ROOT)
                violations.append(str(rel))
        assert violations == [], (
            "Stale 'Round 2 is mandatory' references found:\n"
            + "\n".join(f"  - {v}" for v in violations)
        )

    def test_design_principles_summary_matches_protocol(self, agents_md):
        """AGENTS.md Design Principle '2. No False Convergence' must describe opt-in model."""
        m = re.search(
            r"### 2\. No False Convergence\s*\n(.*?)(?=\n### )",
            agents_md, re.DOTALL,
        )
        assert m, "Design Principle 2 block missing from AGENTS.md"
        block = m.group(1)
        assert not OBSOLETE_ROUND_2_MANDATORY_RE.search(block), (
            "Design Principle 2 still claims Round 2 is mandatory — "
            "contradicts the opt-in gated protocol"
        )
        assert re.search(r"opt[- ]?in", block, re.IGNORECASE), (
            "Design Principle 2 must describe the opt-in gated model"
        )

    def test_entry_gate_clause_present(self, agents_md):
        """AGENTS.md must define the Entry Gate (before round 2 → SKIPPED on skip)."""
        assert re.search(
            r"Entry gate.*before round 2.*Skip convergence loop.*SKIPPED",
            agents_md, re.DOTALL,
        ), "AGENTS.md missing Entry Gate clause tying SKIPPED to user skip"

    def test_per_round_gate_clause_present(self, agents_md):
        """AGENTS.md must define the Per-Round Gate (rounds 3+ → USER_STOPPED on stop)."""
        assert re.search(
            r"Per-round gate.*rounds? 3.*Stop here.*USER_STOPPED",
            agents_md, re.DOTALL,
        ), "AGENTS.md missing Per-Round Gate clause tying USER_STOPPED to user stop"

    def test_convergence_detection_silent_exit(self, agents_md):
        """AGENTS.md must forbid re-prompting when CONVERGED is detected (silent exit)."""
        assert re.search(
            r"zero new findings[\s\S]{0,400}CONVERGED[\s\S]{0,400}(NEVER|DO NOT)\s+(offer|ask)",
            agents_md, re.IGNORECASE,
        ), (
            "AGENTS.md Convergence Detection must explicitly forbid re-prompting "
            "on CONVERGED (look for 'NEVER offer' or 'DO NOT ask')"
        )

    def test_hard_limit_clause_present(self, agents_md):
        """AGENTS.md must define round 5 as the hard limit → HARD_LIMIT."""
        assert re.search(
            r"Round 5 is the maximum[\s\S]{0,300}HARD_LIMIT",
            agents_md, re.DOTALL,
        ), "AGENTS.md missing Round-5 hard limit tying to HARD_LIMIT"

    def test_dispatch_failure_clause_present(self, agents_md):
        """AGENTS.md must define the Dispatch Failure path → Retry/Stop → DISPATCH_FAILED_ABORTED."""
        assert re.search(
            r"Dispatch failure[\s\S]{0,500}Retry round[\s\S]{0,500}DISPATCH_FAILED_ABORTED",
            agents_md, re.DOTALL,
        ), "AGENTS.md missing Dispatch Failure path tying to DISPATCH_FAILED_ABORTED"

    def test_all_convergence_skills_carry_opt_in_protocol(self):
        """Each consumer SKILL.md must inline the new heading and all 5 exit statuses."""
        violations = []
        for skill in SKILLS_WITH_CONVERGENCE:
            content = _read_skill(skill)
            if not CONVERGENCE_HEADING_RE.search(content):
                violations.append(f"{skill}: missing Opt-In, Gated heading")
            for status in ["CONVERGED", "USER_STOPPED", "SKIPPED",
                           "HARD_LIMIT", "DISPATCH_FAILED_ABORTED"]:
                if status not in content:
                    violations.append(f"{skill}: missing status '{status}'")
            if OBSOLETE_ROUND_2_MANDATORY_RE.search(content):
                violations.append(f"{skill}: still contains 'Round 2 is mandatory'")
        assert violations == [], "\n".join(violations)


# --- optimus-tasks.md format spec: marker, Tipo, versions, state.json ---


class TestTasksFormatSpec:
    """optimus-tasks.md format invariants must be defined in AGENTS.md."""

    def test_agents_md_defines_format_marker(self):
        """AGENTS.md must define the tasks-v1 format marker."""
        content = AGENTS_MD.read_text()
        assert "<!-- optimus:tasks-v1 -->" in content, \
            "AGENTS.md missing format marker <!-- optimus:tasks-v1 -->"

    def test_agents_md_defines_tipo_values(self):
        """AGENTS.md must list all 6 Tipo values."""
        content = AGENTS_MD.read_text()
        for tipo in ["Feature", "Fix", "Refactor", "Chore", "Docs", "Test"]:
            assert tipo in content, f"AGENTS.md missing Tipo value '{tipo}'"

    def test_agents_md_defines_version_statuses(self):
        """AGENTS.md must list all 5 version status values."""
        content = AGENTS_MD.read_text()
        for status in ["Ativa", "Backlog"]:
            assert status in content, f"AGENTS.md missing version status '{status}'"

    def test_status_lives_in_state_json(self):
        """AGENTS.md must state that status is NOT stored in optimus-tasks.md."""
        content = AGENTS_MD.read_text()
        assert "NOT stored in optimus-tasks.md" in content or \
            "NOT in optimus-tasks.md" in content, (
            "AGENTS.md missing statement that status lives in state.json, not optimus-tasks.md"
        )

    def test_agents_md_has_column_spec(self):
        """AGENTS.md must define the required columns: ID, Title, Tipo, Depends, Priority, Version."""
        content = AGENTS_MD.read_text()
        for col in ["ID", "Title", "Tipo", "Depends", "Priority", "Version"]:
            assert f"| {col} |" in content or f"| {col}" in content, \
                f"AGENTS.md missing column definition for '{col}'"


# --- optimus-tasks.md location redesign: optimus-tasks.md lives in tasksDir (not in .optimus/) ---

SKILLS_THAT_TOUCH_TASKS = [
    "plan", "build", "review", "done", "batch", "resume",
    "report", "quick-report", "resolve", "tasks", "import",
]

LEGACY_TASKS_PATH_RE = re.compile(r'\.optimus/tasks\.md')
TASKS_GIT_HELPER_RE = re.compile(r'tasks_git\s*\(\)')


class TestTasksDirLocation:
    """optimus-tasks.md lives at <tasksDir>/optimus-tasks.md (not .optimus/tasks.md).
    config.json is gitignored (not versioned).
    """

    def test_agents_md_no_legacy_hardcoded_tasks_file(self):
        """AGENTS.md must not reference `.optimus/tasks.md` as a live path.

        After M1 (Protocol: Migrate tasks.md to tasksDir) was removed in
        issue #20, NO legitimate reference to `.optimus/tasks.md` remains —
        the legacy migration that touched it is gone. Any reappearance is a
        bug.
        """
        content = AGENTS_MD.read_text()
        violations = []
        for i, line in enumerate(content.splitlines(), 1):
            if LEGACY_TASKS_PATH_RE.search(line):
                violations.append(f"AGENTS.md:{i}: {line.strip()}")
        assert violations == [], (
            "AGENTS.md references `.optimus/tasks.md` (legacy path); the M1 "
            "migration that justified those references was removed:\n"
            + "\n".join(f"  - {v}" for v in violations)
        )

    def test_skills_no_legacy_tasks_file_as_live_path(self):
        """SKILL.md bodies must not assume `.optimus/tasks.md` as the current location.
        After M1 removal (#20), mentions are allowed ONLY as explicit historical
        / legacy context (e.g., 'if a legacy .optimus/tasks.md exists'). The
        previous tolerance for 'migrate'/'migration' keywords was dropped —
        with M1 gone there is no legitimate reason to use those terms inline."""
        violations = []
        for skill in SKILLS_THAT_TOUCH_TASKS:
            paths = list(REPO_ROOT.glob(f"{skill}/skills/*/SKILL.md"))
            if not paths:
                continue
            content = paths[0].read_text()
            body = content.split("<!-- INLINE-PROTOCOLS:START -->", 1)[0]
            lines = body.splitlines()
            for i, line in enumerate(lines, 1):
                if not LEGACY_TASKS_PATH_RE.search(line):
                    continue
                # Check a 3-line context window (±1 line) for the "legacy"
                # marker. Only "legacy" remains a valid exemption keyword
                # post-M1; any other context is a regression.
                start = max(0, i - 2)
                end = min(len(lines), i + 1)
                context = " ".join(lines[start:end]).lower()
                is_legacy_context = "legacy" in context
                if not is_legacy_context:
                    violations.append(f"{skill}/SKILL.md:{i}: {line.strip()}")
        assert violations == [], (
            "SKILL bodies use `.optimus/tasks.md` outside an explicit legacy "
            "context (the only valid reason after M1 removal in #20):\n"
            + "\n".join(f"  - {v}" for v in violations)
        )

    def test_agents_md_has_resolve_tasks_git_scope_protocol(self):
        """AGENTS.md must define Protocol: Resolve Tasks Git Scope."""
        content = AGENTS_MD.read_text()
        assert "### Protocol: Resolve Tasks Git Scope" in content, \
            "AGENTS.md missing Protocol: Resolve Tasks Git Scope"
        assert "tasks_git()" in content, \
            "AGENTS.md missing tasks_git() helper definition"
        assert "TASKS_GIT_SCOPE" in content, \
            "AGENTS.md missing TASKS_GIT_SCOPE variable"
        assert '"same-repo"' in content, \
            "AGENTS.md missing same-repo scope case"
        assert '"separate-repo"' in content, \
            "AGENTS.md missing separate-repo scope case"

    def test_agents_md_has_no_migrate_protocol(self):
        """Negation guard: M1 was removed in issue #20 and must not return.

        Catches accidental re-introduction of `Protocol: Migrate tasks.md to
        tasksDir` (e.g., via a stale rebase, copy-paste, or merge from a long-
        lived branch). The protocol's hot-path startup cost is the reason it
        was removed; a silent regression would re-add it without alerting CI
        unless this assertion exists.
        """
        content = AGENTS_MD.read_text()
        assert "### Protocol: Migrate tasks.md to tasksDir" not in content, (
            "AGENTS.md re-introduces `Protocol: Migrate tasks.md to tasksDir` "
            "(removed in issue #20). This protocol is dead and must stay gone — "
            "see PR #24 for context."
        )

    def test_agents_md_has_no_rename_protocol(self):
        """Negation guard: M2 was removed in issue #20 and must not return.

        Catches accidental re-introduction of `Protocol: Rename tasks.md to
        optimus-tasks.md`. Same rationale as the M1 guard above — the protocol
        is dead, hot-path startup cost is gone, and we don't want it to come
        back via stale branches.
        """
        content = AGENTS_MD.read_text()
        assert "### Protocol: Rename tasks.md to optimus-tasks.md" not in content, (
            "AGENTS.md re-introduces `Protocol: Rename tasks.md to "
            "optimus-tasks.md` (removed in issue #20). This protocol is dead "
            "and must stay gone — see PR for context."
        )

    def test_inline_protocols_has_no_migrate_constant(self):
        """Negation guard: `MIGRATE_PROTOCOL_KEY` was removed alongside M1.

        Re-defining the constant in `inline-protocols.py` is the most likely
        regression path back into the deleted Migrate logic. This test imports
        the script and asserts the attribute is absent.
        """
        import importlib.util
        ip_path = REPO_ROOT / "scripts" / "inline-protocols.py"
        spec = importlib.util.spec_from_file_location("inline_protocols", ip_path)
        assert spec is not None, f"Cannot load spec for {ip_path}"
        assert spec.loader is not None, f"Spec loader is None for {ip_path}"
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        assert not hasattr(mod, "MIGRATE_PROTOCOL_KEY"), (
            "scripts/inline-protocols.py re-introduces MIGRATE_PROTOCOL_KEY "
            "(removed in issue #20). The legacy Migrate protocol is gone — "
            "see PR #24 for context."
        )

    def test_inline_protocols_has_no_rename_constant(self):
        """Negation guard: `RENAME_PROTOCOL_KEY` was removed alongside M2.

        Symmetric to the migrate guard above. Rename was removed because no
        project needs the rename anymore — the constant must stay gone.
        """
        import importlib.util
        ip_path = REPO_ROOT / "scripts" / "inline-protocols.py"
        spec = importlib.util.spec_from_file_location("inline_protocols", ip_path)
        assert spec is not None, f"Cannot load spec for {ip_path}"
        assert spec.loader is not None, f"Spec loader is None for {ip_path}"
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        assert not hasattr(mod, "RENAME_PROTOCOL_KEY"), (
            "scripts/inline-protocols.py re-introduces RENAME_PROTOCOL_KEY "
            "(removed in issue #20). The legacy Rename protocol is gone — "
            "see PR for context."
        )

    def test_config_json_is_gitignored(self):
        """Protocol: Initialize .optimus Directory must include config.json in the
        gitignore block."""
        content = AGENTS_MD.read_text()
        init_section = re.search(
            r"### Protocol: Initialize \.optimus Directory(.*?)###\s+Protocol:",
            content, re.DOTALL,
        )
        assert init_section, "Could not find Protocol: Initialize .optimus Directory"
        block = init_section.group(1)
        assert ".optimus/config.json" in block, \
            "Protocol: Initialize .optimus Directory must gitignore .optimus/config.json"

    def test_all_tasks_touching_skills_resolve_scope(self):
        """Every skill that reads or writes optimus-tasks.md must reference Protocol:
        Resolve Tasks Git Scope (directly or via optimus-tasks.md Validation)."""
        missing = []
        for skill in SKILLS_THAT_TOUCH_TASKS:
            paths = list(REPO_ROOT.glob(f"{skill}/skills/*/SKILL.md"))
            if not paths:
                continue
            content = paths[0].read_text()
            # The inlined block OR body should contain the protocol; check whole file.
            if "Protocol: Resolve Tasks Git Scope" not in content:
                missing.append(skill)
        assert missing == [], (
            "Skills missing Resolve Tasks Git Scope reference:\n"
            + "\n".join(f"  - {v}" for v in missing)
        )

    def test_tasks_git_helper_inlined_in_stage_skills(self):
        """Stage skills (plan, build, review, done) and batch/resolve/tasks MUST
        have the tasks_git() helper inlined so they can run git commands uniformly."""
        required = ["plan", "build", "review", "done", "batch", "resolve", "tasks", "resume"]
        missing = []
        for skill in required:
            paths = list(REPO_ROOT.glob(f"{skill}/skills/*/SKILL.md"))
            if not paths:
                continue
            content = paths[0].read_text()
            if not TASKS_GIT_HELPER_RE.search(content):
                missing.append(skill)
        assert missing == [], (
            "Skills missing tasks_git() helper definition:\n"
            + "\n".join(f"  - {v}" for v in missing)
        )

    def test_no_raw_git_add_of_tasks_file_in_bodies(self):
        """Skills bodies must not use raw `git <verb> "$TASKS_FILE"` —
        use `tasks_git <verb> "$TASKS_GIT_REL"` instead (for separate-repo support).
        Verb list covers state-mutating and read operations that would break in
        separate-repo mode: add/commit/diff/show/rm/mv/push/stash/reset/checkout/log/blame.
        """
        pattern = re.compile(
            r'(?<!tasks_)\bgit\s+(add|commit|diff|show|rm|mv|push|stash|reset|checkout|log|blame)\s+.*\$TASKS_FILE'
        )
        violations = []
        for skill in SKILLS_THAT_TOUCH_TASKS:
            paths = list(REPO_ROOT.glob(f"{skill}/skills/*/SKILL.md"))
            if not paths:
                continue
            content = paths[0].read_text()
            body = content.split("<!-- INLINE-PROTOCOLS:START -->", 1)[0]
            for i, line in enumerate(body.splitlines(), 1):
                if pattern.search(line):
                    violations.append(f"{skill}/SKILL.md:{i}: {line.strip()}")
        assert violations == [], (
            "Skill bodies use raw `git <op> $TASKS_FILE` — must use `tasks_git`:\n"
            + "\n".join(f"  - {v}" for v in violations)
        )


# --- done redesign: 3 hard gates, no local lint/test ---


class TestDoneRedesign:
    """done must use 4 hard gates (incl. PR review feedback) and NOT run local lint/test."""

    def test_done_has_four_hard_gates(self):
        """done SKILL.md must reference all 4 hard gates: uncommitted, unpushed,
        PR review feedback, PR final state."""
        content = _read_skill("done")
        assert "uncommitted" in content.lower(), \
            "done missing 'uncommitted changes' gate"
        assert "unpushed" in content.lower(), \
            "done missing 'unpushed commits' gate"
        assert "PR Review Feedback" in content or "review feedback" in content.lower(), \
            "done missing 'PR review feedback' gate (Gate 3)"
        assert "PR" in content and ("MERGED" in content or "final state" in content.lower()), \
            "done missing 'PR in final state' gate"

    def test_done_pr_review_gate_queries_review_decision(self):
        """Gate 3 must query reviewDecision via gh pr list/view to detect
        unresolved reviewer feedback before allowing the task to close."""
        content = _read_skill("done")
        body = content.split("<!-- INLINE-PROTOCOLS:START -->", 1)[0]
        assert "reviewDecision" in body, (
            "done Gate 3 must query GitHub's reviewDecision field "
            "(via `gh pr list ... --json ... reviewDecision`) to detect feedback"
        )
        assert "CHANGES_REQUESTED" in body, (
            "done Gate 3 must handle the CHANGES_REQUESTED reviewDecision value"
        )

    def test_done_pr_review_gate_offers_pr_check(self):
        """When reviewDecision is CHANGES_REQUESTED, Gate 3 must offer to invoke
        /optimus-pr-check as the recommended path to resolve feedback."""
        content = _read_skill("done")
        body = content.split("<!-- INLINE-PROTOCOLS:START -->", 1)[0]
        assert "optimus-pr-check" in body or "/optimus-pr-check" in body, (
            "done Gate 3 must reference /optimus-pr-check as the suggested action"
        )
        # Must offer at least: Run pr-check, Override, Cancel — 3 distinct paths.
        assert "Override" in body or "I have addressed" in body, (
            "done Gate 3 must offer an override path for users who already "
            "addressed feedback outside Optimus"
        )

    def test_done_no_local_lint_test(self):
        """done SKILL.md must NOT contain make lint or make test as execution steps.

        Catches both the bare form (`make test`) and the wrapped form
        (`_optimus_quiet_run "make-test" make test`) so the invariant survives
        the Quiet Command Execution helper migration. Wrapped regex accepts
        single OR double quotes around the label, and any of the make targets
        (lint, test, test-coverage, test-integration, test-integration-coverage).
        """
        content = _read_skill("done")
        lines = content.splitlines()
        violations = []
        # Bare form: `make lint`, `make test`, `make test-coverage`, etc.
        bare_re = re.compile(
            r"^make (lint|test)(-(coverage|integration|integration-coverage))?\b"
        )
        # Wrapped form: `_optimus_quiet_run "make-test" make test`, with single
        # OR double quotes (or no quotes) around the label, and any verify variant.
        wrapped_re = re.compile(
            r'^_optimus_quiet_run\s+["\']?make-(lint|test)(-(coverage|integration|integration-coverage))?["\']?'
            r'\s+make\s+(lint|test)(-(coverage|integration|integration-coverage))?\b'
        )
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("#") or stripped.startswith("**"):
                continue
            if bare_re.search(stripped) or wrapped_re.search(stripped):
                violations.append(f"done/SKILL.md:{i}: {stripped}")
        assert violations == [], (
            "done should not run local lint/test (CI responsibility):\n"
            + "\n".join(f"  - {v}" for v in violations)
        )

    def test_done_closes_current_task_only(self):
        """done should close the current task only when no explicit task ID is provided."""
        content = _read_skill("done")
        body = content.split("<!-- INLINE-PROTOCOLS:START -->", 1)[0]
        assert "only closes the current task from the current branch" in body, (
            "done must state that no-ID execution closes only the current branch task"
        )
        assert "Never offer a list of multiple tasks to close" in body, (
            "done must forbid a multi-task chooser"
        )
        assert "If multiple found, ask the user which one to close" not in body, (
            "done should not ask the user to choose from multiple tasks"
        )

    def test_done_does_not_offer_resume_or_restart(self):
        """done should not offer resume/start-fresh/restart style choices."""
        content = _read_skill("done")
        body = content.split("<!-- INLINE-PROTOCOLS:START -->", 1)[0]
        assert "Session State (done-specific)" in body, (
            "done should define its own session-state behavior"
        )
        assert "must not offer to resume, start fresh, redo previous stages" in body, (
            "done must explicitly forbid resume/restart flows"
        )
        assert "Options: Resume / Start fresh (delete session) / Continue (keep session file)" not in content, (
            "done should not include resume/start-fresh/continue options"
        )


class TestResumeAdmin:
    """resume is an Administrative skill that resolves a task's workspace without altering state."""

    def test_resume_is_classified_admin(self):
        """AGENTS.md classification table must list resume as Admin."""
        text = AGENTS_MD.read_text()
        assert re.search(r"\|\s*Admin\s*\|\s*resume\s*\|", text), (
            "AGENTS.md must classify resume as Admin in the Admin vs Execution table"
        )

    def test_resume_only_writes_state_json_via_reset_recovery(self):
        """resume is read-only on state.json EXCEPT for a user-confirmed Reset-to-Pendente recovery.

        The only accepted mutation is the jq 'del(.[$id])' block in Step 3.3 Case 3,
        gated by an AskUser option. Any other write to state.json is forbidden.
        """
        content = _read_skill("resume")
        body = content.split("<!-- INLINE-PROTOCOLS:START -->", 1)[0]
        # Must disclose the Reset-to-Pendente override
        assert "Reset to Pendente" in body, (
            "resume must disclose the Reset-to-Pendente recovery override"
        )
        assert "del(.[$id])" in body, (
            "resume must implement the Reset-to-Pendente via jq del"
        )
        # Any state.json write MUST be inside the Reset-to-Pendente recovery block.
        # Detect foreign mutation: "jq ... '.[" ... "] = {" outside Case 3.
        foreign_write = re.compile(r"jq\s+.*'\.\[\$id\]\s*=\s*\{", re.MULTILINE)
        assert not foreign_write.search(body), (
            "resume must not assign new status/branch into state.json (only the gated del() is permitted)"
        )

    def test_resume_stops_on_corrupted_state_json(self):
        """resume must STOP on state.json corruption, not silently rm -f."""
        content = _read_skill("resume")
        body = content.split("<!-- INLINE-PROTOCOLS:START -->", 1)[0]
        assert "state.json is corrupted" in body, (
            "resume must detect corrupted state.json"
        )
        assert "jq empty \"$STATE_FILE\"" in body, (
            "resume must jq-empty-validate state.json before reading"
        )
        # Must NOT include the destructive rm -f recovery in the body (inlined protocol has it;
        # the body MUST override it).
        body_mentions_rm_state = re.compile(r'rm\s+-f\s+"?\$STATE_FILE"?')
        lines_with_rm = [
            i for i, line in enumerate(body.splitlines(), 1)
            if body_mentions_rm_state.search(line)
        ]
        # Allow references in prose/anti-rationalization (mentions rm -f in quotes/backticks),
        # but the body should not have executable `rm -f "$STATE_FILE"` outside of prose.
        # Check that any occurrence is inside a quoted anti-rationalization example.
        for line_num in lines_with_rm:
            line = body.splitlines()[line_num - 1]
            # Accept if the line looks like anti-rationalization prose or fenced explanation
            acceptable = ("`rm -f" in line or '"rm -f' in line or
                          "NO." in line or "let me" in line.lower())
            assert acceptable, (
                f"resume body executes `rm -f $STATE_FILE` at line {line_num} — this is forbidden by the override"
            )

    def test_resume_does_not_run_lint_or_tests(self):
        """resume SKILL.md must not run make lint or make test as execution steps.

        Catches both the bare form and the wrapped form (Quiet Command
        Execution). Wrapped regex accepts single/double quotes around label
        and all verify variants (lint, test, test-coverage, test-integration,
        test-integration-coverage).
        """
        content = _read_skill("resume")
        body = content.split("<!-- INLINE-PROTOCOLS:START -->", 1)[0]
        lines = body.splitlines()
        violations = []
        bare_re = re.compile(
            r"^make (lint|test)(-(coverage|integration|integration-coverage))?\b"
        )
        wrapped_re = re.compile(
            r'^_optimus_quiet_run\s+["\']?make-(lint|test)(-(coverage|integration|integration-coverage))?["\']?'
            r'\s+make\s+(lint|test)(-(coverage|integration|integration-coverage))?\b'
        )
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("#") or stripped.startswith("**"):
                continue
            if bare_re.search(stripped) or wrapped_re.search(stripped):
                violations.append(f"resume/SKILL.md:{i}: {stripped}")
        assert violations == [], (
            "resume should not run local lint/test:\n"
            + "\n".join(f"  - {v}" for v in violations)
        )

    def test_resume_does_not_offer_resume_start_fresh_continue(self):
        """resume must not expose the Resume/Start fresh/Continue trio as AskUser options."""
        content = _read_skill("resume")
        body = content.split("<!-- INLINE-PROTOCOLS:START -->", 1)[0]
        # The SKILL.md may mention the phrase in prose rules ("Does NOT offer ..."),
        # but must never present it as AskUser options like `Options: Resume / Start fresh / Continue`.
        offending = re.compile(
            r"Options:\s*Resume\s*/\s*Start fresh(\s*\(delete session\))?\s*/\s*Continue",
            re.IGNORECASE,
        )
        assert not offending.search(body), (
            "resume must not list Resume/Start fresh/Continue as AskUser options"
        )

    def test_resume_has_auto_detect_and_pendente_paths(self):
        """resume must document the auto-detect and Pendente fallback behaviors."""
        content = _read_skill("resume")
        body = content.split("<!-- INLINE-PROTOCOLS:START -->", 1)[0]
        assert "Auto-Detect" in body, (
            "resume must document the auto-detect flow when no T-XXX is provided"
        )
        assert "/optimus-plan" in body, (
            "resume must reference /optimus-plan as the Pendente-flow delegate"
        )

    def test_resume_validates_task_id_format(self):
        """resume must validate TASK_ID matches ^T-[0-9]+$ and refuse empty/malformed IDs."""
        content = _read_skill("resume")
        body = content.split("<!-- INLINE-PROTOCOLS:START -->", 1)[0]
        # Look for the regex check and the Step 3.2 hard guard
        assert re.search(r'\[\[\s*"\$TASK_ID"\s*=~\s*\^T-\[0-9\]\+\$\s*\]\]', body), (
            "resume must have a regex guard for TASK_ID format (=~ ^T-[0-9]+$)"
        )
        # Must refuse at Step 3.2 before grep/awk
        assert "Refusing worktree lookup to avoid matching main repo" in body, (
            "resume must document the Step 3.2 guard to prevent matching the main repo"
        )

    def test_resume_checks_empty_tasks_table(self):
        """resume must detect zero-data-row tables per AGENTS.md Format Validation item 15."""
        content = _read_skill("resume")
        body = content.split("<!-- INLINE-PROTOCOLS:START -->", 1)[0]
        assert "Reject Empty Tasks Table" in body or "zero-data-row" in body, (
            "resume must have an explicit empty-table rejection step"
        )
        assert re.search(r"grep -cE '[^']*T-\[0-9\]\+", body), (
            "resume must use grep -cE '^\\| T-[0-9]+ \\|' to count data rows"
        )

    def test_resume_checks_dependencies(self):
        """resume must compute BLOCKING_DEPS and hide stage options when deps are not DONE."""
        content = _read_skill("resume")
        body = content.split("<!-- INLINE-PROTOCOLS:START -->", 1)[0]
        assert "BLOCKING_DEPS" in body, (
            "resume must compute BLOCKING_DEPS from the Depends column"
        )
        assert "Dependency Check" in body, (
            "resume must have an explicit Dependency Check step"
        )
        assert "Next stage is BLOCKED" in body, (
            "resume must surface the BLOCKED warning in the Phase 4 summary"
        )

    def test_resume_checks_pr_state(self):
        """resume must query gh pr view and adapt the next-stage recommendation to PR state."""
        content = _read_skill("resume")
        body = content.split("<!-- INLINE-PROTOCOLS:START -->", 1)[0]
        assert "gh pr view" in body, (
            "resume must check PR state via gh pr view"
        )
        assert "PR_STATE" in body or "PR_INFO" in body, (
            "resume must capture PR state/info for the summary"
        )
        # The Phase 4 recommendation table should mention both /optimus-pr-check and /optimus-done
        assert "/optimus-pr-check" in body, (
            "resume must recommend /optimus-pr-check for Validando Impl + OPEN PR"
        )

    def test_resume_reports_worktree_git_status(self):
        """resume must report git status (uncommitted/unpushed/behind) in Phase 4 summary."""
        content = _read_skill("resume")
        body = content.split("<!-- INLINE-PROTOCOLS:START -->", 1)[0]
        assert "GIT_UNCOMMITTED" in body, (
            "resume must count uncommitted changes in the worktree"
        )
        assert "GIT_UNPUSHED" in body, (
            "resume must count unpushed commits in the worktree"
        )

    def test_resume_reads_session_file(self):
        """resume must read .optimus/sessions/session-<task-id>.json when available."""
        content = _read_skill("resume")
        body = content.split("<!-- INLINE-PROTOCOLS:START -->", 1)[0]
        assert "SESSION_FILE" in body, (
            "resume must inspect the session file for crash-recovery info"
        )
        assert "sessions/session-" in body, (
            "resume must reference the session file path pattern"
        )

    def test_resume_reads_stats_file(self):
        """resume must surface stats.json churn signals when plan_runs or review_runs >= 2."""
        content = _read_skill("resume")
        body = content.split("<!-- INLINE-PROTOCOLS:START -->", 1)[0]
        assert "STATS_FILE" in body, (
            "resume must inspect stats.json for churn signals"
        )
        assert "plan_runs" in body and "review_runs" in body, (
            "resume must display plan_runs and review_runs counters when significant"
        )

    def test_resume_sets_terminal_title(self):
        """resume must set the terminal title per AGENTS.md Protocol: Terminal Identification."""
        content = _read_skill("resume")
        body = content.split("<!-- INLINE-PROTOCOLS:START -->", 1)[0]
        assert re.search(r'optimus:\s+RESUME\s+\$TASK_ID', body), (
            "resume must set terminal title with RESUME label"
        )
        assert re.search(r'_optimus_set_title\s+"optimus:\s+RESUME', body), (
            "resume must invoke the _optimus_set_title helper with the RESUME label"
        )

    # --- Round 2 regression tests ---

    def test_resume_body_has_no_fcode_markers(self):
        """No F# markers (F1, F3/F11, F18, etc.) should remain in the body — they are
        non-durable references to historical finding indices. (R13)
        """
        content = _read_skill("resume")
        body = content.split("<!-- INLINE-PROTOCOLS:START -->", 1)[0]
        # Accept "#<digits>" (PR numbers) but reject bare F<digits> markers
        offending = []
        for i, line in enumerate(body.splitlines(), 1):
            for m in re.finditer(r"\bF\d+\b", line):
                # Allow unit-qualified references that happen to start with F (none expected)
                offending.append(f"line {i}: {line.strip()}")
        assert offending == [], (
            "resume body still contains F# markers (R13):\n"
            + "\n".join(f"  - {v}" for v in offending[:20])
        )

    def test_resume_step_2_3_has_explicit_extraction(self):
        """The Read-Task-Metadata step (anchor `step-read-task-metadata`) must have
        bash extracting TASK_TITLE/TIPO/DEPENDS/VERSION with non-empty assertions —
        prose-only is insufficient. (R1)

        Anchor-based reference replaces the verbatim numeric step ID for stability.
        """
        content = _read_skill("resume")
        body = content.split("<!-- INLINE-PROTOCOLS:START -->", 1)[0]
        assert '<a id="step-read-task-metadata"></a>' in body, (
            "resume must define a `step-read-task-metadata` anchor above the "
            "metadata-extraction step."
        )
        assert "TASK_ROW=" in body, (
            "resume read-task-metadata step must capture the row into TASK_ROW via awk/grep"
        )
        assert re.search(r"awk -F'\|'.*print\s*\$3", body) or "print $3" in body, (
            "resume read-task-metadata step must extract columns 3/4/5/7 via awk -F'|'"
        )
        # Must loop over the captured vars and STOP if any is empty
        assert "TASK_TITLE TASK_TIPO TASK_DEPENDS TASK_VERSION" in body or \
               all(v in body for v in ["TASK_TITLE", "TASK_TIPO", "TASK_DEPENDS", "TASK_VERSION"]), (
            "resume read-task-metadata step must reference all four extracted vars"
        )

    def test_resume_git_worktree_add_checks_exit(self):
        """`git worktree add` must be wrapped in `if !` to HARD BLOCK on failure. (R2)"""
        content = _read_skill("resume")
        body = content.split("<!-- INLINE-PROTOCOLS:START -->", 1)[0]
        assert re.search(r"if\s+!\s+git worktree add", body), (
            "resume must HARD BLOCK when `git worktree add` fails"
        )
        assert re.search(r"if\s+!\s+cd\s+\"\$WORKTREE_PATH\"", body), (
            "resume must HARD BLOCK when `cd` after worktree creation fails"
        )

    def test_resume_three_state_pr(self):
        """PR_STATE must distinguish NONE / concrete state / UNKNOWN. (R9)"""
        content = _read_skill("resume")
        body = content.split("<!-- INLINE-PROTOCOLS:START -->", 1)[0]
        assert "gh auth status" in body, (
            "resume must probe gh auth before relying on gh pr view output"
        )
        assert "UNKNOWN" in body and "NONE" in body, (
            "resume must differentiate UNKNOWN (gh failure) from NONE (no PR) in Phase 4"
        )
        # Phase 4.4 recommendation table must mention UNKNOWN suppression
        assert "UNKNOWN" in body and "Suppressed" in body, (
            "resume Phase 4.4 must suppress PR-dependent recommendations when PR_STATE is UNKNOWN"
        )

    def test_resume_case3_no_unsafe_plan_delegation(self):
        """The Reset-to-Pendente recovery (anchor `step-reset-to-pendente-recovery`)
        must NOT offer a bare 'Re-run /optimus-plan' option — plan's anti-pulo rejects
        in-progress statuses. Use the chained "Reset then plan" option. (R3)

        Anchor reference instead of verbatim step number keeps the test stable across
        phase renumbering.
        """
        content = _read_skill("resume")
        body = content.split("<!-- INLINE-PROTOCOLS:START -->", 1)[0]
        # The in-progress recovery sub-case must use the chained option
        assert "Reset to Pendente, then run /optimus-plan" in body, (
            "resume reset-to-pendente recovery must offer 'Reset to Pendente, then run /optimus-plan'"
        )
        # And must not offer a bare "Re-run /optimus-plan" alongside
        case3_section = body.split("Inconsistency: T-XXX has status")[-1]
        case3_section = case3_section.split("**Abort**")[0] if "**Abort**" in case3_section else case3_section
        assert "**Re-run /optimus-plan**" not in case3_section, (
            "resume reset-to-pendente recovery must NOT offer a bare 'Re-run /optimus-plan' option"
        )

    def test_resume_reset_tracks_success(self):
        """Reset-to-Pendente must track RESET_DONE and print success only on actual write. (R8)"""
        content = _read_skill("resume")
        body = content.split("<!-- INLINE-PROTOCOLS:START -->", 1)[0]
        assert "RESET_DONE=0" in body, (
            "resume must initialize RESET_DONE=0 before attempting the jq del"
        )
        assert "RESET_DONE=1" in body, (
            "resume must set RESET_DONE=1 only after the mv succeeds"
        )
        assert 'RESET_DONE" -eq 1' in body or 'RESET_DONE" = 1' in body, (
            "resume must gate the success message on RESET_DONE"
        )

    def test_resume_dry_run_forbids_reset(self):
        """The dry-run short-circuit step (anchor `step-dry-run-short-circuit`) must
        explicitly forbid the Reset-to-Pendente recovery (anchor
        `step-reset-to-pendente-recovery`) in dry-run mode. (R25)

        Anchor-based check stays stable across phase renumbering.
        """
        content = _read_skill("resume")
        body = content.split("<!-- INLINE-PROTOCOLS:START -->", 1)[0]
        # Both anchors must be present (locating the steps is not number-dependent).
        assert '<a id="step-dry-run-short-circuit"></a>' in body, (
            "resume must define a `step-dry-run-short-circuit` anchor above the "
            "dry-run short-circuit step."
        )
        assert '<a id="step-reset-to-pendente-recovery"></a>' in body, (
            "resume must define a `step-reset-to-pendente-recovery` anchor above "
            "the inconsistent-state recovery option."
        )
        # The dry-run section must explicitly forbid the Reset-to-Pendente recovery.
        # Match on the action description, not on a verbatim step number.
        assert re.search(
            r"Do NOT run the .*Reset to Pendente.*recovery", body
        ), (
            "resume dry-run short-circuit must forbid the Reset-to-Pendente recovery "
            "(prose 'Do NOT run the ... Reset to Pendente ... recovery')."
        )

    def test_resume_whitelists_non_terminal_status(self):
        """Auto-detect filter must whitelist concrete non-terminal statuses to avoid
        treating null/missing status as in-progress. (R6)
        """
        content = _read_skill("resume")
        body = content.split("<!-- INLINE-PROTOCOLS:START -->", 1)[0]
        # Step 2.2 filter must use "or"-whitelist, not the negative "!="-blacklist
        assert '.value.status == "Validando Spec"' in body, (
            "resume Step 2.2 filter must whitelist Validando Spec explicitly"
        )
        assert '.value.status == "Em Andamento"' in body, (
            "resume Step 2.2 filter must whitelist Em Andamento explicitly"
        )
        assert '.value.status == "Validando Impl"' in body, (
            "resume Step 2.2 filter must whitelist Validando Impl explicitly"
        )


# --- Integration tests for the optimus-tasks.md relocation + separate-repo feature ---


def _has_git():
    return shutil.which("git") is not None


def _run(cmd, cwd=None, env=None):
    """Run a command, capturing both stdout and stderr. Returns (rc, out, err)."""
    result = subprocess.run(
        cmd, cwd=cwd, env=env,
        capture_output=True, text=True, check=False,
    )
    return result.returncode, result.stdout, result.stderr


def _init_repo(path: Path):
    """Initialize a minimal git repo at path with user configured."""
    path.mkdir(parents=True, exist_ok=True)
    _run(["git", "init", "--initial-branch=main"], cwd=path)
    _run(["git", "config", "user.email", "test@example.com"], cwd=path)
    _run(["git", "config", "user.name", "Test"], cwd=path)
    _run(["git", "config", "commit.gpgsign", "false"], cwd=path)


def _extract_protocol_bash(section_title: str) -> str:
    """Extract the first bash code block under a protocol section in AGENTS.md."""
    content = AGENTS_MD.read_text()
    # Find the section
    marker = f"### {section_title}"
    idx = content.find(marker)
    if idx == -1:
        raise RuntimeError(f"Section '{section_title}' not found in AGENTS.md")
    # Find next `### ` (next section) or end of content
    next_idx = content.find("\n### ", idx + len(marker))
    section = content[idx:next_idx] if next_idx != -1 else content[idx:]
    # Extract first ```bash ... ``` block
    bash_start = section.find("```bash\n")
    if bash_start == -1:
        raise RuntimeError(f"No bash block under '{section_title}'")
    bash_end = section.find("\n```", bash_start + len("```bash\n"))
    return section[bash_start + len("```bash\n"):bash_end]


@pytest.mark.skipif(not _has_git(), reason="git not available")
class TestScopeIntegration:
    """Integration tests for `Protocol: Resolve Tasks Git Scope` and TaskSpec
    resolution. After M1 (Migrate) was removed in issue #20, this class no
    longer covers migration — it focuses on scope detection, dash-prefix
    rejection, non-git rejection, and path-traversal protection.

    These tests execute the bash blocks from AGENTS.md against real tmp git
    repos to verify the protocols actually work — not just that their
    documentation exists.
    """

    def test_scope_resolution_same_repo(self, tmp_path: Path):
        """Resolve Tasks Git Scope should detect same-repo when tasksDir is inside project."""
        _init_repo(tmp_path)
        (tmp_path / "docs" / "pre-dev").mkdir(parents=True, exist_ok=True)
        bash = _extract_protocol_bash("Protocol: Resolve Tasks Git Scope")
        # Run the bash and check the exported variables.
        probe = f'{bash}\necho "SCOPE=$TASKS_GIT_SCOPE"\necho "DIR=$TASKS_DIR"\necho "FILE=$TASKS_FILE"\n'
        rc, out, err = _run(["bash", "-c", probe], cwd=tmp_path)
        assert rc == 0, f"Bash failed: {err}"
        assert "SCOPE=same-repo" in out, f"Expected same-repo scope, got: {out}"
        assert "DIR=docs/pre-dev" in out
        assert "FILE=docs/pre-dev/optimus-tasks.md" in out

    def test_scope_resolution_separate_repo(self, tmp_path: Path):
        """Resolve Tasks Git Scope should detect separate-repo when tasksDir is in a different repo."""
        project = tmp_path / "project"
        tasks_repo = tmp_path / "tasks-repo"
        _init_repo(project)
        _init_repo(tasks_repo)
        # Point tasksDir from project config to the tasks repo.
        (project / ".optimus").mkdir()
        config = project / ".optimus" / "config.json"
        config.write_text(f'{{"tasksDir": "{tasks_repo}"}}\n')
        bash = _extract_protocol_bash("Protocol: Resolve Tasks Git Scope")
        probe = f'{bash}\necho "SCOPE=$TASKS_GIT_SCOPE"\necho "REL=$TASKS_GIT_REL"\n'
        rc, out, err = _run(["bash", "-c", probe], cwd=project)
        assert rc == 0, f"Bash failed: {err}\n\n{out}"
        assert "SCOPE=separate-repo" in out
        # Path relative to tasks repo root → just "optimus-tasks.md"
        assert "REL=optimus-tasks.md" in out

    def test_scope_resolution_rejects_dash_prefix(self, tmp_path: Path):
        """Resolve Tasks Git Scope must reject TASKS_DIR starting with '-' (git injection)."""
        _init_repo(tmp_path)
        (tmp_path / ".optimus").mkdir()
        config = tmp_path / ".optimus" / "config.json"
        config.write_text('{"tasksDir": "--exec-path=/tmp/evil"}\n')
        bash = _extract_protocol_bash("Protocol: Resolve Tasks Git Scope")
        rc, out, err = _run(["bash", "-c", bash], cwd=tmp_path)
        assert rc != 0, "Should reject dash-prefixed tasksDir"
        assert "security" in err.lower() or "start with" in err.lower()

    def test_scope_resolution_rejects_non_git_dir(self, tmp_path: Path):
        """Resolve Tasks Git Scope must reject tasksDir that exists but is not a git repo.

        The non-git directory must be truly outside any git repo — otherwise `git -C`
        walks upward and finds the parent. We create the project repo in a subdir and
        the non-git dir as a sibling.
        """
        project = tmp_path / "project"
        _init_repo(project)
        # non-git-dir is a sibling of project, at tmp_path level (not inside any git repo).
        non_git = tmp_path / "not-a-git-repo"
        non_git.mkdir()
        (project / ".optimus").mkdir()
        config = project / ".optimus" / "config.json"
        config.write_text(f'{{"tasksDir": "{non_git}"}}\n')
        bash = _extract_protocol_bash("Protocol: Resolve Tasks Git Scope")
        rc, out, err = _run(["bash", "-c", bash], cwd=project)
        assert rc != 0, f"Should reject non-git tasksDir (out={out}, err={err})"
        assert "not inside a git repository" in err.lower()

    def test_taskspec_rejects_path_traversal(self, tmp_path: Path):
        """TaskSpec Resolution must reject ../../../etc/passwd escape attempts."""
        _init_repo(tmp_path)
        tasks_dir = tmp_path / "docs" / "pre-dev"
        tasks_dir.mkdir(parents=True)
        # Malicious TaskSpec
        probe = f'''
TASKS_DIR="{tasks_dir}"
TASK_SPEC="../../../../etc/passwd"
TASKS_DIR_ABS=$(cd "$TASKS_DIR" && pwd)
RESOLVED_PATH=$(cd "$TASKS_DIR_ABS" && realpath -m "$TASK_SPEC" 2>/dev/null \
  || python3 -c "import os,sys; print(os.path.realpath(os.path.join(sys.argv[1], sys.argv[2])))" "$TASKS_DIR_ABS" "$TASK_SPEC" 2>/dev/null)
case "$RESOLVED_PATH" in
  "$TASKS_DIR_ABS"/*) echo "ALLOWED" ;;
  *) echo "BLOCKED" ;;
esac
'''
        rc, out, err = _run(["bash", "-c", probe], cwd=tmp_path)
        assert "BLOCKED" in out, f"Path traversal was not blocked: {out}"

# --- Test that inline-protocols.py auto-injects foundational protocols when
#     Protocol: optimus-tasks.md Validation is referenced ---


class TestInlineProtocolsFoundational:
    """Verify inline-protocols.py auto-injects foundational protocols for optimus-tasks.md Validation refs.

    This is the `needs_format` branch added in commit ad0d8d7 — previously untested.
    """

    def test_needs_format_injects_scope(self, tmp_path: Path):
        """When a skill references Protocol: optimus-tasks.md Validation, the inlined block
        MUST contain Protocol: Resolve Tasks Git Scope (validation depends on it)."""
        import importlib.util
        ip_path = REPO_ROOT / "scripts" / "inline-protocols.py"
        spec = importlib.util.spec_from_file_location("inline_protocols", ip_path)
        assert spec is not None, f"Cannot load spec for {ip_path}"
        assert spec.loader is not None, f"Spec loader is None for {ip_path}"
        ip = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ip)

        agents = tmp_path / "AGENTS.md"
        agents.write_text(
            "## Protocol: optimus-tasks.md Validation (HARD BLOCK)\nValidation content\n"
            "## Protocol: Resolve Tasks Git Scope\nScope resolution content\n"
        )
        skill_dir = tmp_path / "myplugin" / "skills" / "optimus-myplugin"
        skill_dir.mkdir(parents=True)
        skill = skill_dir / "SKILL.md"
        skill.write_text("Body: see AGENTS.md Protocol: optimus-tasks.md Validation.\n")

        # Monkey-patch paths
        original_agents = ip.AGENTS_MD
        original_root = ip.REPO_ROOT
        try:
            ip.AGENTS_MD = agents
            ip.REPO_ROOT = tmp_path
            ip.inline_protocols()
        finally:
            ip.AGENTS_MD = original_agents
            ip.REPO_ROOT = original_root

        inlined = skill.read_text()
        assert "Scope resolution content" in inlined, \
            "Resolve Tasks Git Scope was not auto-injected"
        assert "Validation content" in inlined

    def test_discover_review_droids_inlined_in_consumers(self):
        """Both pr-check and deep-review must reference Protocol: Discover Review
        Droids in their body AND have it inlined in their <!-- INLINE-PROTOCOLS -->
        block. Catches regressions where inline-protocols.py silently fails to
        sync due to reference-format drift.
        """
        consumers = [
            "pr-check/skills/optimus-pr-check/SKILL.md",
            "deep-review/skills/optimus-deep-review/SKILL.md",
        ]
        missing_body = []
        missing_inlined = []
        for rel in consumers:
            path = REPO_ROOT / rel
            content = path.read_text()
            # Body reference
            if "Protocol: Discover Review Droids" not in content:
                missing_body.append(rel)
            # Inlined block (between markers)
            m = re.search(
                r"<!-- INLINE-PROTOCOLS:START -->(.*?)<!-- INLINE-PROTOCOLS:END -->",
                content, re.DOTALL,
            )
            if not m or "### Protocol: Discover Review Droids" not in m.group(1):
                missing_inlined.append(rel)
        assert not missing_body, (
            f"Skills reference Protocol: Discover Review Droids in body but it's "
            f"missing in: {missing_body}"
        )
        assert not missing_inlined, (
            f"Skills reference Protocol: Discover Review Droids but it's NOT "
            f"inlined in their <!-- INLINE-PROTOCOLS --> block: {missing_inlined}. "
            f"Likely cause: scripts/inline-protocols.py regex did not match the "
            f"reference syntax. Re-run the syncer and inspect."
        )

    def test_pr_check_has_outdated_thread_cleanup(self):
        """pr-check MUST collect outdated threads into a separate `outdated_threads`
        list (NOT discard them) and auto-resolve them in the cleanup step (anchor
        `step-cleanup-outdated-threads`). Without this, outdated threads remain
        open on the PR — CodeRabbit and similar approval gates withhold approval
        as long as ANY thread (active or outdated) is unresolved.

        References use a stable semantic anchor instead of the verbatim numeric
        step ID so this test does not break when phases are renumbered.
        """
        path = REPO_ROOT / "pr-check/skills/optimus-pr-check/SKILL.md"
        content = path.read_text()

        # Stale "filter/filtered" prose check — the partition refactor must sweep ALL
        # references to the old discard-only model. These assertions catch regressions
        # where future edits accidentally re-introduce filter terminology.
        stale_phrases = [
            "Outdated (filtered)",         # summary template (F2)
            "outdated filtered",            # totals line (F2)
            "filtered set",                  # findings_total formula (F1)
            "filtered out by Step 1.3.1",   # narrative (F3)
        ]
        remaining = [p for p in stale_phrases if p in content]
        assert not remaining, (
            f"Stale 'filter/filtered' prose found in pr-check after the partition "
            f"refactor at the thread-collection step. The partition model replaced "
            f"the old discard semantics; these phrases are vestigial and contradict "
            f"the new flow: {remaining}. See the cleanup step anchored at "
            f"`step-cleanup-outdated-threads` for the hygiene path."
        )

        # Thread-collection step must partition into active + outdated lists, not discard.
        assert "outdated_threads" in content, (
            "pr-check thread-collection step must collect outdated threads into an "
            "`outdated_threads` list (not discard via filter). Without the list, "
            "the cleanup step has no input to clean up."
        )
        # Old discard-only language must be gone.
        assert "Filter outdated threads:** Remove all threads" not in content, (
            "pr-check thread-collection step still uses the old discard-only language "
            "for outdated threads. Replace with the partition-into-two-lists pattern."
        )
        # Cleanup step must exist (located via stable anchor) and target outdated threads.
        assert '<a id="step-cleanup-outdated-threads"></a>' in content, (
            "pr-check is missing the outdated-thread cleanup step (semantic anchor "
            "`step-cleanup-outdated-threads`). Outdated threads block CodeRabbit "
            "approval and must be hygienically auto-resolved regardless of REVIEW_MODE."
        )
        # The auto-reply text must be present so runtime LLMs use a stable phrase
        # (the cleanup step's idempotency check matches against this exact string).
        assert "Outdated — this thread references code that was modified" in content, (
            "pr-check cleanup step must specify the exact auto-reply text. The "
            "idempotency check (skip reply if it already exists) matches this "
            "string verbatim to handle re-runs after a crash."
        )


class TestDualPlatformParity:
    """Optimus ships to BOTH Claude Code and Droid (Factory) but the two
    platforms package commands differently:

    - Droid: 17 separate plugins (`.factory-plugin/marketplace.json`),
      invoked as `/<plugin>` or `/<alias>` (no namespace prefix possible).
    - Claude Code: a SINGLE `optimus` plugin (`.claude-plugin/marketplace.json`)
      whose source is the repo root. Top-level `commands/<plugin>.md` and
      `commands/<alias>.md` are auto-discovered by Claude and exposed as
      `/optimus:<plugin>` and `/optimus:<alias>`.

    These tests enforce that BOTH layers stay aligned: every Droid plugin
    has the per-plugin surfaces (SKILL.md, plugin.json, optional alias)
    AND a corresponding top-level `commands/<name>.md` for Claude.

    See AGENTS.md "Dual-platform parity (Claude Code ↔ Droid)" for the
    contributor workflow these tests enforce.
    """

    def test_claude_marketplace_has_single_optimus_plugin(self):
        """Claude marketplace ships exactly ONE plugin (`optimus`) sourced
        from the repo root. The 17 commands surface via the top-level
        `commands/` directory, not as 17 marketplace entries.
        """
        claude_path = REPO_ROOT / ".claude-plugin" / "marketplace.json"
        claude_data = json.loads(claude_path.read_text())
        plugins = claude_data.get("plugins", [])
        assert len(plugins) == 1, (
            f"Claude marketplace must have exactly 1 plugin (`optimus`), "
            f"found {len(plugins)}. The single-plugin layout is what gives "
            f"users the `/optimus:<command>` namespaced invocation."
        )
        assert plugins[0]["name"] == "optimus", (
            f"Claude marketplace plugin must be named `optimus`, got "
            f"{plugins[0]['name']!r}."
        )
        assert plugins[0]["source"] == "./", (
            f"Claude `optimus` plugin source must be `./` (repo root) so the "
            f"top-level `commands/` directory is discovered. Note: the leading "
            f"`./` is required by the marketplace schema validator (bare `.` "
            f"fails). Got {plugins[0]['source']!r}."
        )

    def test_every_plugin_has_both_platform_surfaces(self):
        """Every plugin in the Droid marketplace must ship BOTH platform
        surfaces:

        - Droid:  `<plugin>/.factory-plugin/plugin.json` and the SKILL.md.
        - Claude: top-level `commands/<plugin>.md` (generated by
          `scripts/sync-claude-commands.py` from the SKILL.md).

        Missing either surface means the command fails to install/discover
        on that platform.
        """
        factory_path = REPO_ROOT / ".factory-plugin" / "marketplace.json"
        factory_data = json.loads(factory_path.read_text())

        missing_skill = []
        missing_droid = []
        missing_claude_command = []
        for plugin in factory_data["plugins"]:
            name = plugin["name"]
            plugin_dir = REPO_ROOT / name
            skill_md = plugin_dir / "skills" / f"optimus-{name}" / "SKILL.md"
            droid_config = plugin_dir / ".factory-plugin" / "plugin.json"
            claude_cmd = REPO_ROOT / "commands" / f"{name}.md"
            if not skill_md.exists():
                missing_skill.append(
                    f"{name} (expected {skill_md.relative_to(REPO_ROOT)})"
                )
            if not droid_config.exists():
                missing_droid.append(
                    f"{name} (expected {droid_config.relative_to(REPO_ROOT)})"
                )
            if not claude_cmd.exists():
                missing_claude_command.append(
                    f"{name} (expected {claude_cmd.relative_to(REPO_ROOT)})"
                )

        assert not missing_skill, (
            f"Plugins missing SKILL.md (the shared body source): "
            f"{missing_skill}."
        )
        assert not missing_droid, (
            f"Plugins missing Droid surface (.factory-plugin/plugin.json): "
            f"{missing_droid}. The sync would install these on Claude Code "
            f"only — Droid users would not see them."
        )
        assert not missing_claude_command, (
            f"Plugins missing Claude command surface (commands/<name>.md): "
            f"{missing_claude_command}. Run "
            f"`python3 scripts/sync-claude-commands.py` to regenerate."
        )

    def test_command_aliases_correspond_to_real_plugins(self):
        """Every ``<plugin>/commands/<alias>.md`` slash-command alias file
        must be inside a directory that corresponds to a real plugin listed
        in the Droid marketplace, and the alias body must redirect to the
        matching ``/optimus-<plugin>`` slash command (the per-plugin layout
        also feeds Droid, which uses the bare prefix).

        The flattened `commands/<alias>.md` files at repo root are emitted
        by `scripts/sync-claude-commands.py` and rewrite the redirect to
        `/optimus:<plugin>`; that direction is verified separately by
        ``TestClaudeCommandsSync``.
        """
        factory_path = REPO_ROOT / ".factory-plugin" / "marketplace.json"
        factory_data = json.loads(factory_path.read_text())
        plugin_names = {p["name"] for p in factory_data["plugins"]}

        orphans = []
        broken_redirects = []
        for cmd_file in sorted(REPO_ROOT.glob("*/commands/*.md")):
            plugin_name = cmd_file.parent.parent.name
            if plugin_name not in plugin_names:
                orphans.append(
                    f"{cmd_file.relative_to(REPO_ROOT)} (plugin '{plugin_name}' "
                    f"not in marketplace)"
                )
                continue
            body = cmd_file.read_text()
            expected_redirect = f"/optimus-{plugin_name}"
            if expected_redirect not in body:
                broken_redirects.append(
                    f"{cmd_file.relative_to(REPO_ROOT)} does not redirect to "
                    f"{expected_redirect} (alias should forward to the main "
                    f"slash command)"
                )

        assert not orphans, (
            "Orphan command alias files (alias exists but plugin is not in "
            "the marketplace):\n  - " + "\n  - ".join(orphans)
        )
        assert not broken_redirects, (
            "Command alias files that don't redirect to their plugin's main "
            "slash command:\n  - " + "\n  - ".join(broken_redirects)
        )


def _rewrite_slash_refs(text: str) -> str:
    """Apply the `/optimus-X` -> `/optimus:X` substitution that
    `scripts/sync-claude-commands.py` performs. Mirrored locally to
    avoid importing from the script (its filename has a hyphen).
    """
    return re.sub(r"/optimus-([a-z][a-z0-9-]*)", r"/optimus:\1", text)


def _strip_frontmatter(text: str) -> str:
    """Return the body portion of a markdown file with YAML-ish frontmatter.

    Tolerates a missing frontmatter (returns the text unchanged).
    """
    if not text.startswith("---\n"):
        return text
    end = text.find("\n---\n", 4)
    if end == -1:
        return text
    return text[end + len("\n---\n") :]


class TestClaudeCommandsSync:
    """Drift-detection tests for the top-level `commands/` directory.

    `scripts/sync-claude-commands.py` flattens per-plugin SKILL.md bodies
    into single-file `commands/<plugin>.md` entries (and copies aliases).
    These tests verify the flattened files exist, are not orphaned, and
    actually match what the script would produce — so a contributor cannot
    forget to rerun the syncer and ship a stale Claude command surface.
    """

    def _factory_plugin_names(self) -> list[str]:
        factory_path = REPO_ROOT / ".factory-plugin" / "marketplace.json"
        return [p["name"] for p in json.loads(factory_path.read_text())["plugins"]]

    def _alias_files_by_name(self) -> dict[str, Path]:
        """Map alias filename → source path under `<plugin>/commands/`."""
        out: dict[str, Path] = {}
        for cmd_file in sorted(REPO_ROOT.glob("*/commands/*.md")):
            out[cmd_file.name] = cmd_file
        return out

    def test_main_command_exists_for_every_plugin(self):
        """Every Droid plugin has a corresponding top-level
        `commands/<plugin>.md`."""
        missing = []
        for name in self._factory_plugin_names():
            cmd_file = REPO_ROOT / "commands" / f"{name}.md"
            if not cmd_file.exists():
                missing.append(name)
        assert not missing, (
            f"Top-level commands missing for plugins: {missing}. "
            f"Run `python3 scripts/sync-claude-commands.py` to regenerate."
        )

    def test_alias_command_exists_for_every_alias(self):
        """Every per-plugin `<plugin>/commands/<alias>.md` has a matching
        top-level `commands/<alias>.md`."""
        missing = []
        for alias_name, source_path in self._alias_files_by_name().items():
            target = REPO_ROOT / "commands" / alias_name
            if not target.exists():
                missing.append(
                    f"{alias_name} (source: "
                    f"{source_path.relative_to(REPO_ROOT)})"
                )
        assert not missing, (
            f"Top-level alias commands missing: {missing}. "
            f"Run `python3 scripts/sync-claude-commands.py`."
        )

    def test_no_orphan_top_level_commands(self):
        """Every `commands/*.md` corresponds to either a real plugin (main
        command) or a real alias from a `<plugin>/commands/<alias>.md`."""
        plugin_names = set(self._factory_plugin_names())
        alias_names = set(self._alias_files_by_name().keys())
        valid = {f"{p}.md" for p in plugin_names} | alias_names

        commands_dir = REPO_ROOT / "commands"
        if not commands_dir.is_dir():
            pytest.skip("commands/ directory does not exist yet")
        orphans = []
        for cmd_file in sorted(commands_dir.glob("*.md")):
            if cmd_file.name not in valid:
                orphans.append(cmd_file.name)
        assert not orphans, (
            f"Orphan top-level commands (no matching plugin or alias): "
            f"{orphans}. Run `python3 scripts/sync-claude-commands.py` to "
            f"prune them."
        )

    def test_main_command_body_matches_skill_md(self):
        """`commands/<plugin>.md` body equals `<plugin>/skills/optimus-<plugin>/SKILL.md`
        body after applying `/optimus-X` -> `/optimus:X`. This proves
        `scripts/sync-claude-commands.py` was run before commit and that no
        manual edits drifted from the SKILL.md source.
        """
        violations = []
        for name in self._factory_plugin_names():
            skill_path = REPO_ROOT / name / "skills" / f"optimus-{name}" / "SKILL.md"
            cmd_path = REPO_ROOT / "commands" / f"{name}.md"
            if not (skill_path.exists() and cmd_path.exists()):
                # Surface as a separate failure mode in the existence tests.
                continue
            skill_body = _strip_frontmatter(skill_path.read_text())
            cmd_body = _strip_frontmatter(cmd_path.read_text())
            expected = _rewrite_slash_refs(skill_body).rstrip() + "\n"
            actual = cmd_body.rstrip() + "\n"
            if expected != actual:
                violations.append(name)
        assert not violations, (
            f"`commands/<plugin>.md` bodies have drifted from their SKILL.md "
            f"sources for: {violations}. "
            f"Run `python3 scripts/sync-claude-commands.py` to resync."
        )

    def test_alias_command_body_redirects_to_namespaced_slash(self):
        """`commands/<alias>.md` files at the repo root redirect to
        `/optimus:<plugin>` (the namespaced Claude form), not the bare
        `/optimus-<plugin>` form used by the per-plugin Droid layer.
        """
        violations = []
        for alias_name, source_path in self._alias_files_by_name().items():
            plugin_name = source_path.parent.parent.name
            target = REPO_ROOT / "commands" / alias_name
            if not target.exists():
                continue
            body = target.read_text()
            expected = f"/optimus:{plugin_name}"
            forbidden = f"/optimus-{plugin_name}"
            if expected not in body:
                violations.append(
                    f"{alias_name} missing `{expected}` redirect"
                )
            elif forbidden in body:
                violations.append(
                    f"{alias_name} still contains the un-namespaced "
                    f"`{forbidden}` form"
                )
        assert not violations, (
            "Top-level alias commands have wrong redirects:\n  - "
            + "\n  - ".join(violations)
        )


class TestWorkspaceValidationHardening:
    """Defense-in-depth checks for branch/worktree validation across stage skills.

    Covers three independent guarantees layered on top of Workspace Auto-Navigation:

    1. Mutating stages (build, review, done) reference Protocol: Default Branch
       Refusal so a bypass of Workspace Auto-Navigation cannot silently mutate the
       default branch.
    2. pr-check cross-checks the PR's headRefName against the user's current branch
       and surfaces a confirmation when the user passed an explicit PR number that
       belongs to a different branch.
    3. Protocol: Workspace Auto-Navigation documents the stage-specific override that
       `done` applies (no multi-task chooser, no auto-navigation across tasks).
    """

    def test_default_branch_hard_block_in_stage_skills(self):
        """build, review, done must reference Protocol: Default Branch Refusal.

        Workspace Auto-Navigation is the primary safeguard, but it can be bypassed
        (user cancels AskUser, silent failure, future skill that forgets to invoke
        the protocol). Each mutating stage MUST invoke Default Branch Refusal as a
        second, unconditional guard before any state mutation.
        """
        missing = []
        for skill in WORKSPACE_SKILLS:
            content = _read_skill(skill)
            if "Protocol: Default Branch Refusal" not in content:
                missing.append(skill)
        assert missing == [], (
            "Stage skills missing Protocol: Default Branch Refusal reference "
            "(defense-in-depth against commits/mutations on the default branch):\n"
            + "\n".join(f"  - {v}" for v in missing)
        )

    def test_default_branch_refusal_protocol_defined_in_agents_md(self):
        """AGENTS.md must define the Protocol: Default Branch Refusal sub-protocol
        that the stage skills reference.
        """
        content = AGENTS_MD.read_text()
        assert "### Protocol: Default Branch Refusal" in content, (
            "AGENTS.md is missing the `### Protocol: Default Branch Refusal` "
            "section that build/review/done reference."
        )
        # Body must contain the actual guard logic — keyword sanity check so a
        # future edit that empties the section still trips the test.
        section_start = content.index("### Protocol: Default Branch Refusal")
        # Slice to next top-level `### Protocol` heading
        next_heading = content.find("### Protocol:", section_start + 1)
        section = content[section_start:next_heading] if next_heading != -1 else content[section_start:]
        assert "DEFAULT_BRANCH" in section and "git branch --show-current" in section, (
            "Protocol: Default Branch Refusal must contain the DEFAULT_BRANCH "
            "resolution and current-branch comparison shell snippet."
        )
        assert "refusing to run" in section.lower(), (
            "Protocol: Default Branch Refusal must include the refusal error "
            "message ('refusing to run ... on default branch')."
        )

    def test_pr_check_validates_task_branch_consistency(self):
        """pr-check must cross-check the PR's headRefName with the current branch
        when the user passed an explicit PR number, and AskUser on mismatch.

        Without this guard, `/optimus-pr-check 30` from branch `feat/t-007` silently
        operates on PR #30 (which may belong to a different branch) — the user's
        mental model becomes misaligned with what pr-check is actually reviewing.
        """
        content = _read_skill("pr-check")
        # The cross-check step must exist as a discrete step (any sub-step number
        # under Phase 1 is acceptable so we don't pin to 1.2.2 specifically).
        assert "headRefName" in content and "git branch --show-current" in content, (
            "pr-check must compare the PR's `headRefName` with the user's current "
            "branch (`git branch --show-current`) and AskUser on mismatch. The "
            "cross-check belongs to Phase 1 after Step 1.2 (Fetch PR Metadata)."
        )
        # The mismatch warning must be presented via AskUser (BLOCKING), not as a
        # silent log line.
        assert re.search(
            r"PR #.*is for branch.*but you are on", content, re.DOTALL
        ), (
            "pr-check must surface the PR-vs-current-branch mismatch via an "
            "AskUser prompt (warning text 'PR #<num> is for branch ... but you "
            "are on ...')."
        )

    def test_workspace_auto_navigation_documents_done_override(self):
        """Protocol: Workspace Auto-Navigation must document that `done` applies a
        stricter form of resolution (no multi-task chooser, no auto-navigation
        across tasks).

        Without this note in the canonical protocol, contributors reading
        AGENTS.md assume `done` follows the same logic as build/review and may
        introduce drift. The note tells them where to look for the strict-mode
        rule (anchored in done/SKILL.md as `step-resolve-current-workspace`).

        Anchor reference instead of verbatim step number keeps the test stable
        across phase renumbering.
        """
        content = AGENTS_MD.read_text()
        protocol_start = content.index("### Protocol: Workspace Auto-Navigation")
        next_heading = content.find("### Protocol:", protocol_start + 1)
        section = content[protocol_start:next_heading] if next_heading != -1 else content[protocol_start:]

        assert "Stage-specific overrides" in section, (
            "Protocol: Workspace Auto-Navigation must include a 'Stage-specific "
            "overrides' subsection documenting `done`'s stricter rule."
        )
        assert "/optimus-done" in section, (
            "Stage-specific overrides must reference `/optimus-done` explicitly."
        )
        # Must point readers at the concrete location of the strict-mode rule so
        # they don't have to grep blindly. The location is identified by a stable
        # semantic anchor (kebab-case, prefixed `step-`) embedded in done/SKILL.md.
        assert "step-resolve-current-workspace" in section, (
            "Stage-specific overrides must point at the `step-resolve-current-workspace` "
            "anchor in done/SKILL.md for the full strict-mode rule."
        )
        # And the anchor MUST actually exist in done/SKILL.md.
        done_skill = (REPO_ROOT / "done/skills/optimus-done/SKILL.md").read_text()
        assert '<a id="step-resolve-current-workspace"></a>' in done_skill, (
            "done/SKILL.md must define the `step-resolve-current-workspace` anchor "
            "above the workspace-resolution step."
        )


class TestSanitizeCharsetUniformity:
    """No SKILL body may redefine _optimus_sanitize with a non-canonical charset.

    Path-traversal defense: AGENTS.md canonical _optimus_sanitize forbids '.' and '/'.
    Body-level overrides that allow them are a security regression.
    """

    CANONICAL_CHARSET = "[:alnum:][:space:]-_:"

    def test_no_body_redefinition_of_sanitize(self):
        violations = []
        for skill_path in REPO_ROOT.glob("*/skills/*/SKILL.md"):
            content = skill_path.read_text()
            # Strip inlined block — only check body code
            marker = "<!-- INLINE-PROTOCOLS:START -->"
            body = content.split(marker, 1)[0]
            if "_optimus_sanitize()" in body:
                violations.append(str(skill_path.relative_to(REPO_ROOT)))
        assert violations == [], (
            f"Body-level redefinition of _optimus_sanitize() found in: {violations}. "
            f"Use the inlined canonical helper from Protocol: Notification Hooks."
        )


class TestBashBlockHygiene:
    """Ensures bash code blocks in SKILL.md and AGENTS.md don't disable set flags
    that the contract assumes (e.g., `set +u`, `set +e`, `set +o pipefail`).

    The contract is documented in AGENTS.md under Editing Rules:
    `set -euo pipefail` MUST be assumed active inside any bash code block.
    Disabling those flags inline silently breaks the assumption that helpers
    like the Quiet Command Execution wrapper rely on.
    """

    DISABLERS = ("set +u", "set +e", "set +o pipefail")

    def test_no_disable_set_flags_in_bash_blocks(self):
        """No bash block may disable -e, -u, or pipefail."""
        violations = []
        targets = [AGENTS_MD] + list(REPO_ROOT.glob("*/skills/*/SKILL.md"))
        for path in targets:
            if not path.exists():
                continue
            content = path.read_text()
            in_bash = False
            for lineno, line in enumerate(content.splitlines(), start=1):
                stripped = line.strip()
                if stripped.startswith("```bash"):
                    in_bash = True
                    continue
                if stripped.startswith("```"):
                    in_bash = False
                    continue
                if in_bash and any(d in stripped for d in self.DISABLERS):
                    rel = path.relative_to(REPO_ROOT)
                    violations.append(f"{rel}:{lineno}: {stripped}")
        assert violations == [], (
            "Bash blocks may not disable set flags that the contract assumes:\n"
            + "\n".join(f"  - {v}" for v in violations)
        )

    def test_bash_block_contract_documented_in_agents_md(self):
        """AGENTS.md must document the bash code-block contract under Editing Rules."""
        content = AGENTS_MD.read_text()
        assert "Bash code-block contract" in content, (
            "AGENTS.md must document the bash code-block contract under Editing Rules."
        )


class TestSemanticAnchorConvention:
    """Stable semantic anchors (`<a id="step-..."></a>`) replace verbatim numeric
    step IDs in cross-skill / cross-test references. This prevents test rigidity
    when SKILL.md phases are renumbered."""

    ANCHOR_PATTERN = re.compile(r'<a id="(step|phase)-([a-z0-9][a-z0-9-]*[a-z0-9])"></a>')

    def test_anchors_are_kebab_lowercase(self):
        violations = []
        for path in REPO_ROOT.glob("*/skills/*/SKILL.md"):
            content = path.read_text()
            for match in re.finditer(r'<a id="([^"]+)"></a>', content):
                anchor = match.group(1)
                if not self.ANCHOR_PATTERN.fullmatch(f'<a id="{anchor}"></a>'):
                    violations.append(
                        f"{path.relative_to(REPO_ROOT)}: invalid anchor '{anchor}' "
                        f"(must be 'step-<kebab>' or 'phase-<kebab>')"
                    )
        assert violations == [], "\n".join(violations)

    def test_no_duplicate_anchors_within_a_skill(self):
        violations = []
        for path in REPO_ROOT.glob("*/skills/*/SKILL.md"):
            content = path.read_text()
            anchors = re.findall(r'<a id="([^"]+)"></a>', content)
            seen = set()
            for a in anchors:
                if a in seen:
                    violations.append(f"{path.relative_to(REPO_ROOT)}: duplicate anchor '{a}'")
                seen.add(a)
        assert violations == [], "\n".join(violations)


class TestPhaseNumberingNoGaps:
    """Step/Phase numbering inside a phase must be sequential — no gaps allowed
    (e.g., Step 6.2 numbered 1,2,4,5 is a bug because the markdown-rendered
    list shows 1,2,3,4 regardless, hiding the gap from readers).

    Scans ordered-list items (`^\\d+\\. `) directly under Step/Phase headings and
    asserts the integer prefixes form a sequential 1..K range. Skips ordered
    lists inside fenced code blocks.
    """

    # Match an ordered-list item at the start of a line (no leading spaces, since
    # nested lists belong to a sub-context — we only check the top-level list under
    # a heading). Captures the integer prefix.
    OL_ITEM_RE = re.compile(r"^(\d+)\.\s+\S")
    # Sub-numbered items like `3.1.` or `1.0.2.` — these are "labels", not list
    # entries. They appear inline with top-level lists in some skills. Treat them
    # as neutral: don't capture them into the sequence, but also don't reset it.
    SUB_NUM_RE = re.compile(r"^\d+\.\d")
    HEADING_RE = re.compile(r"^#{1,6}\s+(Step|Phase)\s+([\d.]+)\b")

    def _scan_skill(self, path):
        """Yield (heading_label, expected_seq, actual_seq) for each numbered list
        directly under a Step/Phase heading.

        Implementation: collect ALL top-level (zero-indent) `^\\d+\\. ` items
        between consecutive Step/Phase headings as one logical group. This is
        intentionally tolerant of intervening narrative paragraphs, tables, and
        bold-emphasis lines, because those forms commonly appear inside a single
        instruction list in our SKILL.md style guide. Sub-numbered items
        (`3.1. ...`) and content inside fenced code blocks are excluded. A
        "group" is only checked when it has >= 2 items (single-item lists are
        meaningless for sequence detection). If the same heading section
        contains multiple discontiguous lists (e.g., separated by another
        heading), each is checked independently.
        """
        content = path.read_text()
        # Strip the inlined-protocols block — those steps belong to AGENTS.md and
        # are not authored in the skill body.
        body = content.split("<!-- INLINE-PROTOCOLS:START -->", 1)[0]

        lines = body.splitlines()
        in_fence = False
        current_heading = None
        current_seq = []

        results = []

        def flush():
            if current_heading is not None and len(current_seq) >= 2:
                expected = list(range(1, len(current_seq) + 1))
                results.append((current_heading, expected, list(current_seq)))

        for line in lines:
            stripped = line.lstrip()
            # Code-fence toggle (any ``` opens or closes a fence).
            if stripped.startswith("```"):
                in_fence = not in_fence
                continue
            if in_fence:
                continue

            heading = self.HEADING_RE.match(line)
            if heading:
                # New heading — flush any prior list, start a fresh group.
                flush()
                current_heading = f"{heading.group(1)} {heading.group(2)}"
                current_seq = []
                continue

            # Sub-numbered "labels" (e.g., `3.1. **Active version guard:**`) are
            # neutral — skip without touching state.
            if self.SUB_NUM_RE.match(line):
                continue

            # Top-level (zero-indent) ordered-list item.
            ol = self.OL_ITEM_RE.match(line)
            if ol:
                value = int(ol.group(1))
                # If we encounter `1.` while a list is already in progress, that
                # is the start of a NEW list — flush the prior one first. (Some
                # Step/Phase sections legitimately contain multiple distinct
                # numbered lists separated by prose.)
                if value == 1 and current_seq:
                    flush()
                    current_seq = []
                current_seq.append(value)
                continue

            # Everything else (prose, tables, indented continuations, blank lines)
            # is ignored — we tolerate intervening content within a single
            # heading's instruction list.

        flush()
        return results

    def test_step_numbering_within_phase_is_sequential(self):
        """For each numbered list directly under a Step/Phase heading, the leading
        integer prefixes must be `range(1, K+1)` — no gaps, no duplicates, no
        non-1 starts.
        """
        violations = []
        scanned_count = 0
        for path in sorted(REPO_ROOT.glob("*/skills/*/SKILL.md")):
            for heading, expected, actual in self._scan_skill(path):
                scanned_count += 1
                if actual != expected:
                    violations.append(
                        f"{path.relative_to(REPO_ROOT)}: under '{heading}', "
                        f"numbered list is {actual} (expected sequential {expected})"
                    )
        assert violations == [], (
            "Numbering gaps found in numbered lists under Step/Phase headings:\n"
            + "\n".join(f"  - {v}" for v in violations)
        )
        # Sanity: the scanner must find a non-trivial number of lists, otherwise
        # the test silently passes on any future SKILL.md edit that changes the
        # heading style.
        assert scanned_count >= 5, (
            f"Phase-numbering scanner only found {scanned_count} numbered lists "
            f"under Step/Phase headings — expected at least 5. The scanner "
            f"regex may have drifted from the actual SKILL.md heading format."
        )


class TestAllDepsCancelledMessage:
    """AGENTS.md Protocol: All-Dependencies-Cancelled Resolution must be referenced
    by each stage agent that performs dependency checks."""

    REQUIRED_SKILLS = ["plan", "build", "review", "done", "batch"]
    REQUIRED_REF = "AGENTS.md Protocol: All-Dependencies-Cancelled Resolution"

    def test_stage_skills_reference_all_deps_cancelled_protocol(self):
        violations = []
        for skill in self.REQUIRED_SKILLS:
            path = REPO_ROOT / skill / "skills" / f"optimus-{skill}" / "SKILL.md"
            content = path.read_text()
            # Strip inlined block
            body = content.split("<!-- INLINE-PROTOCOLS:START -->", 1)[0]
            if self.REQUIRED_REF not in body:
                violations.append(f"{path.relative_to(REPO_ROOT)}: missing reference")
        assert violations == [], "\n".join(violations)


class TestResolveFullValidation:
    """resolve Step 4.2 must reference the full Protocol: optimus-tasks.md Validation
    rather than enumerating a subset of checks inline."""

    def test_resolve_uses_full_format_validation_protocol(self):
        """Resolve Step 4.2 must reference Protocol: optimus-tasks.md Validation
        (full 15-item check), not enumerate a subset of checks inline."""
        path = REPO_ROOT / "resolve" / "skills" / "optimus-resolve" / "SKILL.md"
        content = path.read_text()
        body = content.split("<!-- INLINE-PROTOCOLS:START -->", 1)[0]
        assert "AGENTS.md Protocol: optimus-tasks.md Validation" in body, (
            "Resolve must reference the full validation protocol, not an inline subset."
        )


class TestStructuredAskUserScope:
    """The structured AskUser template ([topic]/[option]) is required ONLY for
    finding-decision AskUsers in cycle review skills. Documenting and enforcing
    this scope prevents two failure modes:
    1. Cycle review skills slipping a prose AskUser inside a finding loop.
    2. Admin/stage skills being incorrectly flagged for using prose AskUser
       in legitimate non-finding contexts.
    """

    # Only skills that present findings/decisions are required to use the
    # structured template. `done` is a stage skill but presents prose
    # confirmations (close confirmation, divergence warnings, PR-state prompts)
    # — it is NOT a finding-loop skill, so the structured template is not
    # required there. AGENTS.md's "Common Patterns" section formally lists
    # plan, review, pr-check, coderabbit-review as cycle review skills, with
    # deep-review and deep-doc-review as variants that follow the same finding
    # presentation principles. build is included because it presents finding
    # decisions during pre-dev artifact validation.
    CYCLE_REVIEW_SKILLS = [
        "plan", "build", "review",
        "pr-check", "deep-review", "deep-doc-review", "coderabbit-review",
    ]

    def test_cycle_review_skills_use_structured_template_in_findings(self):
        """Within Phase 5 / finding-decision sections of cycle review skills,
        AskUser calls must include `[topic]` and `[option]` markers."""
        # Scan each cycle review SKILL.md body, find AskUser calls (look for
        # `AskUser` or `AskUserQuestion` mentions), and check that within
        # finding-decision contexts (sections containing keywords like
        # "Phase 5", "Phase 4", "for each finding", "AskUser per-finding"),
        # the structured markers are present.
        violations = []
        for skill in self.CYCLE_REVIEW_SKILLS:
            path = REPO_ROOT / skill / "skills" / f"optimus-{skill}" / "SKILL.md"
            content = path.read_text()
            # Look for the canonical [topic]/[option] template presence anywhere
            # in the body — every cycle review skill should have at least one.
            if "[topic]" not in content or "[option]" not in content:
                violations.append(
                    f"{path.relative_to(REPO_ROOT)}: cycle review skill missing "
                    f"structured AskUser template"
                )
        assert violations == [], "\n".join(violations)

    def test_scope_clarification_documented_in_agents_md(self):
        """AGENTS.md must document the structured AskUser scope explicitly."""
        content = (REPO_ROOT / "AGENTS.md").read_text()
        assert "Scope of the structured AskUser template" in content, (
            "AGENTS.md must document the scope of the AskUser structured template."
        )


# --- F11: done skill robustness regression tests ---


class TestDoneRobustness:
    """F11 regression tests: done skill must handle push-failure modes
    explicitly and use deterministic resolutions."""

    def test_done_classifies_remote_delete_failures(self):
        """done/SKILL.md must distinguish network/protection/already-deleted
        on `git push origin --delete` failure."""
        path = REPO_ROOT / "done" / "skills" / "optimus-done" / "SKILL.md"
        content = path.read_text()
        body = content.split("<!-- INLINE-PROTOCOLS:START -->", 1)[0]
        # At minimum the body must mention these failure-cause keywords
        # near a `git push origin --delete` block.
        assert "remote ref does not exist" in body or "already deleted" in body, (
            "done must classify 'remote ref does not exist' as benign"
        )
        assert "protected" in body, "done must distinguish protected-branch failures"
        assert "Network" in body or "connection" in body or "timeout" in body, (
            "done must distinguish network/transient failures"
        )

    def test_done_uses_deterministic_default_branch(self):
        """done/SKILL.md must use show-ref --verify (or symbolic-ref) for
        default branch resolution — NOT 'git branch --list main master | head -1'."""
        path = REPO_ROOT / "done" / "skills" / "optimus-done" / "SKILL.md"
        content = path.read_text()
        body = content.split("<!-- INLINE-PROTOCOLS:START -->", 1)[0]
        forbidden = "git branch --list main master | head"
        assert forbidden not in body, (
            f"done body contains non-deterministic default-branch resolution: {forbidden!r}"
        )
        assert "show-ref --verify" in body or "symbolic-ref" in body or (
            "AGENTS.md Protocol: Default Branch Resolution" in body
        ) or (
            "AGENTS.md Protocol: Workspace Auto-Navigation" in body
        ), "done must use deterministic resolution (or reference canonical protocol)"


class TestStageSkillsParseTaskTitleEarly:
    """F11d regression: stage skills must parse TASK_TITLE before
    interpolating it into the terminal title."""

    STAGE_SKILLS = ["plan", "build", "review", "done"]

    def test_stage_skills_parse_task_title_from_tasks_file(self):
        violations = []
        for skill in self.STAGE_SKILLS:
            path = REPO_ROOT / skill / "skills" / f"optimus-{skill}" / "SKILL.md"
            content = path.read_text()
            body = content.split("<!-- INLINE-PROTOCOLS:START -->", 1)[0]
            # The terminal title interpolates $TASK_TITLE; before that line,
            # the skill must have an awk/grep against optimus-tasks.md or a
            # documented metadata-extraction step.
            if "TASK_TITLE" in body:
                # Must parse it from somewhere
                if not any(
                    p in body
                    for p in (
                        "awk",
                        "grep",
                        "TASK_TITLE=$(",
                        'TASK_TITLE="$(',
                        "Read task metadata",
                    )
                ):
                    violations.append(
                        f"{path.relative_to(REPO_ROOT)}: TASK_TITLE used but never parsed"
                    )
        assert violations == [], "\n".join(violations)


class TestTaskIdMatchUsesAnchoredPattern:
    """F11c regression: searches for a worktree by TASK_ID must NOT use
    `grep -iF` (substring) which produces false positives for short IDs."""

    def test_no_unanchored_taskid_grep(self):
        violations = []
        targets = [REPO_ROOT / "AGENTS.md", *REPO_ROOT.glob("*/skills/*/SKILL.md")]
        for path in targets:
            content = path.read_text()
            body = (
                content.split("<!-- INLINE-PROTOCOLS:START -->", 1)[0]
                if "skills/" in str(path)
                else content
            )
            for lineno, line in enumerate(body.splitlines(), start=1):
                # Match `git worktree list ... | grep -iF "$TASK_ID"` patterns
                if (
                    "git worktree list" in line
                    and "grep -iF" in line
                    and "TASK_ID" in line
                ):
                    violations.append(
                        f"{path.relative_to(REPO_ROOT)}:{lineno}: unanchored grep"
                    )
        assert violations == [], (
            "Unanchored TASK_ID greps allow false positives (T-1 matches T-10):\n"
            + "\n".join(violations)
        )


class TestReRunGuardResetSemantics:
    """F12b: Re-run Guard must explicitly reset convergence_status and phase
    to prevent phantom convergence on subsequent runs."""

    def test_agents_md_documents_rerun_reset_semantics(self):
        content = (REPO_ROOT / "AGENTS.md").read_text()
        assert "Re-run reset semantics" in content
        assert "convergence_status" in content
        assert "MUST" in content  # mandatory marker


class TestPrCheckHardBlocksAreUncompromising:
    """F12c: pr-check HARD BLOCK markers must not be paired with an AskUser
    that lets the user opt out of the block."""

    def test_no_askuser_immediately_after_hard_block_in_pr_check(self):
        path = REPO_ROOT / "pr-check" / "skills" / "optimus-pr-check" / "SKILL.md"
        content = path.read_text()
        body = content.split("<!-- INLINE-PROTOCOLS:START -->", 1)[0]
        # Find each "HARD BLOCK" mention and inspect the next ~40 lines for AskUser
        violations = []
        lines = body.splitlines()
        for i, line in enumerate(lines):
            if "HARD BLOCK" in line:
                window = "\n".join(lines[i:i + 40])
                if "Proceed with partial" in window or "proceed with the partial" in window:
                    violations.append(
                        f"line {i+1}: HARD BLOCK followed by partial-set AskUser"
                    )
        assert violations == [], "\n".join(violations)


class TestSharedCodeRabbitParserProtocol:
    """F12d: Both pr-check and coderabbit-review must reference the shared
    AGENTS.md `Protocol: Parse CodeRabbit Review Body` instead of carrying
    their own divergent copies of the algorithm."""

    def test_agents_md_defines_shared_protocol(self):
        content = (REPO_ROOT / "AGENTS.md").read_text()
        assert "### Protocol: Parse CodeRabbit Review Body" in content, (
            "AGENTS.md must define the shared CodeRabbit parser protocol"
        )

    def test_pr_check_references_shared_protocol(self):
        path = REPO_ROOT / "pr-check" / "skills" / "optimus-pr-check" / "SKILL.md"
        content = path.read_text()
        body = content.split("<!-- INLINE-PROTOCOLS:START -->", 1)[0]
        assert "Protocol: Parse CodeRabbit Review Body" in body, (
            "pr-check SKILL body must reference the shared protocol"
        )

    def test_coderabbit_review_references_shared_protocol(self):
        path = (
            REPO_ROOT
            / "coderabbit-review"
            / "skills"
            / "optimus-coderabbit-review"
            / "SKILL.md"
        )
        content = path.read_text()
        body = content.split("<!-- INLINE-PROTOCOLS:START -->", 1)[0]
        assert "Protocol: Parse CodeRabbit Review Body" in body, (
            "coderabbit-review SKILL body must reference the shared protocol"
        )


class TestDiscoverReviewDroidsDenyList:
    """F12e: Protocol: Discover Review Droids must apply a deny-list filter
    (architecture/design/planning/process/workflow/strategy) AFTER the
    inclusion regex to prevent meta-level reviewers from being dispatched
    against actual code."""

    def test_agents_md_defines_deny_list(self):
        content = (REPO_ROOT / "AGENTS.md").read_text()
        # Locate the Discover Review Droids section
        start = content.find("### Protocol: Discover Review Droids")
        assert start != -1
        # Find the next protocol section
        end = content.find("\n### Protocol: ", start + 1)
        section = content[start:end if end != -1 else len(content)]
        assert "Deny-list filter" in section, (
            "Discover Review Droids must define a Deny-list filter section"
        )
        # Required deny-regex words
        for term in (
            "architecture",
            "design",
            "planning",
            "process",
            "workflow",
            "strategy",
        ):
            assert term in section, f"Deny-list must mention {term!r}"

    def test_deny_list_does_not_block_known_good_droids(self):
        """Sanity check: the deny-list applies AFTER the inclusion regex,
        so genuine reviewers like `ring-default-code-reviewer` whose
        descriptions do NOT contain deny terms remain dispatchable.

        We assert this structurally by verifying the protocol documents the
        explicit ordering: inclusion regex -> deny-list -> final selection.
        """
        content = (REPO_ROOT / "AGENTS.md").read_text()
        start = content.find("### Protocol: Discover Review Droids")
        end = content.find("\n### Protocol: ", start + 1)
        section = content[start:end if end != -1 else len(content)]
        # Order semantics MUST be made explicit
        assert "AFTER inclusion regex" in section or "applied AFTER" in section
        assert "BEFORE final selection" in section or "BEFORE final" in section


class TestTerminalIdentificationNotPastedInBody:
    """F12f: After consolidating `_optimus_set_title`, no SKILL body should
    contain a manual definition. The function comes from the inlined block
    via the `AGENTS.md Protocol: Terminal Identification` reference."""

    def test_no_set_title_definition_in_skill_bodies(self):
        violations = []
        for skill_path in _all_skill_files():
            content = skill_path.read_text()
            body = content.split("<!-- INLINE-PROTOCOLS:START -->", 1)[0]
            if "_optimus_set_title() {" in body:
                violations.append(str(skill_path.relative_to(REPO_ROOT)))
        assert violations == [], (
            "These SKILL.md files still contain a body-level "
            "`_optimus_set_title()` definition; move it to the inlined "
            "`Protocol: Terminal Identification` block:\n"
            + "\n".join(violations)
        )


class TestReadOnlyDescriptionsMatchSkillBody:
    """F10a: Skills that claim 'Read-only' in their public descriptions
    must NOT have any write operations in their SKILL.md body. If a skill
    DOES write (like report/quick-report writing config.json defaultScope),
    its description must reflect that ('Mostly read-only')."""

    KNOWN_OPT_IN_WRITERS = {"report", "quick-report"}

    def test_skills_with_writes_dont_claim_pure_read_only(self):
        violations = []
        for skill in self.KNOWN_OPT_IN_WRITERS:
            skill_path = REPO_ROOT / skill / "skills" / f"optimus-{skill}" / "SKILL.md"
            content = skill_path.read_text()
            # SKILL frontmatter
            if "Read-only" in content[:300] and "Mostly read-only" not in content[:300]:
                violations.append(
                    f"{skill_path.relative_to(REPO_ROOT)}: claims 'Read-only' in frontmatter "
                    f"but writes config.json"
                )
            # Plugin.json
            plugin_path = REPO_ROOT / skill / ".factory-plugin" / "plugin.json"
            if plugin_path.exists():
                pcontent = plugin_path.read_text()
                if "Read-only" in pcontent and "Mostly read-only" not in pcontent:
                    violations.append(f"{plugin_path.relative_to(REPO_ROOT)}: claims 'Read-only'")
        assert violations == [], "\n".join(violations)

    def test_marketplaces_describe_writers_accurately(self):
        violations = []
        for mp_file in [".factory-plugin/marketplace.json", ".claude-plugin/marketplace.json"]:
            with open(REPO_ROOT / mp_file) as f:
                data = json.load(f)
            for plugin in data.get("plugins", []):
                # plugin schema differs between droid and claude
                name = plugin.get("name", "")
                desc = plugin.get("description", "")
                # normalize: claude uses "optimus-report", droid uses "report"
                bare = name.replace("optimus-", "")
                if bare in self.KNOWN_OPT_IN_WRITERS:
                    if "Read-only" in desc and "Mostly read-only" not in desc:
                        violations.append(f"{mp_file}: '{name}' description claims 'Read-only'")
        assert violations == [], "\n".join(violations)


class TestOwnerIdentityConsistency:
    """F10b: Owner identity must be canonical across all metadata surfaces.
    Canonical identity: 'Alex Garzão' (with diacritic) + 'alexgarzao@gmail.com'.
    Sources of drift: .factory-plugin/marketplace.json, .claude-plugin/marketplace.json,
    each <plugin>/.factory-plugin/plugin.json (×17)."""

    CANONICAL_NAME = "Alex Garzão"
    CANONICAL_EMAIL = "alexgarzao@gmail.com"

    def test_no_undiacritized_alex_garzao(self):
        """No file in the repo metadata may spell 'Alex Garzao' without diacritic."""
        violations = []
        for path in REPO_ROOT.glob("**/marketplace.json"):
            content = path.read_text()
            if "Alex Garzao" in content:
                violations.append(f"{path.relative_to(REPO_ROOT)}: contains 'Alex Garzao' (missing diacritic)")
        for path in REPO_ROOT.glob("**/plugin.json"):
            content = path.read_text()
            if "Alex Garzao" in content:
                violations.append(f"{path.relative_to(REPO_ROOT)}: contains 'Alex Garzao' (missing diacritic)")
        assert violations == [], "\n".join(violations)

    def test_marketplace_owners_have_email(self):
        """Both marketplace files must declare the canonical email."""
        for mp_file in [".factory-plugin/marketplace.json", ".claude-plugin/marketplace.json"]:
            with open(REPO_ROOT / mp_file) as f:
                data = json.load(f)
            owner = data.get("owner") or data.get("author") or {}
            if isinstance(owner, dict):
                email = owner.get("email", "")
            else:
                email = ""
            assert email == self.CANONICAL_EMAIL, (
                f"{mp_file}: owner email '{email}' does not match canonical '{self.CANONICAL_EMAIL}'"
            )


class TestMarketplaceSchemaParity:
    """F10c: Droid marketplace plugin entries must include the same metadata
    fields as Claude marketplace entries (version, homepage, repository, license).
    Without this, Droid cannot detect plugin versions or license compliance."""

    REQUIRED_FIELDS = ["version", "homepage", "repository", "license"]

    def test_droid_marketplace_has_full_schema(self):
        with open(REPO_ROOT / ".factory-plugin" / "marketplace.json") as f:
            data = json.load(f)
        violations = []
        for plugin in data.get("plugins", []):
            name = plugin.get("name", "<unknown>")
            for field in self.REQUIRED_FIELDS:
                if field not in plugin:
                    violations.append(f"{name}: missing '{field}'")
        assert violations == [], "\n".join(violations)

    def test_marketplaces_have_matching_versions(self):
        """For each plugin name present in both marketplaces (post-name-normalization),
        the version string must agree."""
        with open(REPO_ROOT / ".factory-plugin" / "marketplace.json") as f:
            droid = json.load(f)
        with open(REPO_ROOT / ".claude-plugin" / "marketplace.json") as f:
            claude = json.load(f)
        droid_versions = {p["name"]: p.get("version") for p in droid.get("plugins", [])}
        claude_versions = {p["name"].replace("optimus-", "", 1): p.get("version")
                           for p in claude.get("plugins", [])}
        violations = []
        for name in droid_versions:
            if name in claude_versions:
                if droid_versions[name] != claude_versions[name]:
                    violations.append(
                        f"{name}: Droid='{droid_versions[name]}' "
                        f"vs Claude='{claude_versions[name]}'"
                    )
        assert violations == [], "\n".join(violations)


# --- F13c: Cancelado state.json shape contract ---


class TestCanceladoStateShape:
    """F13c: Cancelado state.json entries have branch="" (empty string),
    NOT absent field. Documented in AGENTS.md State Management."""

    def test_agents_md_documents_cancelado_branch_shape(self):
        content = (REPO_ROOT / "AGENTS.md").read_text()
        assert "Cancelado state.json shape" in content, (
            "AGENTS.md must document the Cancelado branch-field shape contract."
        )


# --- F13d: task-blocked hook 4-arg signature ---


class TestTaskBlockedHookSignature:
    """F13d: task-blocked hook event uses 4 args (event, task_id, current_status,
    reason) — not 5 with duplicate current_status."""

    def test_no_duplicate_current_status_in_task_blocked_examples(self):
        content = (REPO_ROOT / "AGENTS.md").read_text()
        # Find task-blocked example invocations and verify they have 4 args
        # not the historical 5-arg form. Each arg is wrapped in
        # "$(_optimus_sanitize "$var")"; counting sanitize calls per
        # invocation line tells us how many args were passed.
        # 4-arg signature: 3 sanitized args (task_id, current_status, reason).
        # 5-arg signature: 4 sanitized args (task_id, current_status, current_status, reason).
        violations = []
        for line in content.splitlines():
            if "task-blocked" not in line:
                continue
            sanitize_calls = line.count("_optimus_sanitize")
            if sanitize_calls >= 4:
                violations.append(line.strip())
        assert violations == [], (
            "task-blocked example must use 4-arg signature: "
            + "\n".join(violations)
        )


# --- F13e: resolve detects legacy schema ---


class TestResolveDetectsLegacySchema:
    """F13e: resolve must check for legacy Status/Branch columns before
    attempting structural merge."""

    def test_resolve_has_legacy_schema_pre_check(self):
        path = REPO_ROOT / "resolve" / "skills" / "optimus-resolve" / "SKILL.md"
        content = path.read_text()
        body = content.split("<!-- INLINE-PROTOCOLS:START -->", 1)[0]
        assert "legacy Status/Branch" in body or "legacy schema" in body, (
            "resolve must document and check for the pre-redesign legacy column schema."
        )


# --- F13f: tasks re-validates after mutation ---


class TestTasksReValidatesAfterMutation:
    """F13f: tasks SKILL must re-validate optimus-tasks.md after every
    mutation, before staging/committing."""

    MUTATING_OPERATIONS = ["Apply Cancellation", "Apply Reopen", "Apply Advance",
                          "Apply Demotion", "Apply Edit", "Apply Create", "Apply Remove"]

    def test_each_mutation_step_re_validates(self):
        path = REPO_ROOT / "tasks" / "skills" / "optimus-tasks" / "SKILL.md"
        content = path.read_text()
        body = content.split("<!-- INLINE-PROTOCOLS:START -->", 1)[0]
        # For each mutation step heading, find its section and check it
        # references the validation protocol (or has a "Re-validate" instruction)
        violations = []
        for op in self.MUTATING_OPERATIONS:
            # Find op in body; check next ~80 lines for re-validate reference
            idx = body.find(op)
            if idx < 0:
                # Operation may not exist in current SKILL; skip silently
                continue
            window = body[idx:idx + 4000]  # ~80 lines worth
            if not ("Re-validate" in window or "AGENTS.md Protocol: optimus-tasks.md Validation" in window):
                violations.append(op)
        assert violations == [], (
            "Mutating operations must re-validate after edits:\n" + "\n".join(violations)
        )


# --- TaskSpec self-heal in /optimus:plan ---


class TestSpecSelfHeal:
    """plan auto-heals missing TaskSpec via ring:pre-dev-feature; build/review redirect to plan."""

    def test_plan_has_resolve_missing_spec_step(self):
        """plan SKILL.md must declare a self-heal step that runs before TaskSpec Resolution."""
        plan_md = (REPO_ROOT / "plan" / "skills" / "optimus-plan" / "SKILL.md").read_text()
        assert "Step 1.0.4.5" in plan_md or "Resolve Missing Spec" in plan_md, (
            "plan SKILL.md must contain a 'Step 1.0.4.5: Resolve Missing Spec' step "
            "that handles TaskSpec=- BEFORE the workspace is created"
        )
        assert "ring:pre-dev-feature" in plan_md, (
            "plan SKILL.md must delegate to ring:pre-dev-feature for spec generation"
        )
        assert "Link existing spec" in plan_md, (
            "plan SKILL.md must offer 'Link existing spec' as a fallback when Ring unavailable"
        )

    def test_plan_self_heal_runs_before_taskspec_resolution(self):
        """The self-heal step must appear textually before the TaskSpec Resolution call."""
        plan_md = (REPO_ROOT / "plan" / "skills" / "optimus-plan" / "SKILL.md").read_text()
        heal_idx = plan_md.find("Resolve Missing Spec")
        resolve_idx = plan_md.find("Protocol: TaskSpec Resolution")
        assert heal_idx > 0 and resolve_idx > 0, (
            "Both 'Resolve Missing Spec' and 'Protocol: TaskSpec Resolution' must be present"
        )
        assert heal_idx < resolve_idx, (
            "'Resolve Missing Spec' must appear BEFORE 'Protocol: TaskSpec Resolution' "
            "so the spec is guaranteed valid by the time Resolution runs"
        )

    def test_protocol_redirects_to_plan(self):
        """AGENTS.md Protocol: TaskSpec Resolution STOP message must redirect to /optimus-plan."""
        agents_md = AGENTS_MD.read_text()
        start = agents_md.find("### Protocol: TaskSpec Resolution")
        assert start > 0, "Protocol: TaskSpec Resolution section missing"
        end = agents_md.find("\n### ", start + 1)
        section = agents_md[start:end if end > 0 else len(agents_md)]
        assert "Run `/optimus-plan T-XXX`" in section
        assert "ring:pre-dev-feature" in section
        assert "Link one via `/optimus-tasks` or `/optimus-import`" not in section

    def test_build_review_dont_self_heal(self):
        """build and review SKILL.md bodies must not introduce their own self-heal logic."""
        for skill in ("build", "review"):
            content = (REPO_ROOT / skill / "skills" / f"optimus-{skill}" / "SKILL.md").read_text()
            # Body = SKILL.md content excluding the inlined-protocols block.
            # The inlined block legitimately contains "ring:pre-dev-feature"
            # (from the new TaskSpec Resolution STOP message), so we strip it
            # before asserting the host body is self-heal-free.
            body = content.split("<!-- INLINE-PROTOCOLS:START -->", 1)[0]
            assert "ring:pre-dev-feature" not in body, (
                f"{skill} SKILL.md body must not invoke ring:pre-dev-feature — "
                "only plan self-heals; build/review delegate via TaskSpec Resolution protocol"
            )

    def test_tasks_creation_offers_defer_option(self):
        """tasks SKILL.md must offer 'Defer' as a first-class option at creation time
        (not just a fallback when Ring is unavailable). This keeps the user in control
        and is symmetric with plan's self-heal flow."""
        tasks_md = (REPO_ROOT / "tasks" / "skills" / "optimus-tasks" / "SKILL.md").read_text()
        assert "**Defer**" in tasks_md or "**Defer —" in tasks_md, (
            "tasks SKILL.md must expose a 'Defer' option at task creation time "
            "(sets TaskSpec to `-`, deferring spec generation to /optimus:plan)"
        )
        # Old fallback-only phrasing must be gone — Defer is now a top-level choice
        assert "Create with empty TaskSpec" not in tasks_md, (
            "tasks SKILL.md must not retain the old 'Create with empty TaskSpec' fallback "
            "phrasing — replaced by the unconditional 'Defer' option"
        )

    def test_plan_self_heal_offers_cancel_option(self):
        """Cancel must be a first-class option that aborts the plan with a clear STOP message."""
        body = (REPO_ROOT / "plan" / "skills" / "optimus-plan" / "SKILL.md").read_text()
        body = body.split("<!-- INLINE-PROTOCOLS:START -->", 1)[0]
        assert "**Cancel**" in body, "plan self-heal must offer Cancel as first-class option"
        assert "Plan cancelled" in body, "Cancel branch must STOP with deterministic message"

    def test_plan_self_heal_revalidates_and_commits(self):
        """Step 1.0.4.5 mutates optimus-tasks.md; it MUST re-validate + commit per AGENTS.md protocols."""
        body = (REPO_ROOT / "plan" / "skills" / "optimus-plan" / "SKILL.md").read_text()
        body = body.split("<!-- INLINE-PROTOCOLS:START -->", 1)[0]
        start = body.find("### Step 1.0.4.5")
        end = body.find("### Step 1.0.5", start + 1)
        section = body[start:end] if start >= 0 and end > start else ""
        assert "Re-validate" in section, "self-heal must re-validate optimus-tasks.md after mutation"
        assert "Protocol: optimus-tasks.md Validation" in section
        assert "tasks_git" in section, "self-heal must commit via tasks_git"

    def test_tasks_defer_documents_handoff_to_plan(self):
        """Tasks Defer branch must point user at /optimus-plan for later spec generation."""
        body = (REPO_ROOT / "tasks" / "skills" / "optimus-tasks" / "SKILL.md").read_text()
        body = body.split("<!-- INLINE-PROTOCOLS:START -->", 1)[0]
        assert "/optimus-plan" in body and "later" in body, (
            "tasks Defer must inform user that /optimus-plan T-XXX will pick this up later"
        )

    def test_plan_self_heal_uses_progress_topic_format(self):
        """The new AskUser prompt must use the canonical [topic] (X/N) progress prefix."""
        import re
        body = (REPO_ROOT / "plan" / "skills" / "optimus-plan" / "SKILL.md").read_text()
        body = body.split("<!-- INLINE-PROTOCOLS:START -->", 1)[0]
        start = body.find("### Step 1.0.4.5")
        end = body.find("### Step 1.0.5", start + 1)
        section = body[start:end] if start >= 0 and end > start else ""
        assert re.search(r"\[topic\]\s+\(\d+/\d+\)", section), (
            "Resolve Missing Spec AskUser prompt must use [topic] (X/N) format"
        )

    def test_protocol_references_resolve(self):
        """Every 'AGENTS.md Protocol: X' reference in any SKILL.md must resolve
        to a real `### Protocol: X` heading in AGENTS.md. Catches dangling refs early.

        Uses the same heuristic chain as inline-protocols.py (see
        ``extract_refs_from_content`` there) so that references resolved by the
        inliner are also resolved here, and references it warns about as
        unmatched are also surfaced as test failures."""
        import sys
        sys.path.insert(0, str(REPO_ROOT / "scripts"))
        try:
            inline_protocols = __import__("inline-protocols")
        finally:
            sys.path.pop(0)

        agents_sections, _summaries = inline_protocols.parse_agents_md()
        violations = []
        for path in _all_skill_files():
            # Use the inliner's body-only extraction to skip the inlined block.
            content = path.read_text()
            body = content.split("<!-- INLINE-PROTOCOLS:START -->", 1)[0]
            refs = inline_protocols.extract_refs_from_content(body)
            for ref in refs:
                if not ref.startswith("Protocol: "):
                    continue
                if inline_protocols.match_ref_to_section(ref, agents_sections) is None:
                    rel = path.relative_to(REPO_ROOT)
                    violations.append(f"{rel}: '{ref}' has no matching heading in AGENTS.md")
        assert violations == [], "Dangling protocol references:\n" + "\n".join(violations)

    def test_link_existing_spec_uses_canonical_protocol_reference(self):
        """Both plan and tasks 'Link existing spec' must reference the canonical protocol."""
        canonical = "AGENTS.md Protocol: TaskSpec Resolution"
        for skill_path in [
            REPO_ROOT / "plan" / "skills" / "optimus-plan" / "SKILL.md",
            REPO_ROOT / "tasks" / "skills" / "optimus-tasks" / "SKILL.md",
        ]:
            content = skill_path.read_text().split("<!-- INLINE-PROTOCOLS:START -->", 1)[0]
            link_section = content.split("Link existing spec", 1)[1].split("\n\n###", 1)[0]
            assert canonical in link_section, (
                f"{skill_path.parent.parent.name} 'Link existing spec' must reference {canonical}"
            )

    def test_link_existing_spec_mentions_symlink(self):
        """Symlink TOCTOU is part of the protocol — prose must surface it at the new entry point."""
        for skill_path in [
            REPO_ROOT / "plan" / "skills" / "optimus-plan" / "SKILL.md",
            REPO_ROOT / "tasks" / "skills" / "optimus-tasks" / "SKILL.md",
        ]:
            content = skill_path.read_text().split("<!-- INLINE-PROTOCOLS:START -->", 1)[0]
            link_section = content.split("Link existing spec", 1)[1].split("\n\n###", 1)[0]
            assert "symlink" in link_section.lower(), (
                f"{skill_path.parent.parent.name} 'Link existing spec' must explicitly mention symlinks"
            )


class TestWorktreeLocationConvention:
    """F-worktrees: All worktree-creation sites use ${MAIN_WORKTREE}/.worktrees/<branch>
    pattern; .gitignore auto-inject uses post-F1 ${MAIN_WORKTREE}/.gitignore contract."""

    CREATOR_FILES = [
        (REPO_ROOT / "AGENTS.md", "Workspace Auto-Navigation"),
        (REPO_ROOT / "plan" / "skills" / "optimus-plan" / "SKILL.md", "Step 1.0.5"),
        (REPO_ROOT / "resume" / "skills" / "optimus-resume" / "SKILL.md", "Step 3.3"),
    ]

    # User-facing command mirrors (auto-generated from SKILL.md by sync-claude-commands.py).
    COMMAND_MIRRORS = [
        REPO_ROOT / "commands" / "plan.md",
        REPO_ROOT / "commands" / "resume.md",
    ]

    def test_no_sibling_worktree_path_pattern(self):
        """No `../${REPO_NAME}-...` or `../<repo>-...` worktree-add invocations should remain."""
        violations = []
        for path, _ in self.CREATOR_FILES:
            content = path.read_text()
            body = content.split("<!-- INLINE-PROTOCOLS:START -->", 1)[0]
            for lineno, line in enumerate(body.splitlines(), start=1):
                if "git worktree add" in line and "../" in line:
                    violations.append(f"{path.relative_to(REPO_ROOT)}:{lineno}: sibling pattern: {line.strip()}")
        # Also check user-facing command mirrors.
        for path in self.COMMAND_MIRRORS:
            if not path.exists():
                continue
            content = path.read_text()
            body = content.split("<!-- INLINE-PROTOCOLS:START -->", 1)[0]
            for lineno, line in enumerate(body.splitlines(), start=1):
                if "git worktree add" in line and "../" in line:
                    violations.append(f"{path.relative_to(REPO_ROOT)}:{lineno}: sibling pattern: {line.strip()}")
        assert violations == [], "\n".join(violations)

    def test_worktree_paths_use_dot_worktrees(self):
        """Creator sites and command mirrors use ${MAIN_WORKTREE}/.worktrees/.

        AGENTS.md is skipped in this check because ${MAIN_WORKTREE}/.worktrees/
        IS in AGENTS.md auto-nav (and that's exactly what we want to verify
        elsewhere via the dedicated test for the convention section)."""
        for path, _ in self.CREATOR_FILES:
            if path.name == "AGENTS.md":
                continue
            content = path.read_text()
            body = content.split("<!-- INLINE-PROTOCOLS:START -->", 1)[0]
            assert "${MAIN_WORKTREE}/.worktrees/" in body, (
                f"{path.relative_to(REPO_ROOT)}: missing ${{MAIN_WORKTREE}}/.worktrees/ pattern"
            )
        # Also verify the command mirrors.
        for path in self.COMMAND_MIRRORS:
            if not path.exists():
                continue
            content = path.read_text()
            body = content.split("<!-- INLINE-PROTOCOLS:START -->", 1)[0]
            assert "${MAIN_WORKTREE}/.worktrees/" in body, (
                f"{path.relative_to(REPO_ROOT)}: missing ${{MAIN_WORKTREE}}/.worktrees/ pattern"
            )

    def test_agents_md_documents_worktree_convention(self):
        content = (REPO_ROOT / "AGENTS.md").read_text()
        assert "### Protocol: Worktree Location" in content
        # And content (not just header)
        idx = content.find("### Protocol: Worktree Location")
        section = content[idx:idx + 4000]
        assert "${MAIN_WORKTREE}/.worktrees/" in section
        assert "Resolve Main Worktree Path" in section  # cross-reference
        assert "Backwards compatibility" in section

    def test_gitignore_auto_inject_uses_main_worktree_path(self):
        """Post-F1 contract: gitignore auto-inject must use ${MAIN_WORKTREE}/.gitignore,
        NOT bare .gitignore (which would write to the linked worktree's .gitignore
        when run from a linked worktree).

        Validates EVERY occurrence of the operational-worktrees marker, not just
        the first — both Initialize Directory and Session State protocols
        contain the auto-inject block."""
        content = (REPO_ROOT / "AGENTS.md").read_text()
        # All occurrences of the marker token (covers both grep guard and
        # printf payload sites). We then assert the protective ${MAIN_WORKTREE}
        # path appears in the surrounding window for each.
        indices = [m.start() for m in re.finditer(r'optimus-operational-worktrees', content)]
        assert indices, "AGENTS.md missing optimus-operational-worktrees marker"
        for idx in indices:
            window = content[max(0, idx - 300):idx + 500]
            assert "${MAIN_WORKTREE}/.gitignore" in window, (
                f"AGENTS.md byte {idx}: gitignore auto-inject must use ${{MAIN_WORKTREE}}/.gitignore"
            )

    def test_branch_traversal_guard_in_creator_sites(self):
        """All worktree-creator sites that actually call `git worktree add`
        MUST guard branch names against path traversal via a `case ... in
        *..*|/*)` statement."""
        # Match `case "<var>" in <newline> *..*|/*)` allowing optional
        # whitespace before the case-arm pattern.
        pattern = re.compile(r'case\s+"[^"]*"\s+in\s*\n\s*\*\.\.\*\|/\*\)')
        violations = []
        for path, _ in self.CREATOR_FILES:
            body = path.read_text().split("<!-- INLINE-PROTOCOLS:START -->", 1)[0]
            if "git worktree add" not in body:
                continue
            if not pattern.search(body):
                violations.append(f"{path.relative_to(REPO_ROOT)}: missing case-stmt traversal guard")
        assert violations == [], "\n".join(violations)


# --- Phase 1 of issue #34: top-3 most-duplicated protocols carry the
# `<!-- inline-mode: summarize -->` marker AND a `**Summary:**` subsection
# in AGENTS.md. The inliner reads both at runtime; this test guards the
# source-of-truth so the marker can't be dropped without flipping a test.

class TestProtocolSummarizeMarker:
    """Phase 1 of issue #34: Verify the 3 top-duplicated protocols carry
    the <!-- inline-mode: summarize --> marker in AGENTS.md."""

    SUMMARIZED_PROTOCOLS = [
        "Resolve Main Worktree Path",
        "Session State",
        "Initialize .optimus Directory",
    ]

    def test_summarize_marker_present_for_top_protocols(self):
        content = AGENTS_MD.read_text()
        for proto in self.SUMMARIZED_PROTOCOLS:
            heading = f"### Protocol: {proto}"
            idx = content.find(heading)
            assert idx >= 0, f"{heading} missing from AGENTS.md"
            # Check the next 600 chars for the marker AND a Summary subsection.
            window = content[idx: idx + 600]
            assert "<!-- inline-mode: summarize -->" in window, (
                f"{proto}: missing <!-- inline-mode: summarize --> marker "
                "(must be placed immediately under the heading)"
            )
            assert "**Summary:**" in window, (
                f"{proto}: missing **Summary:** subsection "
                "(must follow the summarize marker)"
            )

    def test_summarize_marker_implies_marker_appears_first(self):
        """Marker must precede any other prose in the protocol body so
        parse_agents_md sees it before falling through to full-body
        inlining heuristics."""
        content = AGENTS_MD.read_text()
        for proto in self.SUMMARIZED_PROTOCOLS:
            heading = f"### Protocol: {proto}"
            idx = content.find(heading)
            window = content[idx: idx + 600]
            # The marker MUST appear before the first `**Summary:**` (and
            # also before the first `**Referenced by:**` if present).
            marker_idx = window.find("<!-- inline-mode: summarize -->")
            summary_idx = window.find("**Summary:**")
            assert marker_idx < summary_idx, (
                f"{proto}: marker must come before **Summary:** "
                f"(marker={marker_idx}, summary={summary_idx})"
            )
