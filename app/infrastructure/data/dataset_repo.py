from __future__ import annotations
from typing import Dict
from dataclasses import dataclass
import pandas as pd

@dataclass
class Dataset:
    tables: Dict[str, pd.DataFrame]    # table_name -> df

class InMemoryDatasetRepository:
    def __init__(self):
        self._store: Dict[str, Dataset] = {}

    def save(self, session_id: str, dataset: Dataset) -> None:
        self._store[session_id] = dataset

    def get(self, session_id: str) -> Dataset | None:
        return self._store.get(session_id)

    def clear(self, session_id: str) -> None:
        self._store.pop(session_id, None)
