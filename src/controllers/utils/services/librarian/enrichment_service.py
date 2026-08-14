class EnrichmentService:
    async def enrich(self, title: str, content: str) -> dict[str, object]:
        """Deterministic bounded enrichment for stored material."""
        summary = content.strip().replace("\n", " ")[:500]
        return {"title": title.strip()[:300], "summary": summary, "tags": []}
