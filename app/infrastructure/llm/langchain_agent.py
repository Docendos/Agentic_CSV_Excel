from __future__ import annotations

import json
import re
from typing import Dict, List, Any, Tuple, Optional

import pandas as pd

from ..settings import settings

try:
    from langchain_openai import ChatOpenAI
except Exception:
    ChatOpenAI = None


# ---------- prompting ----------

PLAN_SYSTEM = (
    "You are a senior data analyst. "
    "Generate SAFE pandas code to answer the user's question on the provided DataFrames.\n"
    "Return STRICT JSON with keys: code, reasoning, short_answer.\n"
    "Rules:\n"
    "- Use ONLY pandas and the provided DataFrames; do NOT import anything.\n"
    "- Put the final value or DataFrame into a variable named `result`.\n"
    "- If the result is a scalar/Series/DataFrame, wrap it with the helper `as_df(x, name='value')` "
    "  which is available in your environment. Do NOT call `.to_frame()` yourself.\n"
    "- Do not print; no file IO; no network.\n"
)

PLAN_USER_TMPL = """\
DATAFRAMES:
{schema}

QUESTION:
{question}

Respond ONLY with JSON like:
{{"code": "...", "reasoning": "...", "short_answer": "..."}}
"""

def build_schema(tables: Dict[str, pd.DataFrame]) -> str:
    parts = []
    for name, df in tables.items():
        dtypes = ", ".join([f"{c}:{str(df[c].dtype)}" for c in df.columns])
        prev = df.head(3).fillna("null").to_dict(orient="records")
        parts.append(f"- {name}({dtypes})\n  preview: {json.dumps(prev)[:500]}")
    return "\n".join(parts)


# ---------- safety ----------

BAN_PATTERNS = [
    r"\bimport\b",
    r"\bopen\s*\(",
    r"\bos\b",
    r"\bsys\b",
    r"\bsubprocess\b",
    r"\bshutil\b",
    r"\bpathlib\b",
    r"\bpickle\b",
    r"\bjoblib\b",
    r"\burllib\b",
    r"\brequests\b",
    r"\beval\s*\(",
    r"\bexec\s*\(",
    r"__",
    r"\bcompile\s*\(",
    r"\bglobals\s*\(",
    r"\blocals\s*\(",
]

SAFE_BUILTINS = {
    "len": len, "range": range, "min": min, "max": max, "sum": sum,
    "sorted": sorted, "list": list, "dict": dict, "set": set, "tuple": tuple,
    "enumerate": enumerate, "zip": zip, "abs": abs, "round": round,
}

def validate_code_safety(code: str) -> Optional[str]:
    for pat in BAN_PATTERNS:
        if re.search(pat, code):
            return f"Unsafe code rejected by policy (pattern: {pat})."
    return None


def as_df(x, name: str = "value") -> pd.DataFrame:
    """Helper available to the generated code: always return a DataFrame."""
    if isinstance(x, pd.DataFrame):
        return x
    if isinstance(x, pd.Series):
        return x.to_frame().T.reset_index(drop=True)
    return pd.DataFrame([{name: x}])

def execute_pandas_code(tables: Dict[str, pd.DataFrame], code: str) -> pd.DataFrame:
    safe_globals = {"__builtins__": SAFE_BUILTINS, "pd": pd, "as_df": as_df}
    safe_locals: Dict[str, Any] = {**tables}
    exec(code, safe_globals, safe_locals)
    if "result" not in safe_locals:
        for _, v in reversed(list(safe_locals.items())):
            if isinstance(v, (pd.DataFrame, pd.Series, int, float, str)):
                safe_locals["result"] = v
                break
    res = safe_locals.get("result", None)
    return as_df(res)


def _format_number(x: Any) -> str:
    try:
        xv = float(x)
    except Exception:
        return str(x)
    return f"{xv:.12g}"

def answer_from_dataframe(df: pd.DataFrame) -> str:
    if df.empty:
        return "Result is empty."
    if df.shape == (1, 1):
        return _format_number(df.iat[0, 0])
    if df.shape[0] == 1:
        row = df.iloc[0]
        return "; ".join(f"{c}={_format_number(row[c])}" for c in df.columns)
    return f"Returned {len(df)} row(s). Showing first {min(len(df), 10)}."


def _has_llm() -> bool:
    return bool(ChatOpenAI and settings.openai_api_key)

