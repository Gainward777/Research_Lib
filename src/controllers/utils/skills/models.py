from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from controllers.utils.services.librarian.dialog_context import DialogTurn
from models.enums import LibraryItemType


class AttachmentMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["photo", "document"]
    file_unique_id: str
    file_name: str | None = None
    mime_type: str | None = None
    size_bytes: int | None = None
    width: int | None = None
    height: int | None = None


class TelegramMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chat_id: int
    chat_type: str
    message_ids: list[int]
    user_id: int | None = None
    username: str | None = None
    is_forwarded: bool = False
    media_group_id: str | None = None


class RouterInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    original_text: str
    attachments: list[AttachmentMetadata] = Field(default_factory=list)
    telegram: TelegramMetadata
    dialog_context: list[DialogTurn] = Field(default_factory=list)
    collection_active: bool = False


class SkillArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str | None = None
    title: str | None = None
    material_type: LibraryItemType | None = None
    item_ref: str | None = None
    requested_type: str | None = None
    text: str | None = None


class RouterDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["invoke", "clarify"]
    skill_name: str | None
    arguments: SkillArguments
    clarification_question: str | None

    @model_validator(mode="after")
    def validate_decision(self) -> "RouterDecision":
        if self.kind == "invoke" and not self.skill_name:
            raise ValueError("An invoke decision requires skill_name")
        if self.kind == "clarify" and not self.clarification_question:
            raise ValueError("A clarify decision requires clarification_question")
        return self


@dataclass
class SkillContext:
    container: Any
    original_text: str
    telegram: TelegramMetadata
    attachments: list[AttachmentMetadata] = field(default_factory=list)
    attachment_upload_ids: list[str] = field(default_factory=list)
    dialog_context: list[DialogTurn] = field(default_factory=list)
    collection_active: bool = False
    invocation_source: Literal["natural", "alias"] = "natural"

    @property
    def source_external_id(self) -> str:
        if self.telegram.media_group_id:
            return f"telegram-group:{self.telegram.chat_id}:{self.telegram.media_group_id}"
        return f"telegram:{self.telegram.chat_id}:{self.telegram.message_ids[0]}"
