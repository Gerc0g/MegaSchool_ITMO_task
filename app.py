import time
from fastapi import FastAPI, HTTPException, Request
from pydantic import HttpUrl
from schemas.request import PredictionRequest, PredictionResponse, UserRequest
from src.workflow import RequestWorkflow

app = FastAPI()
app_workflow = RequestWorkflow()


@app.post("/api/request", response_model=PredictionResponse)
async def predict(request: Request, body: PredictionRequest):
    """Асинхронный обработчик API-запроса."""
    if not app_workflow:
        raise HTTPException(status_code=500, detail="Workflow не инициализирован")

    state = UserRequest(messages=body.query).model_dump()
    result = await app_workflow.process(state)

    if not isinstance(result, dict) or "final_answ" not in result:
        raise HTTPException(status_code=500, detail="Invalid workflow response format")

    answer_data = result["final_answ"]

    response = PredictionResponse(
        id=body.id,
        answer=str(answer_data["answer"]),
        reasoning=f"{answer_data.get("reasoning", "")} ==== Сгенерировано с помошью OpenaiAPI, поиск информации YandexAPI === ",
        sources=[HttpUrl(src) for src in answer_data.get("sources", []) if isinstance(src, str)]
    )

    return response
