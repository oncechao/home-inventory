import uuid
from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints, field_validator

from app.models import as_utc

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Note = Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)]
UtcDatetime = Annotated[datetime, AfterValidator(as_utc)]


class OrmModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------- 账号 ----------

class RegisterIn(BaseModel):
    username: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=3, max_length=50, pattern=r"^\w+$")
    ]
    password: str = Field(min_length=8, max_length=128)


class LoginIn(BaseModel):
    username: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]
    password: str = Field(min_length=1, max_length=128)


class PasswordIn(BaseModel):
    old_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class UserOut(OrmModel):
    id: uuid.UUID
    username: str


# ---------- 家庭 ----------

class FamilyIn(BaseModel):
    name: Name


class FamilyOut(OrmModel):
    id: uuid.UUID
    name: str


class MemberOut(BaseModel):
    id: uuid.UUID
    username: str
    joined_at: UtcDatetime


class FamilyDetail(FamilyOut):
    members: list[MemberOut]


# ---------- 邀请 ----------

class InviteOut(OrmModel):
    id: uuid.UUID
    code: str
    expires_at: UtcDatetime


class InvitePreview(BaseModel):
    family_id: uuid.UUID
    family_name: str
    already_member: bool


# ---------- 位置 ----------

class PathNode(BaseModel):
    id: uuid.UUID
    name: str


class LocationIn(BaseModel):
    name: Name
    note: Note = ""
    parent_id: uuid.UUID | None = None


class LocationPatch(BaseModel):
    """不传的字段不修改；parent_id 显式传 null 表示移到顶层。"""

    name: Name | None = None
    note: Note | None = None
    parent_id: uuid.UUID | None = None


class LocationOut(BaseModel):
    id: uuid.UUID
    name: str
    note: str
    parent_id: uuid.UUID | None
    path: list[PathNode]
    updated_at: UtcDatetime
    updated_by_name: str | None


# ---------- 物品 ----------

ItemName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Barcode = Annotated[str, StringConstraints(strip_whitespace=True, max_length=64)]


class ItemIn(BaseModel):
    name: ItemName
    barcode: Barcode | None = None
    note: Note = ""
    location_id: uuid.UUID

    @field_validator("barcode")
    @classmethod
    def empty_barcode_to_none(cls, v: str | None) -> str | None:
        return v or None


class ItemPatch(BaseModel):
    """不传的字段不修改；barcode 显式传 null 或空字符串表示清空。"""

    name: ItemName | None = None
    barcode: Barcode | None = None
    note: Note | None = None
    location_id: uuid.UUID | None = None

    @field_validator("barcode")
    @classmethod
    def empty_barcode_to_none(cls, v: str | None) -> str | None:
        return v or None


class ItemOut(BaseModel):
    id: uuid.UUID
    name: str
    barcode: str | None
    note: str
    location_id: uuid.UUID
    path: list[PathNode]
    updated_at: UtcDatetime
    updated_by_name: str | None


class LocationDetail(LocationOut):
    children: list[LocationOut]
    items: list[ItemOut]
