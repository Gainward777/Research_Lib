---
name: library-checkpoint
description: Save resumable state for incomplete development work before pausing, rotating developers, or switching to another task.
---

# Save Development Checkpoint

Read [the Memento contract](../references/memento-contract.md) before publishing.

Use this skill when incomplete work must be resumed later. A checkpoint is not a
task assignment and does not replace Linear.

Inspect Git state read-only and prepare concise content containing:

- completed work;
- decisions already applied;
- tests executed and their observed results;
- blockers and unresolved questions;
- precise next steps;
- branch, HEAD commit, and whether the working tree is dirty.

Publish it as `context_kind=checkpoint` with the current `work_item` or stable
`work_context_id`. Include affected paths when useful. If it replaces an earlier
checkpoint, set `supersedes_item_id`.

Do not claim that uncommitted work can be recovered by another developer. State
clearly that it exists and where, but do not commit, stash, push, or switch
branches without explicit user authorization.
