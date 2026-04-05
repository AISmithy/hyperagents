"""prompt_engine.py
==================
A self-contained HyperAgent loop whose TaskPolicy is a **text prompt**
rather than a set of numerical weights.

Use case
--------
You have a code-reviewer agent (e.g. code-reviewer.md).  After each real
review session you rate how useful the review was (1–5).  This engine uses
that signal to evolve the prompt over time, keeping an archive of every
variant so it can explore past stepping stones rather than greedily
hill-climbing.

Key differences from engine.py
-------------------------------
- TaskPolicy = prompt string (no weights, no threshold)
- Evaluation = human rating 1–5, normalised to fitness 0.0–1.0
- Mutation   = LLM rewrites the prompt guided by what the review missed
- No synthetic dataset — every evaluation comes from a real review cycle

Public API
----------
    engine = PromptEngine(llm_service)
    engine.reset(seed_prompt="You are a code reviewer …")

    # After a real review session:
    engine.submit_review(
        review_text="Here is my review …",
        rating=4,
        strengths=["caught SQL injection", "good tone"],
        gaps=["missed missing tests in auth module"],
        codebase_ref="my-repo @ main",
    )

    best_prompt = engine.best_entry.agent.prompt
    # Write best_prompt back to code-reviewer.md
"""
from __future__ import annotations

import csv
import datetime
import pathlib
import random
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .openai_service import OpenAIHyperAgentService

LOG_PATH = pathlib.Path("results/prompt_runs.csv")

_DEFAULT_SEED_PROMPT = """\
You are a senior code reviewer. Review the provided codebase and give structured feedback.

For each issue found, specify:
- Severity: critical / warning / suggestion
- Location: file and line number if possible
- Description: what the problem is and why it matters
- Fix: a concrete suggested improvement

Focus areas (in priority order):
1. Security vulnerabilities
2. Missing or broken tests
3. Maintainability problems
4. Documentation gaps
5. Code simplicity

Be specific and actionable. Avoid vague comments like "improve naming".\
"""


def _normalise_rating(rating: int) -> float:
    """Convert a 1–5 human rating to a 0.0–1.0 fitness score."""
    return round((max(1, min(5, rating)) - 1) / 4.0, 4)


@dataclass
class PromptAgent:
    agent_id: str
    parent_id: str | None
    generation: int
    prompt: str                         # The actual reviewer prompt text
    meta_notes: list[str] = field(default_factory=list)   # What past iterations learned
    lineage_notes: list[str] = field(default_factory=list)


@dataclass
class PromptEvaluation:
    fitness: float          # Normalised rating: (rating-1) / 4
    rating: int             # Raw human rating 1–5
    review_excerpt: str     # First 500 chars of the actual review (for context)
    codebase_ref: str       # e.g. "my-repo @ commit abc123"
    strengths: list[str]    # What the review got right (human-supplied)
    gaps: list[str]         # What the review missed (human-supplied)


@dataclass
class PromptArchiveEntry:
    agent: PromptAgent
    evaluation: PromptEvaluation
    created_iteration: int


