---
name: library-resume
description: Resume paused development work from its latest checkpoint and relevant GBrain history without changing Git or Linear.
---

# Resume Development Work

Read [the Memento contract](../references/memento-contract.md) before querying.

Use this skill when returning to an existing Linear issue or temporary work
context.

1. Build a descriptive query from the current task goal, bug report, or checkpoint
   request. Do not query by identifier alone.
2. Call `library_get_context` with the project, repository, and current work item
   when known.
3. Identify the most recent relevant checkpoint and combine it with related
   implementations, decisions, problems, and test evidence returned by GBrain.
4. Compare stored branch and commit references with the current workspace. Report
   divergence or a dirty tree; do not silently switch or modify Git state.
5. Produce a short resumption brief: last confirmed state, applicable decisions,
   remaining work, blockers, and the next safe action.

Do not assume that an empty block proves the absence of history. This skill is
read-only and does not publish a new checkpoint.