class PandasAgentRunner:
    """
    LLM generates pandas code; we validate & execute in a restricted namespace.
    - Encourage using as_df(...) to avoid .to_frame() on scalars.
    - Auto-fix common mistake: `.to_frame(...)` on a scalar result.
    - Short answer is derived from the executed result (no duplicates).
    """

    def __init__(self, tables: Dict[str, pd.DataFrame]):
        self.tables = tables

    async def ask(self, question: str) -> Tuple[str, List[str], str, List[str], List[dict]]:
        if not _has_llm():
            return rule_based_answer(self.tables, question)

        llm = ChatOpenAI(model=settings.openai_model, temperature=0.0, api_key=settings.openai_api_key)  # type: ignore
        schema = build_schema(self.tables)
        user_msg = PLAN_USER_TMPL.format(schema=schema, question=question.strip())

        try:
            resp = await llm.ainvoke([
                {"role": "system", "content": PLAN_SYSTEM},
                {"role": "user", "content": user_msg},
            ])
            content = getattr(resp, "content", "") or ""
        except Exception:
            return rule_based_answer(self.tables, question)

        code, reasoning, llm_short = "", "", ""
        try:
            data = json.loads(content)
            code = str(data.get("code", "")).strip()
            reasoning = str(data.get("reasoning", "")).strip()
            llm_short = str(data.get("short_answer", "")).strip()
        except Exception:
            m = re.search(r"```(?:python)?\s*(.*?)```", content, re.S | re.I)
            code = (m.group(1) if m else "").strip()
            reasoning = "Generated from non-JSON response."
            llm_short = ""

        if not code:
            return rule_based_answer(self.tables, question)

        unsafe = validate_code_safety(code)
        if unsafe:
            return ("Request blocked by safety policy.", [code], unsafe, [], [])

        try:
            df = execute_pandas_code(self.tables, code)
        except Exception as e:
            if "to_frame" in code and "result" in code:
                m = re.search(r"^\s*result\s*=\s*(.+)$", code, re.M | re.S)
                if m:
                    expr = m.group(1).strip()
                    name_match = re.search(r"\.to_frame\s*\(\s*name\s*=\s*['\"]([^'\"]+)['\"]\s*\)", expr)
                    col_name = name_match.group(1) if name_match else "value"
                    expr_no_tf = re.sub(r"\.to_frame\s*\(.*?\)", "", expr)
                    fixed_code = f"result = as_df({expr_no_tf}, name='{col_name}')"
                    try:
                        df = execute_pandas_code(self.tables, fixed_code)
                        reasoning2 = (reasoning or "Executed pandas code.") + "\n\nAuto-fix: replaced `.to_frame(...)` with `as_df(...)`."
                        preview = df.head(10).fillna("null")
                        cols, rows = list(preview.columns), preview.to_dict(orient="records")
                        short = answer_from_dataframe(df)
                        return short, [code, fixed_code], reasoning2, cols, rows
                    except Exception as e2:
                        return ("Execution error.", [code, fixed_code], f"Exception after auto-fix: {e2}", [], [])
            return ("Execution error.", [code], f"Exception: {e}", [], [])

        preview = df.head(10).fillna("null")
        cols, rows = list(preview.columns), preview.to_dict(orient="records")
        short = answer_from_dataframe(df)
        expl = reasoning or "Executed pandas code."
        return short, [code], expl, cols, rows

def rule_based_answer(tables: Dict[str, pd.DataFrame], question: str):
    if not tables:
        return ("Please upload a table first.", [], "No data available.", [], [])
    name, df = list(tables.items())[0]
    q = question.lower()
    code_blocks: List[str] = []

    if any(k in q for k in ["deviation", "deviance", "diviance", "diviation", "std"]):
        col = "rating" if "rating" in df.columns else None
        if col:
            val = float(df[col].std())
            code_blocks.append(f"as_df({name}['{col}'].std(), name='{col}_std')")
            return (_format_number(val), code_blocks, f"Computed standard deviation of '{col}'.", [f"{col}_std"], [{f"{col}_std": val}])

    if any(k in q for k in ["total revenue", "sum revenue", "revenue total", "overall revenue"]):
        if "revenue" in df.columns:
            val = float(df["revenue"].sum())
            code_blocks.append(f"as_df({name}['revenue'].sum(), name='revenue_total')")
            return (_format_number(val), code_blocks, "Summed the revenue column.", ["revenue_total"], [{"revenue_total": val}])

    if any(k in q for k in ["average", "avg", "mean"]):
        num_cols = df.select_dtypes("number").columns.tolist()
        col = num_cols[0] if num_cols else None
        if col:
            val = float(df[col].mean())
            code_blocks.append(f"as_df({name}['{col}'].mean(), name='{col}_mean')")
            return (_format_number(val), code_blocks, f"Computed mean over '{col}'.", [f"{col}_mean"], [{f"{col}_mean": val}])

    if "count" in q or "how many" in q:
        n = int(len(df))
        code_blocks.append(f"as_df(len({name}), name='count')")
        return (str(n), code_blocks, "Counted rows.", ["count"], [{"count": n}])

    code_blocks.append(f"{name}.head(5)")
    preview = df.head(5).fillna("null").to_dict(orient="records")
    return ("Showing the first 5 rows.", code_blocks, "Previewed the first rows.", list(df.columns), preview)
