class EnrichmentService:
    async def enrich(self, title: str, content: str) -> dict[str, object]:
        """Deterministic MVP enrichment; replaceable with a bounded LLM client."""
        summary = content.strip().replace("\n", " ")[:500]
        return {"title": title.strip()[:300], "summary": summary, "tags": []}
