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
from .selfimprovingprompt import PromptEngine
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
prompt_engine = PromptEngine(
    llm_service=llm_service,
    write_back_path=settings.reviewer_prompt_path,
)


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


# ── Prompt Agent (self-improving code-reviewer prompt) ────────────────────────

class PromptResetRequest(BaseModel):
    seed_prompt: str = Field(
        default="",
        description="Initial prompt text. Leave empty to use the built-in default. "
                    "Pass the contents of your code-reviewer.md here.",
    )


class SubmitReviewRequest(BaseModel):
    review_text: str = Field(
        min_length=10,
        description="The full output of the review that was just run.",
    )
    rating: int = Field(
        ge=1, le=5,
        description="Your rating of the review quality: 1 (poor) to 5 (excellent).",
    )
    strengths: list[str] = Field(
        default_factory=list,
        description="What the review got right (used to guide mutation).",
    )
    gaps: list[str] = Field(
        default_factory=list,
        description="What the review missed or got wrong (used to guide mutation).",
    )
    codebase_ref: str = Field(
        default="",
        description="Free-text reference to the reviewed codebase, e.g. 'my-repo @ main'.",
    )


@app.get("/api/promptagent/state")
def promptagent_state() -> dict:
    """Return the current state of the prompt engine: active prompt, archive, history."""
    return prompt_engine.snapshot()


@app.post("/api/promptagent/reset")
def promptagent_reset(request: PromptResetRequest = PromptResetRequest()) -> dict:
    """Start a fresh run.  Pass your code-reviewer.md contents as seed_prompt."""
    prompt_engine.reset(seed_prompt=request.seed_prompt or None)
    return prompt_engine.snapshot()


@app.post("/api/promptagent/submit")
def promptagent_submit(request: SubmitReviewRequest) -> dict:
    """Record the result of one real review cycle and get back an improved prompt.

    Workflow
    --------
    1. Run your current active prompt against your codebase.
    2. Read the review output.
    3. Rate it 1–5 and note what it got right (strengths) and what it missed (gaps).
    4. POST to this endpoint.
    5. The response contains new_prompt — use it for the next review cycle.
    6. Repeat.
    """
    try:
        result = prompt_engine.submit_review(
            review_text=request.review_text,
            rating=request.rating,
            strengths=request.strengths,
            gaps=request.gaps,
            codebase_ref=request.codebase_ref,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return result


@app.get("/api/promptagent/export")
def promptagent_export() -> dict:
    """Return the best prompt found so far as plain text.

    Use this to overwrite your code-reviewer.md:
        curl .../api/promptagent/export | jq -r .prompt > code-reviewer.md
    """
    best = prompt_engine.best_entry
    if best is None:
        active = prompt_engine.active_prompt
        return {"prompt": active, "source": "active (no reviews submitted yet)", "fitness": None}
    return {
        "prompt": best.agent.prompt,
        "agent_id": best.agent.agent_id,
        "generation": best.agent.generation,
        "fitness": best.evaluation.fitness,
        "rating": best.evaluation.rating,
        "source": "best archived agent",
    }
