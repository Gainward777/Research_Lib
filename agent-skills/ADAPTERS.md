# Agent adapters

`library-development-workflow` is the default entry point. It automatically
coordinates the four specialist skill directories. Keep their behavior and the
shared Memento contract unchanged when adapting them to a specific agent.

## Codex

Install the complete `agent-skills` tree in the configured Codex skills location,
enable implicit invocation for `library-development-workflow`, and keep the
shared `references/memento-contract.md` reachable at the relative path used by
the skills. Configure Research Library as a remote Streamable HTTP MCP server.

## Cursor

Expose the coordinator as an always-applicable project rule and the four
specialist workflows as referenced rules. Preserve their narrow triggers: find
context, record durable knowledge, checkpoint incomplete work, or resume work.
The rules should call the same two MCP tools and must retain the non-mutating Git
constraints.

## Claude Code

Expose the coordinator as an automatically applicable skill and keep each
specialist workflow available to it. Preserve the canonical payload fields and
idempotency rules.

## Shared requirements

- Connect to the Research Library `/mcp` endpoint as an external client.
- Authenticate with the project-scoped MCP token.
- Let the coordinator select lifecycle actions; developers do not manually
  trigger the four specialist workflows.
- Do not install the agent inside Research Library.
- Do not add document-level ACL behavior in an adapter.
- Do not duplicate Linear task ownership or Git history in agent-local memory.
