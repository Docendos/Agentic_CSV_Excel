from __future__ import annotations

import os
from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware
from fastapi.staticfiles import StaticFiles

from .presentation.api import router
from .infrastructure.settings import settings
from .infrastructure.logging_config import setup_logging
from .infrastructure.db.database import init_models

logger = setup_logging()

app = FastAPI(title=settings.app_name)
app.add_middleware(SessionMiddleware, secret_key=settings.secret_key)
app.include_router(router)

static_dir = "app/presentation/web/static"
if os.path.isdir(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.on_event("startup")
async def _startup():
    await init_models()

@app.get("/health")
async def health():
    return {"status": "ok"}
