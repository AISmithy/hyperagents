from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .engine import HyperAgentEngine
from .openai_service import OpenAIHyperAgentService
from .settings import get_settings

app = FastAPI(
    title="Hyperagents API",
    version="0.1.0",
    description="Proof-of-concept backend for a HyperAgents-inspired framework.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

settings = get_settings()
llm_service = OpenAIHyperAgentService(settings)
engine = HyperAgentEngine(llm_service=llm_service)


class RunRequest(BaseModel):
    iterations: int = Field(default=5, ge=1, le=100)


class ReviewRequest(BaseModel):
    title: str = Field(min_length=4, max_length=200)
    abstract: str = Field(min_length=30, max_length=6000)


@app.get("/")
def read_root() -> dict[str, str]:
    return {
        "message": "Hyperagents backend is running.",
        "state_endpoint": "/api/state",
    }


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/state")
def get_state() -> dict:
    return engine.snapshot()


@app.post("/api/reset")
def reset() -> dict:
    engine.reset()
    return engine.snapshot()


@app.post("/api/run")
def run_iterations(request: RunRequest) -> dict:
    engine.run(request.iterations)
    return engine.snapshot()


@app.post("/api/review")
def review_submission(request: ReviewRequest) -> dict:
    try:
        return engine.review_submission(request.title, request.abstract)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
