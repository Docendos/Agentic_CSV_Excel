from pydantic import BaseModel, Field
from typing import List, Dict, Any

class UploadResponse(BaseModel):
    tables: List[Dict[str, Any]]

class AskRequest(BaseModel):
    question: str = Field(..., min_length=1)

class AskResponse(BaseModel):
    answer: str
    code: List[str]
    explanation: str
    columns: List[str]
    rows: List[Dict[str, Any]]
