# Security Model

Optimus is a marketplace of skills for AI coding assistants. Skills execute bash
protocols from AGENTS.md against local project repositories. This document describes
the threat model, trust boundaries, and mitigations in place.

## Trust Boundaries

| Boundary | Trust Level | Reason |
|---|---|---|
| Project source code | Trusted (user's own code) | User controls the repo |
| AGENTS.md protocols | Trusted | Shipped by Optimus; reviewed in PRs |
| SKILL.md files | Trusted | Same as AGENTS.md |
| `.optimus/config.json` | **Partially untrusted** | Gitignored per-user; could be tampered by local attacker, received via Slack/email, or cloned from a malicious fork |
| `optimus-tasks.md` content | **Partially untrusted** | Versioned — any contributor can add rows. Malicious values in `TaskSpec` column could attempt path traversal |
| Ring pre-dev specs (`<tasksDir>/tasks/*.md`) | **Partially untrusted** | Same as optimus-tasks.md |
| Environment variables | Trusted | User controls them |

## Attack Scenarios and Mitigations

### S1: Malicious `tasksDir` in config.json (git option injection)

**Attack:** An attacker sends or commits a `.optimus/config.json` with
`"tasksDir": "--exec-path=/tmp/evil"`. When `tasks_git` runs
`git -C "$TASKS_DIR"`, git interprets the value as a global option and can execute
attacker-controlled code.

**Mitigation:** `Protocol: Resolve Tasks Git Scope` validates `TASKS_DIR` does not
start with `-` and rejects the value with `exit 1`.

### S2: TaskSpec path traversal

**Attack:** A malicious `TaskSpec` value like `../../../etc/passwd` attempts to read
files outside the Ring pre-dev tree.

**Mitigation:** `Protocol: TaskSpec Resolution` resolves the full path via
`realpath`/`os.path.realpath` and verifies it starts with `$TASKS_DIR_ABS`. Symlinks
are rejected outright to prevent TOCTOU attacks.

### S3: Symlink attack during rename

**Attack:** Attacker creates `<tasksDir>/tasks.md` (or its rename target
`<tasksDir>/optimus-tasks.md`) as a symlink to a sensitive file. The rename would
move/overwrite the sensitive target via the symlinked path.

**Mitigation:** `Protocol: Rename tasks.md to optimus-tasks.md` rejects with `exit 1`
if either source or destination is a symlink, refusing to inspect or rename symlinked
paths.

### S4: Branch name injection in divergence checks

**Attack:** A malicious ref name with shell metacharacters
(`--no-index;rm -rf ~/`) could be interpolated into git commands.

**Mitigation:** `Protocol: Resolve Tasks Git Scope` validates `TASKS_DEFAULT_BRANCH`
against the regex `^[a-zA-Z0-9._/-]+$` and rejects invalid values.

### S5: tasksDir pointing to attacker-controlled repo

**Attack:** An attacker convinces the user to set `tasksDir` to a repo they control,
then loads malicious task specs.

**Mitigation (partial):** Users must explicitly configure `tasksDir`. The default
(`docs/pre-dev`) is always inside the project repo. Documentation warns users to
only point `tasksDir` at repos they trust.

**Residual risk:** If the user is tricked into setting a malicious `tasksDir`, they
are effectively loading untrusted content as task specs. This is comparable to
cloning an untrusted git repo — the user's responsibility.

### S6: Commit message injection

**Attack:** A task title containing backticks or `$()` could be interpolated into
a shell command and executed.

**Mitigation:** All commit messages are written to temp files via `$(mktemp)` and
committed with `git commit -F` (never `-m` with interpolated strings). Temp files
use restrictive permissions (`chmod 600`).

### S7: Hook argument injection

**Attack:** A hook receives `event task_id old_status new_status` as arguments. A
malicious task title could inject shell code if the hook uses `eval`.

**Mitigation:** Hook scripts are documented as MUST NOT use `eval` with their
arguments. The `_optimus_sanitize()` function restricts arguments to alphanumeric,
space, hyphen, underscore, and colon — no `.` or `/` (path traversal vectors).

## What Optimus Does NOT Protect Against

- **Malicious project code**: If the user's project itself contains malicious code,
  Optimus does nothing special. Running any AI assistant against untrusted code is
  risky.
- **Malicious ring droids**: Ring droids are trusted components. Users must install
  them from reputable sources.
- **Local filesystem attacks**: An attacker with local filesystem access can tamper
  with `.optimus/state.json`, session files, etc. Optimus trusts the local filesystem
  permissions.
- **Network attacks**: Optimus uses `git fetch` from `origin`. If DNS/network is
  compromised, cloned repos may contain malicious content.

## Reporting Security Issues

If you find a security issue in Optimus, please open a GitHub issue with the
label `security`. Do NOT include exploit details in public issues — send those
via email to the maintainer.
