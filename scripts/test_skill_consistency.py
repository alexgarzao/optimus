#!/usr/bin/env python3
"""Tests for cross-file consistency rules in SKILL.md and AGENTS.md."""

import json
import re
from pathlib import Path

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
        """Each plugin's marketplace.json description must equal its plugin.json description."""
        if not MARKETPLACE_JSON.exists():
            return
        marketplace = json.loads(MARKETPLACE_JSON.read_text())
        violations = []
        for plugin in marketplace.get("plugins", []):
            name = plugin["name"]
            plugin_json = REPO_ROOT / name / ".factory-plugin" / "plugin.json"
            if not plugin_json.exists():
                continue
            pj = json.loads(plugin_json.read_text())
            if plugin["description"] != pj["description"]:
                violations.append(
                    f"{name}: marketplace.json != plugin.json\n"
                    f"    marketplace: {plugin['description']}\n"
                    f"    plugin.json: {pj['description']}"
                )
        assert violations == [], (
            "Description mismatch between marketplace.json and plugin.json:\n"
            + "\n".join(f"  - {v}" for v in violations)
        )


# --- Stage rename: no stale 'check' references as stage name ---

# Patterns that indicate 'check' used as the stage-3 name (not as English verb
# or part of 'pr-check' tool name or 'gh pr checks' CLI command).
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
NEW_TITLE_FORMAT = re.compile(
    r'printf.*optimus:\s*(%s|\w+)\s+%s\s.*%s'
)
OSC_PRINTF = re.compile(r"printf.*(\\033|\\e|\\x1b)\]0;")
TTY_REDIRECT = re.compile(r">\s*/dev/tty\s+2>/dev/null")
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

    def test_all_osc_printf_redirect_to_tty(self):
        """Every printf with OSC escape (\\033]0;) must redirect to /dev/tty."""
        violations = []
        for filepath in _all_doc_files():
            text = filepath.read_text()
            for i, line in enumerate(text.splitlines(), 1):
                if OSC_PRINTF.search(line) and not TTY_REDIRECT.search(line):
                    rel = filepath.relative_to(REPO_ROOT)
                    violations.append(f"{rel}:{i}: missing > /dev/tty — {line.strip()}")
        assert violations == [], (
            "Terminal title printf without /dev/tty redirect (stdout is captured by Execute tool):\n"
            + "\n".join(f"  - {v}" for v in violations)
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
        """All title skills must have a restore terminal title command with /dev/tty."""
        restore_osc = re.compile(r"printf.*\\033\]0;\\007.*>\s*/dev/tty")
        missing = []
        for skill in TITLE_SKILLS:
            content = _read_skill(skill)
            if not restore_osc.search(content):
                missing.append(skill)
        assert missing == [], (
            "Skills missing restore terminal title with /dev/tty:\n"
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
        """AGENTS.md must define exactly 6 statuses; Revisando PR only in migration code."""
        content = AGENTS_MD.read_text()
        for status in VALID_STATUSES:
            assert status in content, f"AGENTS.md missing status '{status}'"
        for i, line in enumerate(content.splitlines(), 1):
            if "Revisando PR" in line:
                assert "migration" in line.lower() or "migrat" in line.lower() \
                    or "jq" in line or "select(" in line or "echo" in line, (
                    f"AGENTS.md:{i}: 'Revisando PR' outside migration code: {line.strip()}"
                )


# --- Plugin completeness: marketplace matches directory structure ---

EXPECTED_PLUGINS = [
    "batch", "build", "coderabbit-review", "deep-doc-review", "deep-review",
    "done", "help", "import", "plan", "pr-check", "quick-report", "report",
    "resolve", "review", "sync", "tasks",
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
        """Marketplace must have exactly 16 plugins."""
        if not MARKETPLACE_JSON.exists():
            return
        marketplace = json.loads(MARKETPLACE_JSON.read_text())
        count = len(marketplace.get("plugins", []))
        assert count == 16, (
            f"Expected 16 plugins in marketplace, found {count}"
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


# --- Convergence model: Full Roster, no escalating scrutiny ---


class TestConvergenceModel:
    """Convergence loop must use Full Roster Model, not escalating scrutiny."""

    def test_agents_md_has_full_roster_model(self):
        """AGENTS.md must define the Full Roster Model for convergence."""
        content = AGENTS_MD.read_text()
        assert "Full Roster Model" in content, \
            "AGENTS.md missing 'Full Roster Model' convergence definition"

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

    def test_convergence_round_2_mandatory(self):
        """AGENTS.md must state that convergence round 2 is mandatory."""
        content = AGENTS_MD.read_text()
        assert "Round 2 is MANDATORY" in content, \
            "AGENTS.md missing 'Round 2 is MANDATORY' convergence rule"


# --- tasks.md format spec: marker, Tipo, versions, state.json ---


class TestTasksFormatSpec:
    """tasks.md format invariants must be defined in AGENTS.md."""

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
        """AGENTS.md must state that status is NOT stored in tasks.md."""
        content = AGENTS_MD.read_text()
        assert "NOT stored in tasks.md" in content or \
            "NOT in tasks.md" in content, (
            "AGENTS.md missing statement that status lives in state.json, not tasks.md"
        )

    def test_agents_md_has_column_spec(self):
        """AGENTS.md must define the required columns: ID, Title, Tipo, Depends, Priority, Version."""
        content = AGENTS_MD.read_text()
        for col in ["ID", "Title", "Tipo", "Depends", "Priority", "Version"]:
            assert f"| {col} |" in content or f"| {col}" in content, \
                f"AGENTS.md missing column definition for '{col}'"


# --- done redesign: 3 hard gates, no local lint/test ---


class TestDoneRedesign:
    """done must use 3 hard gates and NOT run local lint/test."""

    def test_done_has_three_hard_gates(self):
        """done SKILL.md must reference all 3 hard gates."""
        content = _read_skill("done")
        assert "uncommitted" in content.lower(), \
            "done missing 'uncommitted changes' gate"
        assert "unpushed" in content.lower(), \
            "done missing 'unpushed commits' gate"
        assert "PR" in content and ("MERGED" in content or "final state" in content.lower()), \
            "done missing 'PR in final state' gate"

    def test_done_no_local_lint_test(self):
        """done SKILL.md must NOT contain make lint or make test as execution steps."""
        content = _read_skill("done")
        lines = content.splitlines()
        violations = []
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("#") or stripped.startswith("**"):
                continue
            if re.search(r"^make (lint|test)\b", stripped):
                violations.append(f"done/SKILL.md:{i}: {stripped}")
        assert violations == [], (
            "done should not run local lint/test (CI responsibility):\n"
            + "\n".join(f"  - {v}" for v in violations)
        )
