from __future__ import annotations
from ...infrastructure.data.dataset_repo import InMemoryDatasetRepository
from ...infrastructure.llm.langchain_agent import PandasAgentRunner
from ...domain.exceptions import NoDatasetError
from ..services.answer_builder import to_agent_answer

class AskQuestionUseCase:
    def __init__(self, repo: InMemoryDatasetRepository):
        self.repo = repo

    async def execute(self, session_id: str, question: str):
        dataset = self.repo.get(session_id)
        if not dataset:
            raise NoDatasetError("Please upload a table first.")
        runner = PandasAgentRunner(dataset.tables)
        answer, code_blocks, reasoning, cols, rows = await runner.ask(question)
        aa = to_agent_answer(answer, code_blocks, reasoning, cols, rows)
        return {
            "answer": aa.answer,
            "code": aa.code_blocks,
            "explanation": aa.reasoning,
            "columns": aa.columns or [],
            "rows": aa.table_preview or [],
        }
