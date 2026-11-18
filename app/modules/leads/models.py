import uuid
from datetime import datetime
from typing import Any, Literal

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.modules.db import Base, JSONData, utc_now

LeadStatus = Literal["new", "done"]


class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    form: Mapped[str] = mapped_column(String(64), index=True)
    data: Mapped[dict[str, Any]] = mapped_column(JSONData)
    language: Mapped[str] = mapped_column(String(8))
    status: Mapped[str] = mapped_column(String(16), default="new", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)
    deliveries: Mapped[dict[str, Any]] = mapped_column(JSONData, default=dict)
