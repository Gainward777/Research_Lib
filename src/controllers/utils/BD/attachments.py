import hashlib
import mimetypes
import re
from pathlib import Path
from uuid import uuid4

from controllers.utils.BD.sqlite import Database
from controllers.utils.infrastructure.filesystem.atomic_writer import atomic_write_bytes
from controllers.utils.infrastructure.filesystem.image_processor import normalize_image
from models.library_item import Attachment


def safe_name(name: str | None) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9._-]+", "-", name or "file").strip(".-")
    return normalized[:120] or "file"


class AttachmentStore:
    def __init__(
        self,
        root: Path,
        database: Database,
        *,
        max_long_side: int = 2048,
        image_format: str = "webp",
        image_quality: int = 85,
    ) -> None:
        self.root = root
        self.database = database
        self.max_long_side = max_long_side
        self.image_format = image_format
        self.image_quality = image_quality

    async def save_upload(
        self, content: bytes, filename: str | None, content_type: str | None
    ) -> dict[str, object]:
        if not content:
            raise ValueError("Empty upload")
        upload_id = f"upload_{uuid4().hex}"
        mime_type = (
            content_type or mimetypes.guess_type(filename or "")[0] or "application/octet-stream"
        )
        extension = Path(filename or "file").suffix.lstrip(".") or "bin"
        processed = content
        if mime_type.startswith("image/"):
            processed, extension = normalize_image(
                content,
                max_long_side=self.max_long_side,
                image_format=self.image_format,
                quality=self.image_quality,
            )
            mime_type = f"image/{'jpeg' if extension == 'jpg' else extension}"
        digest = hashlib.sha256(processed).hexdigest()
        relative_path = Path("_uploads") / f"{upload_id}-{safe_name(filename)}.{extension}"
        atomic_write_bytes(self.root / relative_path, processed)
        await self.database.execute(
            "INSERT INTO uploads(id, path, sha256, mime_type, size_bytes, original_name) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (upload_id, relative_path.as_posix(), digest, mime_type, len(processed), filename),
        )
        return {
            "upload_id": upload_id,
            "sha256": digest,
            "mime_type": mime_type,
            "size_bytes": len(processed),
        }

    async def consume(self, upload_id: str, item_id: str) -> Attachment:
        row = await self.database.fetchone("SELECT * FROM uploads WHERE id = ?", (upload_id,))
        if row is None:
            raise ValueError(f"Unknown upload: {upload_id}")
        source = self.root / row["path"]
        extension = source.suffix
        target_relative = (
            Path(item_id) / f"{row['sha256'][:12]}-{safe_name(row['original_name'])}{extension}"
        )
        target = self.root / target_relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            source.replace(target)
        elif source.exists():
            source.unlink()
        await self.database.execute(
            "UPDATE uploads SET path = ?, consumed_at = CURRENT_TIMESTAMP WHERE id = ?",
            (target_relative.as_posix(), upload_id),
        )
        return Attachment(
            id=upload_id,
            path=(Path("attachments") / target_relative).as_posix(),
            sha256=row["sha256"],
            mime_type=row["mime_type"],
            size_bytes=row["size_bytes"],
            original_name=row["original_name"],
        )

    async def discard(self, upload_id: str) -> None:
        row = await self.database.fetchone("SELECT * FROM uploads WHERE id = ?", (upload_id,))
        if row is None or row["consumed_at"] is not None:
            return
        path = self.root / row["path"]
        try:
            path.unlink(missing_ok=True)
        except OSError:
            return
        await self.database.execute("DELETE FROM uploads WHERE id = ?", (upload_id,))
