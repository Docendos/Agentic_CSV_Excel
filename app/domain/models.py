from __future__ import annotations
from dataclasses import dataclass
from typing import List, Dict, Any, Optional

@dataclass(frozen=True)
class ColumnMeta:
    name: str
    dtype: str

@dataclass(frozen=True)
class TableMeta:
    name: str
    columns: List[ColumnMeta]
    preview: List[Dict[str, Any]]

@dataclass
class AgentTraceStep:
    tool: str
    input: str
    output: Optional[str] = None

@dataclass
class AgentAnswer:
    answer: str
    code_blocks: List[str]
    reasoning: str                  
    table_preview: Optional[List[Dict[str, Any]]] = None
    columns: Optional[List[str]] = None
