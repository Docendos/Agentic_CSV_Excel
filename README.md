# AI DataFrame Chat (FastAPI · Pandas · OpenAI)

Chat with your CSV/Excel data.

Upload a file, ask **free-form questions**, and get:
- a precise answer (computed from executed pandas),
- the **actual pandas code** used,
- a clear **explanation**,
- and a small **result preview** (table).

---

## Quickstart

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# .env-based config (see below), but you can also export:
# export OPENAI_API_KEY=sk-...
# export OPENAI_MODEL=gpt-4o-mini
# export DATABASE_URL=postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/db

uvicorn app.main:app --reload --port 8000
```

Open: http://localhost:8000

---

## What’s inside

- **Upload CSV/XLS/XLSX** (multi-sheet → multiple tables)
- **Schema & preview** per table
- **Answer + pandas code + explanation + preview**
- **Postgres logging** of each Q&A turn
- **Safety-first execution**: no external imports; restricted execution environment

---

## How it works

We **do not** use LangChain’s Python REPL tool (which requires special sandboxing).

Flow:
1. The LLM (OpenAI via `langchain-openai`) **generates pandas code** to answer your question.  
2. We **validate** the code with a denylist (no `import`, `open`, `os`, `sys`, `eval`, etc.).  
3. We **execute** it in a **restricted namespace**:
   - available: `pd` (pandas), your session’s DataFrames, a tiny set of safe builtins, and a helper `as_df(x, name='value')`.
   - not available: filesystem, network, arbitrary imports, dunders, eval/exec, etc.
4. We **normalize** the result to a DataFrame and compute the **authoritative answer** from the actual result.
5. UI shows **Explanation**, **Code (pandas)**, and a **table preview**.  
   If a table is shown, the top plain-text answer is hidden to avoid duplication.

If `OPENAI_API_KEY` is not set, a **rule-based fallback** handles simple queries (count/mean/sum/variance/preview).

---

## Architecture

```
app/
  domain/
    models.py                 # core entities (TableMeta, AgentAnswer, etc.)
  application/
    use_cases/
      upload_table.py         # parse & validate CSV/Excel → DataFrames
      ask_question.py         # orchestrate: run agent, format response
  infrastructure/
    data/
      dataset_repo.py         # in-memory, per-session tables
    db/
      database.py             # async SQLAlchemy engine/session + robust init (retries)
      models.py               # ChatQA table
      repositories.py         # ChatLogRepository (persist Q&A)
    llm/
      langchain_agent.py      # LLM→pandas codegen, safety checks, restricted exec, as_df helper
    logging_config.py
    settings.py               # Pydantic settings from `.env`
  presentation/
    api.py                    # FastAPI routes (/api/upload, /api/ask, /)
    schemas.py                # Pydantic I/O shapes
    web/
      templates/
        index.html            # minimal UI (Pico.css)
```

---

## Configuration (`.env`)

The app reads configuration from a `.env` in the project root:

```dotenv
APP_NAME=AI DataFrame Chat
SECRET_KEY=change-me

OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini

# Async SQLAlchemy URL (Postgres):
DATABASE_URL=postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/aidata
```

---

## API

- `GET /` — HTML UI
- `POST /api/upload` — multipart file upload (`.csv`, `.xls`, `.xlsx`)  
  Response: schema + preview; tables are stored per session.
- `POST /api/ask` — body:  
  ```json
  { "question": "..." }
  ```
  Response:
  ```json
  {
    "answer": "string",
    "code": ["pandas snippet", "..."],
    "explanation": "string",
    "columns": ["col1", "col2", "..."],
    "rows": [ { "col1": "...", "col2": "..." } ]
  }
  ```
- `GET /healthz` — healthcheck

Each `/api/ask` is persisted in Postgres (`chat_qa`):  
`session_id, model_name, question, answer, explanation, code, columns, rows, created_at`.

---

## Sample data & prompts

- **sales.csv**
  - “What is the total revenue?”
  - “Average units by region”
  - “Top-3 products by total revenue”
  - “Daily revenue trend”

- **hr.xlsx** (sheets `employees`, `performance`)
  - “Average salary by department”
  - “List employees hired in 2024”
  - “Average June rating by department (join employees and performance)”

---

## Troubleshooting

- **DB init / transient connect errors**  
  Startup includes retries. Verify `DATABASE_URL`, Postgres is running and reachable.

- **Excel parsing**  
  Ensure `openpyxl` is installed (in `requirements.txt`). Re-save the file if corrupted.

- **LLM unavailable**  
  Without `OPENAI_API_KEY`, the rule-based fallback handles only simple questions.

- **Scalar std/var (`.to_frame`) errors**  
  Backend exposes `as_df(x, name='...')`. The prompt requests using it and auto-fixes common `.to_frame(...)` on scalars.

---
