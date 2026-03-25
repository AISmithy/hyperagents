from __future__ import annotations

from dataclasses import asdict
import json
from typing import Any

from .settings import Settings

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover
    OpenAI = None


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
            "allowed_review_styles": ["balanced", "skeptical", "ambitious"],
            "feature_names": ["novelty", "rigor", "clarity", "reproducibility", "significance"],
            "weight_bounds": [0.25, 1.8],
            "threshold_bounds": [2.4, 4.2],
            "step_bounds": {
                "weight_step": [0.04, 0.22],
                "threshold_step": [0.03, 0.14],
                "exploration_scale": [0.05, 0.45],
            },
        }

        prompt = (
            "You are the meta-policy inside a self-improving hyperagent. "
            "Given the parent agent state and evaluation, propose one child mutation. "
            "Return JSON only with this exact shape: "
            "{"
            "\"task_policy\":{\"weights\":{\"novelty\":number,\"rigor\":number,\"clarity\":number,\"reproducibility\":number,\"significance\":number},"
            "\"threshold\":number,\"review_style\":\"balanced|skeptical|ambitious\"},"
            "\"meta_policy\":{\"focus_metric\":\"novelty|rigor|clarity|reproducibility|significance\","
            "\"weight_step\":number,\"threshold_step\":number,\"exploration_scale\":number},"
            "\"memory_note\":string,"
            "\"rationale\":string"
            "}. "
            "Keep values inside the provided bounds and bias toward fixing the parent's observed errors."
        )
        return self._json_response(prompt, payload)

    def review_submission(self, title: str, abstract: str) -> dict[str, Any]:
        if not self.is_enabled:
            raise RuntimeError("OpenAI mode is not enabled.")

        prompt = (
            "You are an expert research reviewer. "
            "Review the proposed paper abstract and return JSON only with this shape: "
            "{"
            "\"recommendation\":\"accept|weak_accept|borderline|weak_reject|reject\","
            "\"score\":number,"
            "\"strengths\":[string,string,string],"
            "\"risks\":[string,string,string],"
            "\"summary\":string"
            "}. "
            "Use a 1-10 score."
        )
        return self._json_response(prompt, {"title": title, "abstract": abstract})

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
