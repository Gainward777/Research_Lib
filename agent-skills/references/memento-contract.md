# Memento MCP contract

Research Library is shared development memory, not a task tracker or source-code
repository. Linear owns tasks and assignments. Git owns code and history.

## Read context

Call `library_get_context` with:

```json
{
  "query": "free-form description of the task, bug, or question",
  "project": "project-slug",
  "repository": "optional-repository-slug",
  "work_item": "optional-current-Linear-ID",
  "limit": 20
}
```

Only `query` is required. Do not require the user to know the historical task,
file, symbol, or commit that introduced a feature. GBrain searches the stored
development history semantically. Project and repository narrow the corpus;
`work_item` identifies the current work but does not restrict history to that ID.

The response contains fixed blocks:

- `related_implementations`;
- `decisions`;
- `known_problems`;
- `tests_and_evidence`;
- `checkpoints`.

Treat empty blocks as “not found”, not as proof that no such context exists. Cite
`item_id`, `slug`, commit, paths, and work item when reporting a result.

## Publish context

Call `library_publish_context` with:

```json
{
  "payload": {
    "context_kind": "decision",
    "project": "project-slug",
    "repository": "optional-repository-slug",
    "work_item": "optional-Linear-ID",
    "work_context_id": "required only when work_item is absent",
    "title": "short factual title",
    "content": "durable context",
    "summary": "optional retrieval summary",
    "branch": "optional branch",
    "commit": "optional commit SHA",
    "paths": ["optional/affected/path"],
    "created_by": "agent",
    "verification": "unverified",
    "tags": [],
    "supersedes_item_id": null,
    "consulted_context_item_ids": ["lib_optional_source"]
  },
  "idempotency_key": "stable retry key"
}
```

Allowed context kinds:

- `decision` — a selected option and its reason;
- `checkpoint` — resumable state of incomplete work;
- `implementation_snapshot` — confirmed state of an implemented feature;
- `problem` — a reproduced defect, limitation, or blocker;
- `test_evidence` — an executed check and its observed result.

At least one of `work_item` and `work_context_id` is required. Prefer an existing
Linear ID. When none exists, use a stable temporary context ID and keep using it
for the same work stream.

Verification values:

- `unverified`;
- `ci-verified`;
- `human-approved`.

Do not mark content as CI-verified or human-approved without corresponding
evidence. A record is immutable. To correct one, publish a new record with
`supersedes_item_id`; never rewrite history.

When the new record relies on context returned by `library_get_context`, include
the actually used item IDs in `consulted_context_item_ids`. The library validates
them, stores them in frontmatter, and creates durable `has-source` relations.
Do not include merely retrieved but unused items.

Use the same idempotency key when retrying the exact same payload. Use a new key
when the payload changes.

## Never publish

- API keys, tokens, passwords, private keys, or credentials;
- hidden chain-of-thought or internal model reasoning;
- complete chat or terminal history;
- speculative claims presented as confirmed facts;
- code contents that should live in Git;
- task ownership or assignment, which belongs in Linear.

Skills may inspect Git state read-only. They must not commit, push, stash, switch
branches, or change Linear without explicit user authorization.
