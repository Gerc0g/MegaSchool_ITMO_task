from langgraph.graph import StateGraph, END
from typing import TypedDict

from src.nodes import (
    route_req,
    retrive_vectorstore,
    retrieve_web,
    store_in_vector_db,
    generate
)


class AgentState(TypedDict):
    messages: str
    context_messages: list
    is_test: str
    is_rag: str
    is_full_answ: str
    final_answ: dict


class RequestWorkflow:
    """Класс для управления графом запросов (асинхронная версия)"""

    def __init__(self):
        """Инициализация и компиляция графа состояний"""
        self.workflow = StateGraph(AgentState)

        self.workflow.add_node("route_req", route_req)
        self.workflow.add_node("retrive_vectorstore", retrive_vectorstore)
        self.workflow.add_node("retrieve_web", retrieve_web)
        self.workflow.add_node("store_in_vector_db", store_in_vector_db)
        self.workflow.add_node("generate", generate)

        self.workflow.set_entry_point("route_req")

        self.workflow.add_conditional_edges(
            "route_req",
            lambda state: state["is_test"],
            {
                "Pass": "retrive_vectorstore",
                "Fail": END
            }
        )

        self.workflow.add_conditional_edges(
            "retrive_vectorstore",
            lambda state: state["is_rag"],
            {
                "Pass": "generate",
                "Fail": "retrieve_web",
            }
        )

        self.workflow.add_edge("retrieve_web", "store_in_vector_db")
        self.workflow.add_edge("store_in_vector_db", "generate")
        self.workflow.add_edge("generate", END)

        self.compiled_workflow = self.workflow.compile()

    async def process(self, input_state: AgentState):
        """Запускает граф с переданным состоянием (асинхронно)"""
        return await self.compiled_workflow.ainvoke(input_state)
