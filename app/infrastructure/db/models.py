from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Text, func
from sqlalchemy.dialects.postgresql import JSONB, BIGINT
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class ChatQA(Base):
    __tablename__ = "chat_qa"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    session_id: Mapped[str] = mapped_column(Text, nullable=False)
    model_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    code: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)     
    columns: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)  
    rows: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)     
