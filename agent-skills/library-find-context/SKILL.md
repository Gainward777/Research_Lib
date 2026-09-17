---
name: library-find-context
description: Find prior implementation knowledge, decisions, bugs, tests, and checkpoints in Research Library from a free-form development task or bug description.
---

# Find Library Context

Read [the Memento contract](../references/memento-contract.md) before the first
MCP call.

Use this skill when development work needs historical or cross-repository context,
including when the user knows only a verbal bug description. Do not require a
historical Linear issue, file, symbol, or commit.

1. Preserve the user's description as the core search query. Add known technical
   terms only when they come from the repository or task, not speculation.
2. Determine project and repository from the current workspace when possible.
3. Call `library_get_context`. Pass the current Linear ID if known, but do not use
   it as a substitute for the descriptive query.
4. Present only non-empty response blocks. Keep source IDs, slugs, Git references,
   and verification states attached to each conclusion.
5. Distinguish stored facts from your inference. If nothing is found, say so and
   continue with local investigation.

This skill is read-only. It does not publish context or modify Git, Linear, or the
workspace.
