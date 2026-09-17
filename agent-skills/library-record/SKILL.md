---
name: library-record
description: Publish a durable development decision, confirmed problem, implementation snapshot, or test result to Research Library.
---

# Record Development Context

Read [the Memento contract](../references/memento-contract.md) before publishing.

Use this skill after a meaningful development fact becomes durable. Do not publish
routine commands, transient exploration, complete conversations, or duplicated
task status.

1. Select the narrowest context kind:
   `decision`, `problem`, `implementation_snapshot`, or `test_evidence`.
2. Use the Linear ID as `work_item` when known. Otherwise reuse a stable
   `work_context_id` for this work stream.
3. Record the reason for a decision, the reproduction evidence for a problem, or
   the exact command and observed result for test evidence.
4. Attach repository, branch, commit, and affected paths only when known.
5. Leave verification `unverified` unless CI or a human actually verified it.
6. If correcting a prior record, publish a new one with its
   `supersedes_item_id`.
7. Call `library_publish_context` with a stable idempotency key.

Never publish secrets, hidden reasoning, raw chat logs, or source code that belongs
in Git. This skill does not commit, push, modify Linear, or change the workspace.
