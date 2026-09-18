import asyncio
import json
import os
import re
from pathlib import Path
from typing import Any

from controllers.utils.BD.markdown import MarkdownItemRepository
from controllers.utils.infrastructure.filesystem.atomic_writer import atomic_write_text
from errors import SearchBackendError
from models.access import SectionRef
from models.commands import SearchCommand
from models.enums import LibraryItemType
from models.library_item import LibraryItem
from models.results import AnswerResult, SearchHit


class GBrainAdapter:
    """Serialized adapter for the pinned official GBrain CLI and its PGLite engine."""

    BOOTSTRAP_MARKER_NAME = ".research-library-bootstrap-v2-sections"

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
        "OPENAI_API_KEY",
    )
    READY_STATUSES = {
        "ok",
        "healthy",
        "ready",
        "pass",
        "warn",
        "warning",
        "warnings",
        "degraded",
    }
    FAILED_CHECK_STATUSES = {"error", "fail", "failed", "unhealthy"}
    CRITICAL_CHECK_NAMES = {
        "connection",
        "schema_version",
        "pgvector",
        "pglite_data_dir",
        "pglite_runtime",
    }

    def __init__(
        self,
        repository: MarkdownItemRepository,
        *,
        command: str = "gbrain",
        timeout_seconds: float = 30,
        home: Path,
        expected_version: str = "",
        no_embedding: bool = True,
        embedding_model: str = "",
        embedding_dimensions: int | None = None,
        think_model: str = "",
    ) -> None:
        self.repository = repository
        self.command = command
        self.timeout_seconds = timeout_seconds
        self.home = home
        self.expected_version = expected_version
        self.no_embedding = no_embedding
        self.embedding_model = embedding_model
        self.embedding_dimensions = embedding_dimensions
        self.think_model = think_model
        # PGLite is single-process. Every CLI invocation must be serialized,
        # including reads, otherwise concurrent Telegram/API requests contend
        # for the same embedded database lock.
        self._process_lock = asyncio.Lock()
        self._known_sources: set[str] = set()

    async def initialize(self) -> bool:
        """Create or migrate the persistent PGLite brain and verify its runtime.

        Returns True until bootstrap has fully rebuilt GBrain from the durable
        Markdown pages and written its completion marker.
        """
        self.home.mkdir(parents=True, exist_ok=True)
        await self._verify_version()

        config_path = self.home / "config.json"
        created = not config_path.exists()
        if created:
            arguments = [
                "init",
                "--pglite",
                "--non-interactive",
                "--path",
                str(self.home / "brain.pglite"),
                "--json",
            ]
            if self.no_embedding:
                arguments.append("--no-embedding")
            else:
                arguments.extend(["--embedding-model", self.embedding_model])
                arguments.extend(["--embedding-dimensions", str(self.embedding_dimensions)])
            result = await self._run_json(arguments)
            status = str(result.get("status", "success")).casefold()
            if status not in {"ok", "success", "ready"}:
                raise SearchBackendError(f"GBrain initialization failed: {result}")
        else:
            await self._run_json(["init", "--migrate-only", "--json"])

        if not await self._doctor_health():
            raise SearchBackendError("GBrain health check failed after initialization")
        return not (self.home / self.BOOTSTRAP_MARKER_NAME).exists()

    def mark_bootstrap_complete(self) -> None:
        atomic_write_text(
            self.home / self.BOOTSTRAP_MARKER_NAME,
            f"gbrain={self.expected_version or 'unknown'}\n",
        )

    async def health(self) -> bool:
        """Cheap readiness probe that opens PGLite and reads its statistics."""
        try:
            result = await self._run_call("get_stats", {})
        except Exception:
            return False
        return isinstance(self._unwrap(result), dict)

    async def _doctor_health(self) -> bool:
        """Full startup diagnostic, limited to checks that block library storage."""
        try:
            raw_result = await self._run_json(["doctor", "--json"])
        except Exception:
            return False
        result = self._unwrap(raw_result)
        if not isinstance(result, dict):
            return await self.health()

        checks = result.get("checks")
        if isinstance(checks, list):
            connection_seen = False
            for check in checks:
                if not isinstance(check, dict):
                    continue
                name = re.sub(
                    r"[^a-z0-9]+",
                    "_",
                    str(check.get("name", "")).strip().casefold(),
                ).strip("_")
                status = str(check.get("status", "")).casefold()
                is_connection = name == "connection" or name.endswith("_connection")
                if is_connection:
                    connection_seen = True
                if (
                    is_connection or name in self.CRITICAL_CHECK_NAMES
                ) and status in self.FAILED_CHECK_STATUSES:
                    return False
            # Opinionated maintenance checks (brain score, graph coverage,
            # enrichment) can fail on an empty but operational library and do
            # not make the storage engine unavailable.
            if connection_seen:
                return True

        status = str(result.get("status", result.get("state", ""))).casefold()
        if status in self.READY_STATUSES:
            return True
        # Doctor has changed its JSON envelope and check names between pinned
        # releases. A successful stats call is the compatibility-safe proof
        # that the embedded database can actually be opened and queried.
        return await self.health()

    async def index(self, item: LibraryItem) -> None:
        row = await self.repository.database.fetchone(
            "SELECT path, slug FROM library_items WHERE id = ?", (item.id,)
        )
        if row is None:
            raise SearchBackendError(f"Cannot index unknown item: {item.id}")
        content = (self.repository.brain_root / row["path"]).read_bytes()
        await self._ensure_source(item.section)
        # stdin avoids argv length limits for unstructured Telegram messages.
        await self._run_command(
            ["put", str(row["slug"])], content, source_id=item.section.gbrain_source_id
        )

    async def search(self, command: SearchCommand) -> list[SearchHit]:
        # GBrain search accepts query/limit, while application-level type and tag
        # filters belong to the library contract and are applied after retrieval.
        gbrain_limit = 100 if command.types or command.tags else command.limit
        source_id = self._command_source(command)
        await self._ensure_source(command.sections[0])
        payload = {"query": command.query, "limit": gbrain_limit}
        result = await self._run_call("search", payload, source_id=source_id)
        hits = self._normalize_hits(result, gbrain_limit)
        return self._filter_hits(hits, command)[: command.limit]

    async def query(self, command: SearchCommand) -> list[SearchHit]:
        source_id = self._command_source(command)
        await self._ensure_source(command.sections[0])
        payload = {"query": command.query, "limit": command.limit}
        result = await self._run_call("query", payload, source_id=source_id)
        return self._normalize_hits(result, command.limit)

    async def think(self, command: SearchCommand) -> AnswerResult:
        payload: dict[str, Any] = {"question": command.query}
        if self.think_model:
            payload["model"] = self.think_model
        source_id = self._command_source(command)
        await self._ensure_source(command.sections[0])
        raw_result = await self._run_call("think", payload, source_id=source_id)
        result = self._unwrap(raw_result)
        if not isinstance(result, dict):
            raise SearchBackendError("GBrain think returned an invalid response")

        synthesis_ok = result.get("synthesisOk", result.get("synthesis_ok", True))
        raw_answer = result.get("answer")
        answer = raw_answer if isinstance(raw_answer, str) else ""
        if synthesis_ok is False or not answer:
            warnings = result.get("warnings")
            detail = ", ".join(map(str, warnings)) if isinstance(warnings, list) else ""
            suffix = f": {detail}" if detail else ""
            raise SearchBackendError(f"GBrain could not synthesize an answer{suffix}")

        sources: list[SearchHit] = []
        seen_slugs: set[str] = set()
        citations = result.get("citations")
        if isinstance(citations, list):
            for citation in citations:
                if not isinstance(citation, dict):
                    continue
                slug = str(citation.get("page_slug") or citation.get("slug") or "")
                if not slug or slug in seen_slugs:
                    continue
                stored = await self.repository.get(slug)
                if stored is None:
                    continue
                item, stored_slug = stored
                sources.append(
                    SearchHit(
                        item_id=item.id,
                        slug=stored_slug,
                        type=item.type,
                        title=item.title,
                        summary=item.summary,
                        tags=item.tags,
                    )
                )
                seen_slugs.add(slug)
        return AnswerResult(answer=answer, sources=sources)

    async def _verify_version(self) -> None:
        output = (await self._run_command(["--version"])).decode("utf-8", errors="replace")
        match = re.search(r"\d+(?:\.\d+){2,3}", output)
        actual = match.group(0) if match else ""
        if not actual:
            raise SearchBackendError(f"Cannot determine GBrain version from: {output.strip()}")
        if self.expected_version and actual != self.expected_version:
            raise SearchBackendError(
                f"GBrain version mismatch: expected {self.expected_version}, got {actual}"
            )

    @staticmethod
    def _command_source(command: SearchCommand) -> str:
        if len(command.sections) != 1:
            raise SearchBackendError("A GBrain call must target exactly one section")
        return command.sections[0].gbrain_source_id

    async def _ensure_source(self, section: SectionRef) -> None:
        source_id = section.gbrain_source_id
        if source_id in self._known_sources:
            return
        source_path = self.home / "sources" / source_id
        source_path.mkdir(parents=True, exist_ok=True)
        try:
            await self._run_command(
                [
                    "sources", "add", source_id, "--path", str(source_path),
                    "--name", section.value, "--no-federated", "--force",
                ]
            )
        except SearchBackendError as exc:
            if "already" not in str(exc).casefold() and "exists" not in str(exc).casefold():
                raise
        self._known_sources.add(source_id)

    async def _run_call(
        self,
        operation: str,
        payload: dict[str, Any],
        *,
        source_id: str | None = None,
    ) -> Any:
        compact = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        arguments = ["call"]
        if source_id:
            arguments.extend(["--source", source_id])
        arguments.extend([operation, compact])
        return await self._run_json(arguments)

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

    async def _run_command(
        self,
        arguments: list[str],
        stdin: bytes | None = None,
        *,
        source_id: str | None = None,
    ) -> bytes:
        environment = {
            name: value
            for name in self.SAFE_ENVIRONMENT_NAMES
            if (value := os.environ.get(name)) is not None
        }
        environment["GBRAIN_HOME"] = str(self.home)
        environment["GBRAIN_NO_ONBOARD_NUDGE"] = "1"
        if source_id:
            environment["GBRAIN_SOURCE"] = source_id
        try:
            async with self._process_lock:
                process = await asyncio.create_subprocess_exec(
                    self.command,
                    *arguments,
                    stdin=(
                        asyncio.subprocess.PIPE if stdin is not None else asyncio.subprocess.DEVNULL
                    ),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=self.home,
                    env=environment,
                )
                try:
                    stdout, stderr = await asyncio.wait_for(
                        process.communicate(stdin), self.timeout_seconds
                    )
                except TimeoutError as exc:
                    try:
                        process.kill()
                    except ProcessLookupError:
                        pass
                    await process.communicate()
                    raise SearchBackendError(
                        f"GBrain command timed out after {self.timeout_seconds:g} seconds"
                    ) from exc
        except OSError as exc:
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
                        raw.get("summary")
                        or raw.get("snippet")
                        or raw.get("compiled_truth")
                        or raw.get("content")
                        or ""
                    )[:1000],
                    score=float(raw.get("score") or raw.get("rank") or 0),
                    tags=list(raw.get("tags") or frontmatter.get("tags") or []),
                )
            )
        return hits

    @staticmethod
    def _filter_hits(hits: list[SearchHit], command: SearchCommand) -> list[SearchHit]:
        allowed_types = set(command.types)
        required_tags = {tag.casefold() for tag in command.tags}
        return [
            hit
            for hit in hits
            if (not allowed_types or hit.type in allowed_types)
            and (not required_tags or required_tags.issubset({tag.casefold() for tag in hit.tags}))
        ]

    @staticmethod
    def _unwrap(value: Any) -> Any:
        while isinstance(value, dict) and set(value).intersection({"data", "result"}):
            value = value["data"] if "data" in value else value["result"]
        return value
