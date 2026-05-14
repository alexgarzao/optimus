---
description: Resolves merge conflicts in optimus-tasks.md caused by parallel structural edits. Since status and branch data live in state.json (gitignored), optimus-tasks.md conflicts are rare — they only occur when structural changes (new tasks, dependency edits, version moves) happen concurrently. This skill detects, parses, and resolves those conflicts — each task's row is independent.
---

Invoke the `optimus-resolve` skill. Arguments: $ARGUMENTS
