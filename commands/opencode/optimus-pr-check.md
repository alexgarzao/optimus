---
description: Standalone PR review orchestrator. Fetches PR metadata, collects ALL review comments (Codacy, DeepSource, CodeRabbit, human reviewers), dispatches parallel agents to evaluate code and comments, presents findings interactively, applies fixes with TDD cycle and separate commits per finding, responds to every comment thread with commit reference or justification, and adds inline suppression tags for Codacy/DeepSource when a finding won't be fixed.
---

Invoke the `optimus-pr-check` skill. Arguments: $ARGUMENTS
