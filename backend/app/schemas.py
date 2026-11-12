import uuid
from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints

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
