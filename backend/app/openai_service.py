from __future__ import annotations

from dataclasses import asdict
from functools import lru_cache
from importlib.resources import files
import json
from typing import Any

from .settings import Settings

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover
    OpenAI = None


@lru_cache(maxsize=None)
def _load_prompt(filename: str) -> str:
    return files("app.prompts").joinpath(filename).read_text(encoding="utf-8").strip()


@lru_cache(maxsize=None)
def _load_prompt_from(package: str, filename: str) -> str:
    return files(package).joinpath(filename).read_text(encoding="utf-8").strip()


class OpenAIHyperAgentService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._last_error = ""
        self._client = None

        if OpenAI and settings.has_api_key and settings.use_openai:
            self._client = OpenAI(api_key=settings.openai_api_key)

    @property
    def is_enabled(self) -> bool:
        return self._client is not None

    @property
    def last_error(self) -> str:
        return self._last_error

    def metadata(self) -> dict[str, Any]:
        mode = "openai" if self.is_enabled else "heuristic"
        if self.is_enabled:
            reason = "Using OpenAI Responses API for mutation planning and live reviews."
        elif not self.settings.has_api_key:
            reason = "OPENAI_API_KEY is not configured."
        elif not self.settings.use_openai:
            reason = "HYPERAGENTS_USE_OPENAI is not enabled."
        elif OpenAI is None:
            reason = "The openai Python package is not installed."
        else:
            reason = "Using deterministic fallback."

        return {
            "mode": mode,
            "configured": self.settings.use_openai,
            "has_api_key": self.settings.has_api_key,
            "client_ready": self.is_enabled,
            "model": self.settings.openai_model,
            "reason": reason,
            "last_error": self._last_error,
        }

    def propose_mutation(self, parent: Any) -> dict[str, Any] | None:
        if not self.is_enabled:
            return None

        payload = {
            "agent": asdict(parent.agent),
            "evaluation": asdict(parent.evaluation),
            "allowed_review_styles": ["balanced", "strict", "lenient"],
            "feature_names": ["maintainability", "security", "test_coverage", "documentation", "simplicity"],
            "weight_bounds": [0.25, 1.8],
            "threshold_bounds": [2.4, 4.2],
            "step_bounds": {
                "weight_step": [0.04, 0.22],
                "threshold_step": [0.03, 0.14],
                "exploration_scale": [0.05, 0.45],
            },
        }

        prompt = _load_prompt("propose_mutation.md")
        return self._json_response(prompt, payload)

    def mutate_reviewer_prompt(self, parent: Any) -> dict[str, Any] | None:
        """Propose an improved code-reviewer prompt based on a human rating + gaps."""
        if not self.is_enabled:
            return None

        ev = parent.evaluation
        payload = {
            "current_prompt": parent.agent.prompt,
            "rating": ev.rating,
            "strengths": ev.strengths,
            "gaps": ev.gaps,
            "review_excerpt": ev.review_excerpt,
            "codebase_ref": ev.codebase_ref,
        }
        prompt = _load_prompt_from("app.selfimprovingprompt.prompts", "mutate_agent_prompt.md")
        return self._json_response(prompt, payload)

    def review_repository(self, repo_url: str, repo_data: dict[str, Any]) -> dict[str, Any]:
        if not self.is_enabled:
            raise RuntimeError("OpenAI mode is not enabled.")

        prompt = _load_prompt("review_repository.md")
        return self._json_response(prompt, {"repo_url": repo_url, "repo": repo_data})

    def _json_response(self, prompt: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            response = self._client.responses.create(
                model=self.settings.openai_model,
                input=[
                    {
                        "role": "system",
                        "content": [{"type": "input_text", "text": prompt}],
                    },
                    {
                        "role": "user",
                        "content": [{"type": "input_text", "text": json.dumps(payload)}],
                    },
                ],
            )
            text = self._extract_json_text(response.output_text)
            self._last_error = ""
            return json.loads(text)
        except Exception as exc:  # pragma: no cover
            self._last_error = str(exc)
            return {}

    def _extract_json_text(self, text: str) -> str:
        candidate = text.strip()
        if candidate.startswith("```"):
            lines = candidate.splitlines()
            if len(lines) >= 3:
                candidate = "\n".join(lines[1:-1]).strip()

        start = candidate.find("{")
        end = candidate.rfind("}")
        if start == -1 or end == -1:
            raise ValueError("Model did not return JSON.")
        return candidate[start : end + 1]
