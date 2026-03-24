from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .engine import HyperAgentEngine

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

engine = HyperAgentEngine()


class RunRequest(BaseModel):
    iterations: int = Field(default=5, ge=1, le=100)


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
