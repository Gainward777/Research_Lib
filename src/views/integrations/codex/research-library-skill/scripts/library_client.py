import argparse
import json
import os
from pathlib import Path

import httpx


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=["search", "get", "save-item"])
    parser.add_argument("value")
    parser.add_argument(
        "--base-url", default=os.getenv("LIBRARY_PUBLIC_URL", "http://localhost:8000")
    )
    parser.add_argument("--token", default=os.getenv("LIBRARY_CODEX_TOKEN", ""))
    parser.add_argument("--idempotency-key")
    args = parser.parse_args()
    headers = {"Authorization": f"Bearer {args.token}"} if args.token else {}
    with httpx.Client(base_url=args.base_url, headers=headers, timeout=60) as client:
        if args.operation == "search":
            response = client.post("/v1/search", json={"query": args.value})
        elif args.operation == "get":
            response = client.get(f"/v1/items/{args.value}")
        else:
            payload = json.loads(Path(args.value).read_text(encoding="utf-8"))
            write_headers = {
                "Idempotency-Key": args.idempotency_key or payload.pop("idempotency_key")
            }
            response = client.post("/v1/items", json=payload, headers=write_headers)
        response.raise_for_status()
        print(json.dumps(response.json(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
