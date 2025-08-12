from __future__ import annotations
from typing import List, Dict, Any, Tuple
import pandas as pd
from ...domain.models import AgentAnswer

def to_agent_answer(answer: str, code_blocks: List[str], reasoning: str, cols: List[str], rows: List[Dict[str, Any]]) -> AgentAnswer:
    return AgentAnswer(
        answer=answer,
        code_blocks=code_blocks,
        reasoning=reasoning,
        columns=cols or None,
        table_preview=rows or None
    )
