from __future__ import annotations

import hashlib
import re
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator

SECTION_KEY_PATTERN = re.compile(r"^[a-z0-9_](?:[a-z0-9._-]{0,62}[a-z0-9])?$")


class SectionDomain(StrEnum):
    MEMENTO = "memento"
    RESEARCH = "research"


class SectionReadPolicy(StrEnum):
    PUBLIC = "public"
    AUTHENTICATED = "authenticated"
    RESTRICTED = "restricted"


class SectionStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class AccessPermission(StrEnum):
    READ = "read"
    PUBLISH = "publish"
    ADMIN = "admin"
    SYSTEM_ADMIN = "system_admin"


class SubjectType(StrEnum):
    DEVELOPER = "developer"
    AGENT = "agent"
    CI = "ci"
    TELEGRAM = "telegram"
    SERVICE = "service"


class SectionRef(BaseModel):
    domain: SectionDomain
    key: str = Field(min_length=1, max_length=64)

    @field_validator("key", mode="before")
    @classmethod
    def normalize_key(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        normalized = value.strip().casefold()
        if not SECTION_KEY_PATTERN.fullmatch(normalized):
            raise ValueError(
                "section key must contain only lowercase letters, digits, '.', '_' or '-'"
            )
        return normalized

    @classmethod
    def parse(cls, value: str | SectionRef) -> SectionRef:
        if isinstance(value, cls):
            return value
        domain, separator, key = value.strip().partition("/")
        if not separator:
            raise ValueError("section must use domain/key format")
        return cls(domain=domain, key=key)

    @property
    def value(self) -> str:
        return f"{self.domain.value}/{self.key}"

    @property
    def tag(self) -> str:
        return f"section:{self.value}"

    @property
    def gbrain_source_id(self) -> str:
        raw = f"rl-{self.domain.value}-{self.key}".replace(".", "-").replace("_", "-")
        if len(raw) <= 32:
            return raw
        digest = hashlib.sha256(self.value.encode("utf-8")).hexdigest()[:10]
        return f"{raw[:21].rstrip('-')}-{digest}"


class LibrarySection(BaseModel):
    id: str
    ref: SectionRef
    title: str
    read_policy: SectionReadPolicy
    status: SectionStatus
    created_at: datetime
    updated_at: datetime


class AuthGrant(BaseModel):
    section: SectionRef | None
    permission: AccessPermission


class AuthPrincipal(BaseModel):
    id: str
    name: str
    subject_type: SubjectType | None = None


class AuthorizationContext(BaseModel):
    principal: AuthPrincipal
    authenticated: bool = False
    anonymous: bool = True
    legacy: bool = False
    invalid_token: bool = False
    grants: list[AuthGrant] = Field(default_factory=list)

    @property
    def principal_id(self) -> str:
        return self.principal.id


class IssuedToken(BaseModel):
    id: str
    name: str
    public_prefix: str
    token: str
    subject_type: SubjectType
    expires_at: datetime | None = None


class StoredToken(BaseModel):
    id: str
    name: str
    public_prefix: str
    token_hash: str
    subject_type: SubjectType
    expires_at: datetime | None = None
    revoked_at: datetime | None = None
    last_used_at: datetime | None = None
    created_by_token_id: str | None = None
    created_at: datetime
