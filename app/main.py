from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException

from app.models import (
    AskPromptRequest,
    AskPromptResponse,
    GenerateQuestionsRequest,
    GenerateQuestionsResponse,
)
from app.question_gen import ask_prompt, generate_questions

app = FastAPI(title="Question Generator API", version="1.0.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/questions", response_model=GenerateQuestionsResponse)
async def questions(req: GenerateQuestionsRequest) -> GenerateQuestionsResponse:
    try:
        qs, chosen_model, raw = await generate_questions(
            prompt=req.prompt,
            n=req.question_count,
            variant_count=req.variant_count,
            model=None,
            temperature=0.2,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Ollama error: {e}") from e

    # Keep only valid structured questions.
    qs = [q for q in qs if q.get("question") and len(q.get("variants", [])) >= 2]
    if not qs:
        raise HTTPException(status_code=502, detail="No questions produced by model.")

    include_raw = os.getenv("INCLUDE_RAW", "0") == "1"
    return GenerateQuestionsResponse(model=chosen_model, questions=qs, raw=(raw if include_raw else None))


@app.post("/ask", response_model=AskPromptResponse)
async def ask(req: AskPromptRequest) -> AskPromptResponse:
    try:
        answer, chosen_model, raw = await ask_prompt(
            prompt=req.prompt,
            model=None,
            temperature=0.2,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Ollama error: {e}") from e

    if not answer:
        raise HTTPException(status_code=502, detail="No answer produced by model.")

    include_raw = os.getenv("INCLUDE_RAW", "0") == "1"
    return AskPromptResponse(model=chosen_model, answer=answer, raw=(raw if include_raw else None))

