from __future__ import annotations

import os
import shutil
import tempfile

from fastapi import APIRouter, UploadFile, File, HTTPException, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from ..infrastructure.data.dataset_repo import InMemoryDatasetRepository
from ..application.use_cases.upload_table import UploadTableUseCase
from ..application.use_cases.ask_question import AskQuestionUseCase
from .schemas import UploadResponse, AskRequest, AskResponse

from ..infrastructure.db.database import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from ..infrastructure.db.repositories import ChatLogRepository
from ..infrastructure.settings import settings

router = APIRouter()
templates = Jinja2Templates(directory="app/presentation/web/templates")

_repo = InMemoryDatasetRepository()


def get_session_id(request: Request) -> str:
    sid = request.session.get("sid")
    if not sid:
        import secrets
        sid = secrets.token_hex(16)
        request.session["sid"] = sid
    return sid


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@router.post("/api/upload", response_model=UploadResponse)
async def upload(request: Request, file: UploadFile = File(...)):
    session_id = get_session_id(request)
    suffix = os.path.splitext(file.filename or "")[1].lower()
    if suffix not in [".csv", ".xlsx", ".xls"]:
        raise HTTPException(status_code=400, detail="Only CSV/XLSX/XLS are supported.")

    tmpdir = tempfile.mkdtemp()
    tmpfile = os.path.join(tmpdir, f"upload{suffix}")
    try:
        with open(tmpfile, "wb") as f:
            f.write(await file.read())

        uc = UploadTableUseCase(_repo)
        metas = uc.execute(session_id, tmpfile)
        return {"tables": [m.__dict__ for m in metas]}
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


@router.post("/api/ask", response_model=AskResponse)
async def ask(
    request: Request,
    payload: AskRequest,
    db: AsyncSession = Depends(get_db), 
):
    session_id = get_session_id(request)
    uc = AskQuestionUseCase(_repo)
    try:
        data = await uc.execute(session_id, payload.question.strip())
        repo = ChatLogRepository(db)
        await repo.add_entry(
            session_id=session_id,
            model_name=settings.openai_model,
            question=payload.question.strip(),
            answer=data.get("answer", ""),
            explanation=data.get("explanation", ""),
            code=data.get("code"),
            columns=data.get("columns"),
            rows=data.get("rows"),
        )
        return data
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
