"""Pydantic request/response models for kazusa-home-portal APIs."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


# ── Token API ──────────────────────────────────────────

class CreateTokenRequest(BaseModel):
    description: str = Field(default="", max_length=200)
    expires_in_days: Optional[int] = Field(default=None, ge=1, le=3650)


class TokenResponse(BaseModel):
    id: int
    token: str
    prefix: str
    description: str
    expires_at: Optional[str]


class TokenListItem(BaseModel):
    id: int
    user_id: int
    prefix: str
    description: str
    expires_at: Optional[str]
    last_used_at: Optional[str]
    created_at: Optional[str]
    revoked: bool
    user_email: Optional[str] = None


# ── Session API ───────────────────────────────────────

class SessionItem(BaseModel):
    id: str
    user_id: int
    created_at: Optional[str]
    expires_at: Optional[str]
    last_used_at: Optional[str]
    ip_addr: str
    user_agent: str
    is_current: bool


class RevokeAllSessionsResponse(BaseModel):
    ok: bool
    revoked_count: int


# ── Admin: Users ──────────────────────────────────────

class UpdateUserRoleRequest(BaseModel):
    role: str = Field(..., min_length=1, max_length=64)


# ── Admin: ACL ─────────────────────────────────────────

class ACLRuleBase(BaseModel):
    domain: str = Field(..., min_length=1, max_length=512)
    email: str = Field(..., min_length=1, max_length=512)


class ACLRuleCreate(ACLRuleBase):
    pass


class ACLRuleUpdate(BaseModel):
    domain: Optional[str] = Field(default=None, min_length=1, max_length=512)
    email: Optional[str] = Field(default=None, min_length=1, max_length=512)
    enabled: Optional[bool] = None


# ── Admin: Role ACL ───────────────────────────────────────

class RoleACLRuleBase(BaseModel):
    domain: str = Field(..., min_length=1, max_length=512)
    role: str = Field(..., min_length=1, max_length=64)


class RoleACLRuleCreate(RoleACLRuleBase):
    pass


class RoleACLRuleUpdate(BaseModel):
    domain: Optional[str] = Field(default=None, min_length=1, max_length=512)
    role: Optional[str] = Field(default=None, min_length=1, max_length=64)
    enabled: Optional[bool] = None


# ── Admin: Role Presets ───────────────────────────────────

class RolePresetBase(BaseModel):
    email: str = Field(..., min_length=1, max_length=512)
    role: str = Field(..., min_length=1, max_length=64)


class RolePresetCreate(RolePresetBase):
    pass


class RolePresetUpdate(BaseModel):
    email: Optional[str] = Field(default=None, min_length=1, max_length=512)
    role: Optional[str] = Field(default=None, min_length=1, max_length=64)


# ── Admin: Announcements ─────────────────────────────────

class AnnouncementBase(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    level: str = Field(default="info", pattern=r"^(info|warn|error)$")

    @field_validator("level", mode="before")
    @classmethod
    def _default_level(cls, v):
        return v if v else "info"


class AnnouncementCreate(AnnouncementBase):
    pass


class AnnouncementUpdate(BaseModel):
    message: Optional[str] = Field(default=None, min_length=1, max_length=2000)
    active: Optional[bool] = None
    level: Optional[str] = Field(default=None, pattern=r"^(info|warn|error)$")


# ── QR Login ───────────────────────────────────────────

class QRConfirmRequest(BaseModel):
    sid: str = Field(..., min_length=1)


# ── Mock Login ────────────────────────────────────────

class MockLoginRequest(BaseModel):
    email: Optional[str] = Field(default=None, max_length=512)


# ── Common ────────────────────────────────────────────

class OkResponse(BaseModel):
    ok: bool = True
