import asyncio
import json
import os
import re
from pathlib import Path
from typing import Any

from controllers.utils.BD.markdown import MarkdownItemRepository
from errors import SearchBackendError
from models.commands import SearchCommand
from models.enums import LibraryItemType
from models.library_item import LibraryItem
from models.results import AnswerResult, SearchHit


class GBrainAdapter:
    """Serialized official GBrain CLI adapter with a Markdown search fallback."""

    SAFE_ENVIRONMENT_NAMES = (
        "PATH",
        "PATHEXT",
        "SYSTEMROOT",
        "WINDIR",
        "TEMP",
        "TMP",
        "USERPROFILE",
        "HOME",
        "APPDATA",
        "LOCALAPPDATA",
    )

    def __init__(
        self,
        repository: MarkdownItemRepository,
        *,
        mode: str = "local",
        command: str = "gbrain",
        timeout_seconds: float = 30,
        home: Path | None = None,
    ) -> None:
        self.repository = repository
        self.mode = mode
        self.command = command
        self.timeout_seconds = timeout_seconds
        self.home = home
        self._write_lock = asyncio.Lock()

    async def health(self) -> bool:
        if self.mode == "local":
            return True
        try:
            result = await self._run_json(["doctor", "--json"])
            status = str(result.get("status", result.get("state", "ok"))).casefold()
            return status in {"ok", "healthy", "ready", "pass"}
        except Exception:
            return False

    async def index(self, item: LibraryItem) -> None:
        if self.mode == "local":
            return
        row = await self.repository.database.fetchone(
            "SELECT path, slug FROM library_items WHERE id = ?", (item.id,)
        )
        if row is None:
            raise SearchBackendError(f"Cannot index unknown item: {item.id}")
        content = (self.repository.brain_root / row["path"]).read_bytes()
        async with self._write_lock:
            await self._run_command(["put", str(row["slug"])], content)

    async def search(self, command: SearchCommand) -> list[SearchHit]:
        if self.mode == "subprocess":
            payload: dict[str, Any] = {"query": command.query, "limit": command.limit}
            if command.types:
                payload["types"] = [item.value for item in command.types]
            if command.tags:
                payload["tags"] = command.tags
            result = await self._run_call("search", payload)
            return self._normalize_hits(result, command.limit)
        return await self._local_search(command)

    async def ask(self, command: SearchCommand) -> AnswerResult:
        if self.mode == "subprocess":
            result = await self._run_call("query", {"query": command.query, "limit": command.limit})
            data = self._unwrap(result)
            if not isinstance(data, dict):
                return AnswerResult(answer=str(data))
            answer = str(data.get("answer") or data.get("response") or data.get("text") or "")
            sources_value = data.get("sources") or data.get("hits") or data.get("results") or []
            return AnswerResult(
                answer=answer, sources=self._normalize_hits(sources_value, command.limit)
            )
        hits = await self._local_search(command)
        if not hits:
            return AnswerResult(answer="В библиотеке не найдено подходящих материалов.")
        source_lines = [f"- {hit.title}: {hit.summary or hit.slug}" for hit in hits[:5]]
        return AnswerResult(
            answer="Найдены релевантные материалы:\n" + "\n".join(source_lines),
            sources=hits[:5],
        )

    async def _local_search(self, command: SearchCommand) -> list[SearchHit]:
        terms = set(re.findall(r"[\w-]+", command.query.casefold()))
        hits: list[SearchHit] = []
        allowed_types = set(command.types)
        required_tags = {tag.casefold() for tag in command.tags}
        for page in self.repository.iter_pages():
            try:
                item = self.repository.parse(page.read_text(encoding="utf-8"))
            except (ValueError, TypeError):
                continue
            if allowed_types and item.type not in allowed_types:
                continue
            item_tags = {tag.casefold() for tag in item.tags}
            if required_tags and not required_tags.issubset(item_tags):
                continue
            haystack = " ".join(
                [item.title, item.summary, item.content, " ".join(item.tags)]
            ).casefold()
            matched = sum(1 for term in terms if term in haystack)
            if not matched:
                continue
            relative = page.relative_to(self.repository.brain_root).with_suffix("").as_posix()
            hits.append(
                SearchHit(
                    item_id=item.id,
                    slug=relative,
                    type=item.type,
                    title=item.title,
                    summary=item.summary,
                    score=matched / max(len(terms), 1),
                    tags=item.tags,
                )
            )
        hits.sort(key=lambda hit: (-hit.score, hit.title.casefold()))
        return hits[: command.limit]

    async def _run_call(self, operation: str, payload: dict[str, Any]) -> Any:
        compact = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        return await self._run_json(["call", operation, compact])

    async def _run_json(self, arguments: list[str]) -> dict[str, Any]:
        decoded = (await self._run_command(arguments)).decode("utf-8", errors="replace").strip()
        try:
            value = json.loads(decoded)
        except json.JSONDecodeError:
            value = None
            for line in reversed(decoded.splitlines()):
                try:
                    value = json.loads(line)
                    break
                except json.JSONDecodeError:
                    continue
            if value is None:
                raise SearchBackendError("GBrain returned invalid JSON") from None
        return value if isinstance(value, dict) else {"data": value}

    async def _run_command(self, arguments: list[str], stdin: bytes | None = None) -> bytes:
        environment = {
            name: value
            for name in self.SAFE_ENVIRONMENT_NAMES
            if (value := os.environ.get(name)) is not None
        }
        if self.home is not None:
            environment["GBRAIN_HOME"] = str(self.home)
        try:
            process = await asyncio.create_subprocess_exec(
                self.command,
                *arguments,
                stdin=asyncio.subprocess.PIPE if stdin is not None else asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.home,
                env=environment,
            )
            stdout, stderr = await asyncio.wait_for(
                process.communicate(stdin), self.timeout_seconds
            )
        except (OSError, TimeoutError) as exc:
            raise SearchBackendError(f"GBrain command failed: {exc}") from exc
        if process.returncode != 0:
            message = stderr.decode("utf-8", errors="replace").strip()
            raise SearchBackendError(message or f"GBrain exited with code {process.returncode}")
        return stdout

    @classmethod
    def _normalize_hits(cls, result: Any, limit: int) -> list[SearchHit]:
        value = cls._unwrap(result)
        if isinstance(value, dict):
            value = value.get("hits") or value.get("results") or value.get("pages") or []
        if not isinstance(value, list):
            return []
        hits: list[SearchHit] = []
        for raw in value[:limit]:
            if not isinstance(raw, dict):
                continue
            frontmatter = raw.get("frontmatter") if isinstance(raw.get("frontmatter"), dict) else {}
            slug = str(raw.get("slug") or raw.get("path") or "")
            item_id = str(raw.get("item_id") or raw.get("id") or frontmatter.get("id") or slug)
            raw_type = str(raw.get("type") or frontmatter.get("type") or "note")
            try:
                item_type = LibraryItemType(raw_type)
            except ValueError:
                item_type = LibraryItemType.NOTE
            hits.append(
                SearchHit(
                    item_id=item_id,
                    slug=slug,
                    type=item_type,
                    title=str(raw.get("title") or frontmatter.get("title") or slug),
                    summary=str(
                        raw.get("summary") or raw.get("snippet") or raw.get("content") or ""
                    )[:1000],
                    score=float(raw.get("score") or raw.get("rank") or 0),
                    tags=list(raw.get("tags") or frontmatter.get("tags") or []),
                )
            )
        return hits

    @staticmethod
    def _unwrap(value: Any) -> Any:
        while isinstance(value, dict) and set(value).intersection({"data", "result"}):
            value = value["data"] if "data" in value else value["result"]
        return value
