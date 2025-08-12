from __future__ import annotations
from typing import Dict, List
import pandas as pd
from ...infrastructure.data.dataset_repo import Dataset, InMemoryDatasetRepository
from ...domain.models import TableMeta, ColumnMeta
from ...infrastructure.settings import settings

def infer_tables_from_file(file_path: str) -> Dict[str, pd.DataFrame]:
    if file_path.lower().endswith(('.xlsx', '.xls')):
        xls = pd.ExcelFile(file_path)
        return { (sheet or 'sheet').replace(' ', '_'): xls.parse(sheet) for sheet in xls.sheet_names }
    else:
        df = pd.read_csv(file_path)
        return { 'data': df }

def build_table_meta(df_map: Dict[str, pd.DataFrame]) -> List[TableMeta]:
    metas: List[TableMeta] = []
    for name, df in df_map.items():
        cols = [ColumnMeta(c, str(df[c].dtype)) for c in df.columns]
        preview = df.head(settings.max_preview_rows).fillna("null").to_dict(orient="records")
        metas.append(TableMeta(name=name, columns=cols, preview=preview))
    return metas

class UploadTableUseCase:
    def __init__(self, repo: InMemoryDatasetRepository):
        self.repo = repo

    def execute(self, session_id: str, file_path: str) -> List[TableMeta]:
        tables = infer_tables_from_file(file_path)
        if not tables:
            raise ValueError("No tables found in file.")
        for name, df in tables.items():
            if df.empty:
                raise ValueError(f"Sheet/Table '{name}' is empty.")
        self.repo.save(session_id, Dataset(tables=tables))
        return build_table_meta(tables)
