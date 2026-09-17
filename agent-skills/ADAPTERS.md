# Agent adapters

The four skill directories define the canonical workflows. Keep their behavior and
the shared Memento contract unchanged when adapting them to a specific agent.

## Codex

Install each skill directory in the configured Codex skills location and keep the
shared `references/memento-contract.md` reachable at the relative path used by
the skills. Configure Research Library as a remote Streamable HTTP MCP server.

## Cursor

Expose each workflow as a separate project or user rule. Preserve its narrow
trigger: find context, record durable knowledge, checkpoint incomplete work, or
resume work. The rule should call the same two MCP tools and must retain the
non-mutating Git constraints.

## Claude Code

Expose each workflow as a separate skill or command supported by the local Claude
Code configuration. Preserve the canonical payload fields and idempotency rules.

## Shared requirements

- Connect to the Research Library `/mcp` endpoint as an external client.
- Authenticate with the project-scoped MCP token.
- Do not install the agent inside Research Library.
- Do not add document-level ACL behavior in an adapter.
- Do not duplicate Linear task ownership or Git history in agent-local memory.
