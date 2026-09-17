import json
from typing import Any

import httpx


class OpenAIResponsesClient:
    """Small Responses API client used only for structured intent routing."""

    def __init__(
        self,
        api_key: str,
        *,
        model: str,
        timeout_seconds: float = 30,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.transport = transport

    async def create_structured_response(
        self,
        *,
        system_prompt: str,
        input_text: str,
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        if not self.api_key:
            raise RuntimeError("Для маршрутизатора Telegram требуется OPENAI_API_KEY")

        payload = {
            "model": self.model,
            "store": False,
            "input": [
                {
                    "role": "system",
                    "content": [{"type": "input_text", "text": system_prompt}],
                },
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": input_text}],
                },
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "library_router_decision",
                    "description": "Вызов одного скилла библиотеки или запрос уточнения.",
                    "strict": True,
                    "schema": schema,
                }
            },
            "max_output_tokens": 600,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(
            base_url="https://api.openai.com",
            headers=headers,
            timeout=self.timeout_seconds,
            transport=self.transport,
        ) as client:
            response = await client.post("/v1/responses", json=payload)
            response.raise_for_status()
        return self._extract_json(response.json())

    @staticmethod
    def _extract_json(response: dict[str, Any]) -> dict[str, Any]:
        for output in response.get("output", []):
            if not isinstance(output, dict) or output.get("type") != "message":
                continue
            for content in output.get("content", []):
                if not isinstance(content, dict):
                    continue
                if content.get("type") == "refusal":
                    raise RuntimeError("Маршрутизатор OpenAI отказался классифицировать запрос")
                if content.get("type") == "output_text":
                    value = json.loads(str(content.get("text", "")))
                    if isinstance(value, dict):
                        return value
        raise RuntimeError("Маршрутизатор OpenAI не вернул структурированное решение")
