# Phase 10: Batch Operations

Loaded when the user requests several operations in one invocation. Apply each in sequence, validating after each step.

If the user provides multiple tasks to create at once (e.g., a list of tasks), process them sequentially:

1. Generate IDs for all tasks first (to allow cross-references in dependencies)
2. Validate all dependencies
3. Add all rows to optimus-tasks.md
4. Show summary of all created tasks