class PromptEngine:
    """Self-improving code-reviewer prompt engine.

    Each call to submit_review() is one iteration:
      1. Record the rating for the current best prompt.
      2. Mutate → produce a candidate improved prompt via LLM.
      3. Store both in the archive.
      4. The new prompt becomes the active one for the next review.
    """

    def __init__(self, llm_service: OpenAIHyperAgentService | None = None) -> None:
        self._llm = llm_service
        self._next_id = 0
        self.archive: list[PromptArchiveEntry] = []
        self.history: list[dict[str, Any]] = []   # per-iteration summary log
        self.iterations_completed = 0
        self._current_agent: PromptAgent | None = None

    # ── Public API ────────────────────────────────────────────────────────────

    def reset(self, seed_prompt: str | None = None) -> None:
        """Start a fresh run.  Optionally supply the initial prompt text.
        If omitted, a sensible default is used.
        Pass the contents of your code-reviewer.md here."""
        self._next_id = 0
        self.archive = []
        self.history = []
        self.iterations_completed = 0
        prompt = (seed_prompt or _DEFAULT_SEED_PROMPT).strip()
        self._current_agent = PromptAgent(
            agent_id=self._new_id(),
            parent_id=None,
            generation=0,
            prompt=prompt,
            meta_notes=["Seed prompt — no review history yet."],
            lineage_notes=["Seed prompt loaded from user-supplied agent file."],
        )

    def submit_review(
        self,
        review_text: str,
        rating: int,
        strengths: list[str] | None = None,
        gaps: list[str] | None = None,
        codebase_ref: str = "",
    ) -> dict[str, Any]:
        """Record the result of one real review cycle and evolve the prompt.

        Parameters
        ----------
        review_text:   The full text output of the review (or a summary).
        rating:        Human quality rating, 1 (poor) to 5 (excellent).
        strengths:     List of things the review got right.
        gaps:          List of things the review missed or got wrong.
        codebase_ref:  Free-text reference to the reviewed codebase
                       (e.g. "my-repo @ main", "PR #42").

        Returns
        -------
        dict with: new_prompt, current_agent_id, iteration, fitness, rating
        """
        if self._current_agent is None:
            raise RuntimeError("Call reset() before submit_review().")

        strengths = strengths or []
        gaps = gaps or []

        eval_ = PromptEvaluation(
            fitness=_normalise_rating(rating),
            rating=rating,
            review_excerpt=review_text[:500],
            codebase_ref=codebase_ref,
            strengths=strengths,
            gaps=gaps,
        )

        entry = PromptArchiveEntry(
            agent=self._current_agent,
            evaluation=eval_,
            created_iteration=self.iterations_completed,
        )
        self.archive.append(entry)
        self.iterations_completed += 1

        # Mutate → produce next prompt
        next_agent = self._mutate(entry)
        self._current_agent = next_agent

        self._record_history(entry, next_agent)
        self._log_csv(entry)

        return {
            "iteration": self.iterations_completed,
            "rated_agent_id": entry.agent.agent_id,
            "fitness": eval_.fitness,
            "rating": rating,
            "new_agent_id": next_agent.agent_id,
            "new_prompt": next_agent.prompt,
            "meta_notes": next_agent.meta_notes,
        }

    def snapshot(self) -> dict[str, Any]:
        """Full engine state — suitable for the API to return."""
        best = self.best_entry
        return {
            "iterations_completed": self.iterations_completed,
            "active_prompt": self._current_agent.prompt if self._current_agent else "",
            "active_agent_id": self._current_agent.agent_id if self._current_agent else None,
            "best_agent": self._serialise_entry(best) if best else None,
            "archive": [self._serialise_entry(e) for e in self.archive],
            "history": self.history,
        }

    @property
    def best_entry(self) -> PromptArchiveEntry | None:
        if not self.archive:
            return None
        return max(self.archive, key=lambda e: (e.evaluation.fitness, e.created_iteration))

    @property
    def active_prompt(self) -> str:
        if self._current_agent is None:
            raise RuntimeError("Call reset() first.")
        return self._current_agent.prompt

    # ── Mutation ──────────────────────────────────────────────────────────────

    def _mutate(self, parent: PromptArchiveEntry) -> PromptAgent:
        """Produce a child agent with an improved prompt.

        Tries LLM mutation first.  Falls back to a simple heuristic if the
        LLM is not configured or returns nothing useful.
        """
        if self._llm is not None and self._llm.is_enabled:
            result = self._llm.mutate_reviewer_prompt(parent)
            if result and result.get("improved_prompt"):
                return PromptAgent(
                    agent_id=self._new_id(),
                    parent_id=parent.agent.agent_id,
                    generation=parent.agent.generation + 1,
                    prompt=result["improved_prompt"].strip(),
                    meta_notes=(parent.agent.meta_notes + [result.get("rationale", "LLM mutation.")])[-5:],
                    lineage_notes=(parent.agent.lineage_notes + [result.get("rationale", "LLM mutation.")])[-6:],
                )

        # Heuristic fallback: append a targeted instruction based on gaps
        return self._heuristic_mutate(parent)

    def _heuristic_mutate(self, parent: PromptArchiveEntry) -> PromptAgent:
        """If no LLM is available, append gap-targeted instructions to the prompt."""
        gaps = parent.evaluation.gaps
        rating = parent.evaluation.rating

        additions: list[str] = []
        if gaps:
            additions.append(
                "\n\nBased on past reviews, pay special attention to:\n"
                + "\n".join(f"- {g}" for g in gaps[:3])
            )
        if rating <= 2:
            additions.append(
                "\n\nBe more thorough. Previous review was rated poorly. "
                "Cover all files, not just entry points."
            )
        elif rating == 5:
            additions.append(
                "\n\nMaintain current quality. Previous review was rated excellent."
            )

        note = f"Heuristic: added {len(additions)} targeted instruction(s) based on gaps."
        new_prompt = parent.agent.prompt + "".join(additions)

        return PromptAgent(
            agent_id=self._new_id(),
            parent_id=parent.agent.agent_id,
            generation=parent.agent.generation + 1,
            prompt=new_prompt,
            meta_notes=(parent.agent.meta_notes + [note])[-5:],
            lineage_notes=(parent.agent.lineage_notes + [note])[-6:],
        )

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _new_id(self) -> str:
        agent_id = f"pagent-{self._next_id:03d}"
        self._next_id += 1
        return agent_id

    def _record_history(self, rated: PromptArchiveEntry, next_agent: PromptAgent) -> None:
        best = self.best_entry
        self.history.append({
            "iteration": self.iterations_completed,
            "rated_agent_id": rated.agent.agent_id,
            "next_agent_id": next_agent.agent_id,
            "rating": rated.evaluation.rating,
            "fitness": rated.evaluation.fitness,
            "codebase_ref": rated.evaluation.codebase_ref,
            "gaps_count": len(rated.evaluation.gaps),
            "best_fitness_so_far": best.evaluation.fitness if best else 0.0,
            "archive_size": len(self.archive),
        })

    def _log_csv(self, entry: PromptArchiveEntry) -> None:
        LOG_PATH.parent.mkdir(exist_ok=True)
        with open(LOG_PATH, "a", newline="") as f:
            csv.writer(f).writerow([
                datetime.datetime.utcnow().isoformat(),
                self.iterations_completed,
                entry.agent.agent_id,
                entry.evaluation.rating,
                entry.evaluation.fitness,
                entry.evaluation.codebase_ref,
                "; ".join(entry.evaluation.gaps),
            ])

    def _serialise_entry(self, entry: PromptArchiveEntry) -> dict[str, Any]:
        return {
            "agent": {
                "agent_id": entry.agent.agent_id,
                "parent_id": entry.agent.parent_id,
                "generation": entry.agent.generation,
                "prompt": entry.agent.prompt,
                "meta_notes": entry.agent.meta_notes,
                "lineage_notes": entry.agent.lineage_notes,
            },
            "evaluation": {
                "fitness": entry.evaluation.fitness,
                "rating": entry.evaluation.rating,
                "review_excerpt": entry.evaluation.review_excerpt,
                "codebase_ref": entry.evaluation.codebase_ref,
                "strengths": entry.evaluation.strengths,
                "gaps": entry.evaluation.gaps,
            },
            "created_iteration": entry.created_iteration,
        }
