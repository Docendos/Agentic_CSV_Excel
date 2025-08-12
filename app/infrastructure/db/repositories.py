from __future__ import annotations

from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from .models import ChatQA


class ChatLogRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add_entry(
        self,
        *,
        session_id: str,
        model_name: Optional[str],
        question: str,
        answer: str,
        explanation: Optional[str],
        code: Optional[List[str]],
        columns: Optional[List[str]],
        rows: Optional[List[dict]],
    ) -> ChatQA:
        obj = ChatQA(
            session_id=session_id,
            model_name=model_name,
            question=question,
            answer=answer,
            explanation=explanation,
            code=code,
            columns=columns,
            rows=rows,
        )
        self.session.add(obj)
        await self.session.commit()
        await self.session.refresh(obj)
        return obj
