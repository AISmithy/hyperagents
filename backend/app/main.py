from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .engine import HyperAgentEngine
from .github_service import GitHubService
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
github_service = GitHubService(token=settings.github_token)


class RunRequest(BaseModel):
    iterations: int = Field(default=5, ge=1, le=100)


class RepoReviewRequest(BaseModel):
    repo_url: str = Field(min_length=10, max_length=500)


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


@app.post("/api/review-repo")
def review_repo(request: RepoReviewRequest) -> dict:
    try:
        repo_data = github_service.fetch_repo_summary(request.repo_url)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    try:
        return engine.review_repository(request.repo_url, repo_data)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
