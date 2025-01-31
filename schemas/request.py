from typing import List

from pydantic import BaseModel, HttpUrl


class PredictionRequest(BaseModel):
    id: int
    query: str


class PredictionResponse(BaseModel):
    id: int
    answer: str
    reasoning: str
    sources: List[HttpUrl]


class UserRequest(BaseModel):
    messages: str
    context_messages: list = []
    is_test: str = "Fail"
    is_rag: str = "Fail"
    is_full_answ: str = "none"
    final_answ: dict = {}