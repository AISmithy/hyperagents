from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from .account_service import (
    VALID_PROFILES,
    generate_synthetic_repos,
    infer_features_from_github,
    oracle_label,
)
from .database import Database
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
db = Database(settings.db_path)
engine = HyperAgentEngine(llm_service=llm_service, db=db)
github_service = GitHubService(token=settings.github_token)


class RunRequest(BaseModel):
    iterations: int = Field(default=5, ge=1, le=100)


class ResetRequest(BaseModel):
    mode: str = Field(default="hyperagent", pattern="^(hyperagent|baseline|no_archive)$")


class RepoReviewRequest(BaseModel):
    repo_url: str = Field(min_length=10, max_length=500)


class AddAccountRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    platform: str = Field(default="synthetic", pattern="^(synthetic|github)$")
    profile: str = Field(default="mixed")
    n_repos: int = Field(default=10, ge=1, le=50)


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
def reset(request: ResetRequest = ResetRequest()) -> dict:
    engine.reset(mode=request.mode)
    return engine.snapshot()


@app.get("/api/metrics/json")
def metrics_json() -> list:
    return engine.metrics_json()


@app.get("/api/metrics/csv", response_class=PlainTextResponse)
def metrics_csv() -> str:
    return engine.metrics_csv()


# ── Run management ────────────────────────────────────────────────────────────

@app.get("/api/runs")
def list_runs() -> list:
    return db.list_runs()


@app.get("/api/runs/{run_id}")
def get_run(run_id: int) -> dict:
    snapshot = db.load_run(run_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found.")
    return snapshot


@app.post("/api/runs/{run_id}/load")
def load_run(run_id: int) -> dict:
    """Restore a past run into the active engine. Further iterations continue the same run."""
    snapshot = db.load_run(run_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found.")
    engine.load_run_snapshot(snapshot)
    return engine.snapshot()


@app.delete("/api/runs/{run_id}")
def delete_run(run_id: int) -> dict:
    if not db.delete_run(run_id):
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found.")
    return {"deleted": run_id}


@app.post("/api/run")
def run_iterations(request: RunRequest) -> dict:
    engine.run(request.iterations)
    return engine.snapshot()


# ── Account management ────────────────────────────────────────────────────────

@app.post("/api/accounts")
def add_account(request: AddAccountRequest) -> dict:
    """Add an account and scan (or generate) its repos."""
    if request.platform == "synthetic":
        if request.profile not in VALID_PROFILES:
            raise HTTPException(status_code=400, detail=f"profile must be one of {VALID_PROFILES}")
        repos = generate_synthetic_repos(request.name, request.profile, request.n_repos)
    else:
        # GitHub mode: fetch real repos and infer feature scores
        try:
            repo_metas = github_service.list_user_repos(request.name, max_repos=request.n_repos)
        except (ValueError, RuntimeError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        repos = []
        for meta in repo_metas:
            features = infer_features_from_github(meta)
            repos.append({
                "id": f"gh-{request.name}-{meta['name']}",
                "name": meta["name"],
                **features,
                "label": oracle_label(features),
            })

    account_id = db.create_account(request.name, request.platform, request.profile)
    for repo in repos:
        db.save_account_repo(account_id, repo)

    return {
        "id": account_id,
        "name": request.name,
        "platform": request.platform,
        "profile": request.profile,
        "repo_count": len(repos),
        "repos": repos,
    }


@app.get("/api/accounts")
def list_accounts() -> list:
    return db.list_accounts()


@app.get("/api/accounts/{account_id}/repos")
def get_account_repos(account_id: int) -> list:
    repos = db.get_account_repos(account_id)
    if repos is None:
        raise HTTPException(status_code=404, detail=f"Account {account_id} not found.")
    return repos


@app.delete("/api/accounts/{account_id}")
def delete_account(account_id: int) -> dict:
    if not db.delete_account(account_id):
        raise HTTPException(status_code=404, detail=f"Account {account_id} not found.")
    return {"deleted": account_id}


@app.post("/api/accounts/apply-all")
def apply_all_account_repos() -> dict:
    """Push all saved account repos into the engine's live dataset (80% train / 20% test).

    Call /api/reset afterwards to re-seed the evolutionary loop with the
    updated dataset sizes reflected in the new initial agent's evaluation.
    """
    repos = db.list_all_account_repos()
    engine.set_account_repos(repos)
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
