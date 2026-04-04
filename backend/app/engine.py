from __future__ import annotations

import csv
import datetime
import pathlib
from copy import deepcopy
from dataclasses import asdict, dataclass, field
import random
from typing import Any, TYPE_CHECKING

from .datasets import TEST_REPOS, TRAIN_REPOS

if TYPE_CHECKING:
    from .database import Database
    from .openai_service import OpenAIHyperAgentService

LOG_PATH = pathlib.Path("results/runs.csv")

FEATURES = ("maintainability", "security", "test_coverage", "documentation", "simplicity")
STYLE_THRESHOLD_OFFSET = {
    "balanced": 0.0,
    "strict": 0.09,
    "lenient": -0.09,
}


def log_result(
    run_id: int | None,
    iteration: int,
    agent_id: str,
    train_score: float,
    test_score: float,
    meta_policy: "MetaPolicy",
    condition: str,
) -> None:
    LOG_PATH.parent.mkdir(exist_ok=True)
    with open(LOG_PATH, "a", newline="") as f:
        csv.writer(f).writerow([
            datetime.datetime.utcnow().isoformat(),
            run_id, iteration, agent_id,
            train_score, test_score,
            str(asdict(meta_policy)), condition,
        ])


def clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def average_feature_map(items: list[dict[str, Any]]) -> dict[str, float]:
    if not items:
        return {feature: 0.0 for feature in FEATURES}
    return {
        feature: round(sum(item[feature] for item in items) / len(items), 4)
        for feature in FEATURES
    }


@dataclass
class TaskPolicy:
    weights: dict[str, float]
    threshold: float
    review_style: str


@dataclass
class MetaPolicy:
    focus_metric: str
    weight_step: float
    threshold_step: float
    exploration_scale: float
    memory: list[str] = field(default_factory=list)


@dataclass
class HyperAgent:
    agent_id: str
    parent_id: str | None
    generation: int
    task_policy: TaskPolicy
    meta_policy: MetaPolicy
    lineage_notes: list[str] = field(default_factory=list)


@dataclass
class Evaluation:
    fitness: float
    train_accuracy: float
    test_accuracy: float
    false_positive_count: int
    false_negative_count: int
    false_positive_feature_avgs: dict[str, float]
    false_negative_feature_avgs: dict[str, float]
    summary: str


@dataclass
class ArchiveEntry:
    agent: HyperAgent
    evaluation: Evaluation
    created_iteration: int


VALID_MODES = {"hyperagent", "baseline", "no_archive"}


class HyperAgentEngine:
    def __init__(
        self,
        llm_service: OpenAIHyperAgentService | None = None,
        db: Database | None = None,
        seed: int = 7,
    ) -> None:
        self._llm_service = llm_service
        self._db = db
        self._seed = seed
        self._rng = random.Random(seed)
        # Extra repos injected from accounts — persists across resets
        self._extra_train_repos: list[dict] = []
        self._extra_test_repos: list[dict] = []
        self._recalculate_averages()
        self._mode = "hyperagent"
        self._freeze_meta = False
        self._seed_meta_policy: MetaPolicy | None = None
        self._last_mutation_was_llm = False
        self._run_id: int | None = None
        self.reset()

    def reset(self, mode: str = "hyperagent") -> None:
        if mode not in VALID_MODES:
            raise ValueError(f"mode must be one of {VALID_MODES}")
        self._mode = mode
        self._freeze_meta = mode == "baseline"
        self._rng = random.Random(self._seed)
        self._next_id = 0
        self._last_mutation_was_llm = False
        self.iterations_completed = 0
        self.archive: list[ArchiveEntry] = []
        self.progress: list[dict[str, Any]] = []
        self.recent_events: list[dict[str, Any]] = []
        initial_agent = self._build_initial_agent()
        self._seed_meta_policy = deepcopy(initial_agent.meta_policy)
        initial_entry = ArchiveEntry(
            agent=initial_agent,
            evaluation=self._evaluate_agent(initial_agent),
            created_iteration=0,
        )
        self.archive.append(initial_entry)
        self._record_progress(initial_entry)
        log_result(
            self._run_id, 0, initial_agent.agent_id,
            initial_entry.evaluation.train_accuracy,
            initial_entry.evaluation.test_accuracy,
            initial_agent.meta_policy, self._mode,
        )

        if self._db is not None:
            self._run_id = self._db.create_run(self._mode, self._seed)
            self._db.save_archive_entry(self._run_id, self._serialize_entry(initial_entry))
            self._db.save_progress(self._run_id, self.progress[-1])

    def run(self, iterations: int) -> None:
        for _ in range(iterations):
            parent = self._select_parent()
            child = self._mutate(parent)
            child_eval = self._evaluate_agent(child)
            delta = round(child_eval.fitness - parent.evaluation.fitness, 4)
            self._post_evaluation_meta_adjustment(child, delta)
            entry = ArchiveEntry(
                agent=child,
                evaluation=child_eval,
                created_iteration=self.iterations_completed + 1,
            )
            self.archive.append(entry)
            self.iterations_completed += 1
            log_result(
                self._run_id, self.iterations_completed, child.agent_id,
                child_eval.train_accuracy, child_eval.test_accuracy,
                child.meta_policy, self._mode,
            )
            self.recent_events.append(
                {
                    "iteration": self.iterations_completed,
                    "parent_id": parent.agent.agent_id,
                    "child_id": child.agent_id,
                    "fitness_delta": delta,
                    "summary": child_eval.summary,
                }
            )
            self.recent_events = self.recent_events[-12:]
            self._record_progress(entry)

            if self._db is not None and self._run_id is not None:
                self._db.save_archive_entry(self._run_id, self._serialize_entry(entry))
                self._db.save_progress(self._run_id, self.progress[-1])
                self._db.save_event(self._run_id, self.recent_events[-1])
                self._db.update_run(
                    self._run_id,
                    self.iterations_completed,
                    self.best_entry.evaluation.fitness,
                    self.best_entry.evaluation.test_accuracy,
                )

    def snapshot(self) -> dict[str, Any]:
        best = self.best_entry
        return {
            "project": "hyperagents",
            "domain": "code-review-simulator",
            "description": (
                "A HyperAgents-inspired proof-of-concept where each agent "
                "contains task behavior and self-modification behavior."
            ),
            "mode": self._mode,
            "run_id": self._run_id,
            "iterations_completed": self.iterations_completed,
            "provider": self._provider_snapshot(),
            "dataset": {
                "train_size": len(self._get_train_repos()),
                "test_size": len(self._get_test_repos()),
                "base_train_size": len(TRAIN_REPOS),
                "base_test_size": len(TEST_REPOS),
                "extra_train_size": len(self._extra_train_repos),
                "extra_test_size": len(self._extra_test_repos),
            },
            "best_agent": self._serialize_entry(best),
            "archive": [self._serialize_entry(entry) for entry in self.archive],
            "progress": self.progress,
            "recent_events": list(reversed(self.recent_events)),
        }

    def metrics_json(self) -> list[dict[str, Any]]:
        """Full per-iteration log suitable for analysis or export."""
        return [dict(row, mode=self._mode) for row in self.progress]

    def metrics_csv(self) -> str:
        rows = self.metrics_json()
        if not rows:
            return ""
        columns = list(rows[0].keys())
        lines = [",".join(columns)]
        for row in rows:
            lines.append(",".join(str(row.get(col, "")) for col in columns))
        return "\n".join(lines)

    def load_run_snapshot(self, snapshot: dict[str, Any]) -> None:
        """Restore engine in-memory state from a persisted run snapshot.

        Further calls to run() will append to the same DB run record so the
        full lineage stays in one place.
        """
        mode = snapshot.get("mode", "hyperagent")
        self._mode = mode
        self._freeze_meta = mode == "baseline"
        self._rng = random.Random(self._seed)
        self._last_mutation_was_llm = False
        self.iterations_completed = snapshot["iterations_completed"]
        self.archive = [self._deserialize_entry(e) for e in snapshot["archive"]]
        self.progress = [dict(r) for r in snapshot["progress"]]
        # recent_events in snapshot is newest-first; store oldest-first internally
        self.recent_events = list(reversed(snapshot["recent_events"]))

        # Advance _next_id past all existing IDs to prevent collisions
        self._next_id = 0
        for entry in self.archive:
            try:
                n = int(entry.agent.agent_id.split("-")[1])
                if n >= self._next_id:
                    self._next_id = n + 1
            except (IndexError, ValueError):
                pass

        # Restore seed meta policy from the generation-0 agent
        seed_entries = [e for e in self.archive if e.agent.generation == 0]
        if seed_entries:
            self._seed_meta_policy = deepcopy(seed_entries[0].agent.meta_policy)

        # Continue appending to the same DB run
        self._run_id = snapshot.get("run_id")

    def _deserialize_entry(self, data: dict[str, Any]) -> ArchiveEntry:
        agent_data = data["agent"]
        ev_data = data["evaluation"]
        tp = agent_data["task_policy"]
        mp = agent_data["meta_policy"]
        return ArchiveEntry(
            agent=HyperAgent(
                agent_id=agent_data["agent_id"],
                parent_id=agent_data.get("parent_id"),
                generation=agent_data["generation"],
                task_policy=TaskPolicy(
                    weights=tp["weights"],
                    threshold=tp["threshold"],
                    review_style=tp["review_style"],
                ),
                meta_policy=MetaPolicy(
                    focus_metric=mp["focus_metric"],
                    weight_step=mp["weight_step"],
                    threshold_step=mp["threshold_step"],
                    exploration_scale=mp["exploration_scale"],
                    memory=mp.get("memory", []),
                ),
                lineage_notes=agent_data.get("lineage_notes", []),
            ),
            evaluation=Evaluation(
                fitness=ev_data["fitness"],
                train_accuracy=ev_data["train_accuracy"],
                test_accuracy=ev_data["test_accuracy"],
                false_positive_count=ev_data["false_positive_count"],
                false_negative_count=ev_data["false_negative_count"],
                false_positive_feature_avgs=ev_data["false_positive_feature_avgs"],
                false_negative_feature_avgs=ev_data["false_negative_feature_avgs"],
                summary=ev_data["summary"],
            ),
            created_iteration=data["created_iteration"],
        )

    @property
    def best_entry(self) -> ArchiveEntry:
        return max(
            self.archive,
            key=lambda entry: (
                entry.evaluation.fitness,
                entry.evaluation.test_accuracy,
                entry.created_iteration,
            ),
        )

    def set_account_repos(self, repos: list[dict]) -> None:
        """Replace the extra dataset from accounts and recalculate averages.

        The first 80 % of repos go to train; the remaining 20 % to test.
        Call reset() afterwards to re-initialise the evolutionary loop with
        the updated dataset sizes.
        """
        n_train = max(0, int(len(repos) * 0.8))
        self._extra_train_repos = repos[:n_train]
        self._extra_test_repos = repos[n_train:]
        self._recalculate_averages()

    def _get_train_repos(self) -> list[dict]:
        return TRAIN_REPOS + self._extra_train_repos

    def _get_test_repos(self) -> list[dict]:
        return TEST_REPOS + self._extra_test_repos

    def _recalculate_averages(self) -> None:
        all_train = self._get_train_repos()
        self._train_positive_avgs = average_feature_map(
            [r for r in all_train if r["label"] == 1]
        )
        self._train_negative_avgs = average_feature_map(
            [r for r in all_train if r["label"] == 0]
        )

    def review_repository(self, repo_url: str, repo_data: dict[str, Any]) -> dict[str, Any]:
        if self._llm_service is None:
            raise RuntimeError("OpenAI integration is not configured.")
        return self._llm_service.review_repository(repo_url, repo_data)

    def _build_initial_agent(self) -> HyperAgent:
        return HyperAgent(
            agent_id=self._new_agent_id(),
            parent_id=None,
            generation=0,
            task_policy=TaskPolicy(
                weights={
                    "maintainability": 0.90,
                    "security": 0.85,
                    "test_coverage": 0.88,
                    "documentation": 0.72,
                    "simplicity": 0.78,
                },
                threshold=3.05,
                review_style="balanced",
            ),
            meta_policy=MetaPolicy(
                focus_metric="security",
                weight_step=0.12,
                threshold_step=0.07,
                exploration_scale=0.18,
                memory=[
                    "Initial reviewer: watch for repos with good docs but poor security or no tests."
                ],
            ),
            lineage_notes=[
                "Seed agent with simple weighted scoring and no domain-specific special casing."
            ],
        )

    def _new_agent_id(self) -> str:
        agent_id = f"agent-{self._next_id:03d}"
        self._next_id += 1
        return agent_id

    def _select_parent(self) -> ArchiveEntry:
        # no_archive: greedy hill-climbing — always mutate from the single best.
        # Removes the stepping-stones mechanism to isolate its contribution.
        if self._mode == "no_archive":
            return self.best_entry

        weights = []
        best_fitness = self.best_entry.evaluation.fitness
        for entry in self.archive:
            exploitation = 0.25 + entry.evaluation.fitness
            exploration = 1.0 + entry.agent.meta_policy.exploration_scale
            novelty = 1.0 + min(entry.agent.generation, 8) * 0.03
            if best_fitness - entry.evaluation.fitness > 0.15:
                novelty += 0.08
            weights.append(exploitation * exploration * novelty)
        return self._rng.choices(self.archive, weights=weights, k=1)[0]

    def _mutate(self, parent: ArchiveEntry) -> HyperAgent:
        self._last_mutation_was_llm = False
        if not self._freeze_meta:
            llm_child = self._llm_mutation(parent)
            if llm_child is not None:
                self._last_mutation_was_llm = True
                return llm_child

        child_task = deepcopy(parent.agent.task_policy)
        # Baseline mode: always use seed meta policy so the improver never improves.
        child_meta = deepcopy(self._seed_meta_policy if self._freeze_meta else parent.agent.meta_policy)
        fp_count = parent.evaluation.false_positive_count
        fn_count = parent.evaluation.false_negative_count
        fp_avgs = parent.evaluation.false_positive_feature_avgs
        fn_avgs = parent.evaluation.false_negative_feature_avgs

        if fp_count == 0 and fn_count == 0:
            pressure_by_feature = {feature: 0.0 for feature in FEATURES}
            focus_metric = parent.agent.meta_policy.focus_metric
        else:
            pressure_by_feature: dict[str, float] = {}
            for feature in FEATURES:
                pressure = 0.0
                pressure += max(0.0, self._train_positive_avgs[feature] - fp_avgs[feature])
                pressure += max(0.0, fn_avgs[feature] - self._train_negative_avgs[feature]) * 0.7
                pressure_by_feature[feature] = round(pressure, 4)
            focus_metric = max(pressure_by_feature, key=pressure_by_feature.get)

        child_meta.focus_metric = focus_metric

        for index, feature in enumerate(FEATURES):
            base_step = child_meta.weight_step
            pressure = pressure_by_feature[feature]
            directional_adjustment = pressure * base_step
            noise = self._signed_noise(parent.agent.agent_id, feature, index)
            stochastic_adjustment = noise * child_meta.exploration_scale * 0.05
            if feature == focus_metric:
                directional_adjustment += base_step * 0.04
            child_task.weights[feature] = round(
                clamp(
                    child_task.weights[feature] + directional_adjustment + stochastic_adjustment,
                    0.25,
                    1.8,
                ),
                3,
            )

        if fp_count > fn_count:
            child_task.threshold = round(
                clamp(child_task.threshold + child_meta.threshold_step, 2.4, 4.2),
                3,
            )
            child_task.review_style = "strict"
        elif fn_count > fp_count:
            child_task.threshold = round(
                clamp(child_task.threshold - child_meta.threshold_step, 2.4, 4.2),
                3,
            )
            child_task.review_style = "lenient"
        else:
            child_task.review_style = "balanced"

        # Only update meta-policy parameters in hyperagent mode.
        # In baseline mode child_meta is already a frozen clone of the seed.
        if not self._freeze_meta:
            if pressure_by_feature[focus_metric] < 0.08:
                child_meta.weight_step = round(clamp(child_meta.weight_step + 0.015, 0.04, 0.22), 3)
                child_meta.exploration_scale = round(
                    clamp(child_meta.exploration_scale + 0.03, 0.05, 0.45),
                    3,
                )
            else:
                child_meta.weight_step = round(clamp(child_meta.weight_step - 0.005, 0.04, 0.22), 3)

            if fp_count != fn_count:
                child_meta.threshold_step = round(
                    clamp(child_meta.threshold_step + 0.005, 0.03, 0.14),
                    3,
                )
            else:
                child_meta.threshold_step = round(
                    clamp(child_meta.threshold_step - 0.005, 0.03, 0.14),
                    3,
                )

        note = self._build_memory_note(parent, focus_metric)
        child_meta.memory = (child_meta.memory + [note])[-4:]
        lineage_notes = (parent.agent.lineage_notes + [note])[-6:]

        return HyperAgent(
            agent_id=self._new_agent_id(),
            parent_id=parent.agent.agent_id,
            generation=parent.agent.generation + 1,
            task_policy=child_task,
            meta_policy=child_meta,
            lineage_notes=lineage_notes,
        )

    def _llm_mutation(self, parent: ArchiveEntry) -> HyperAgent | None:
        if self._llm_service is None or not self._llm_service.is_enabled:
            return None

        proposal = self._llm_service.propose_mutation(parent)
        if not proposal:
            return None

        task_policy = proposal.get("task_policy", {})
        meta_policy = proposal.get("meta_policy", {})
        raw_weights = task_policy.get("weights", {})

        weights = {}
        for feature in FEATURES:
            weights[feature] = round(
                clamp(float(raw_weights.get(feature, parent.agent.task_policy.weights[feature])), 0.25, 1.8),
                3,
            )

        next_task = TaskPolicy(
            weights=weights,
            threshold=round(
                clamp(float(task_policy.get("threshold", parent.agent.task_policy.threshold)), 2.4, 4.2),
                3,
            ),
            review_style=task_policy.get("review_style", parent.agent.task_policy.review_style)
            if task_policy.get("review_style") in {"balanced", "strict", "lenient"}
            else parent.agent.task_policy.review_style,
        )

        next_meta = MetaPolicy(
            focus_metric=meta_policy.get("focus_metric", parent.agent.meta_policy.focus_metric)
            if meta_policy.get("focus_metric") in FEATURES
            else parent.agent.meta_policy.focus_metric,
            weight_step=round(
                clamp(float(meta_policy.get("weight_step", parent.agent.meta_policy.weight_step)), 0.04, 0.22),
                3,
            ),
            threshold_step=round(
                clamp(float(meta_policy.get("threshold_step", parent.agent.meta_policy.threshold_step)), 0.03, 0.14),
                3,
            ),
            exploration_scale=round(
                clamp(
                    float(meta_policy.get("exploration_scale", parent.agent.meta_policy.exploration_scale)),
                    0.05,
                    0.45,
                ),
                3,
            ),
            memory=(parent.agent.meta_policy.memory + [proposal.get("memory_note", "LLM mutation executed.")])[-4:],
        )

        lineage_notes = (parent.agent.lineage_notes + [proposal.get("rationale", "LLM-guided mutation.")])[-6:]

        return HyperAgent(
            agent_id=self._new_agent_id(),
            parent_id=parent.agent.agent_id,
            generation=parent.agent.generation + 1,
            task_policy=next_task,
            meta_policy=next_meta,
            lineage_notes=lineage_notes,
        )

    def _post_evaluation_meta_adjustment(self, child: HyperAgent, delta: float) -> None:
        if self._freeze_meta:
            return
        if delta > 0:
            child.meta_policy.exploration_scale = round(
                clamp(child.meta_policy.exploration_scale - 0.02, 0.05, 0.45),
                3,
            )
            child.meta_policy.memory = (
                child.meta_policy.memory + ["Positive update. Tighten exploration and consolidate gains."]
            )[-4:]
        else:
            child.meta_policy.exploration_scale = round(
                clamp(child.meta_policy.exploration_scale + 0.05, 0.05, 0.45),
                3,
            )
            child.meta_policy.memory = (
                child.meta_policy.memory + ["Stagnation detected. Increase exploration on the next mutation."]
            )[-4:]

    def _evaluate_agent(self, agent: HyperAgent) -> Evaluation:
        train_accuracy, false_positives, false_negatives = self._evaluate_dataset(agent, self._get_train_repos())
        test_accuracy, _, _ = self._evaluate_dataset(agent, self._get_test_repos())
        summary = self._build_evaluation_summary(false_positives, false_negatives)
        return Evaluation(
            fitness=round(train_accuracy, 3),
            train_accuracy=round(train_accuracy, 3),
            test_accuracy=round(test_accuracy, 3),
            false_positive_count=len(false_positives),
            false_negative_count=len(false_negatives),
            false_positive_feature_avgs=average_feature_map(false_positives),
            false_negative_feature_avgs=average_feature_map(false_negatives),
            summary=summary,
        )

    def _evaluate_dataset(
        self,
        agent: HyperAgent,
        dataset: list[dict[str, Any]],
    ) -> tuple[float, list[dict[str, Any]], list[dict[str, Any]]]:
        correct = 0
        false_positives: list[dict[str, Any]] = []
        false_negatives: list[dict[str, Any]] = []
        for paper in dataset:
            predicted = self._predict(agent, paper)
            if predicted == paper["label"]:
                correct += 1
            elif predicted == 1:
                false_positives.append(paper)
            else:
                false_negatives.append(paper)
        return correct / len(dataset), false_positives, false_negatives

    def _predict(self, agent: HyperAgent, repo: dict[str, Any]) -> int:
        score = 0.0
        for feature, weight in agent.task_policy.weights.items():
            score += repo[feature] * weight

        if repo["security"] < 0.35:
            score -= 0.15
        if repo["test_coverage"] < 0.30:
            score -= 0.08
        if repo["maintainability"] > 0.78 and repo["security"] > 0.78:
            score += 0.08

        threshold = agent.task_policy.threshold + STYLE_THRESHOLD_OFFSET[agent.task_policy.review_style]
        return 1 if score >= threshold else 0

    def _build_evaluation_summary(
        self,
        false_positives: list[dict[str, Any]],
        false_negatives: list[dict[str, Any]],
    ) -> str:
        if not false_positives and not false_negatives:
            return "Perfect train accuracy. Current lineage is stable."

        parts: list[str] = []
        if false_positives:
            fp_avgs = average_feature_map(false_positives)
            weakest = min(fp_avgs, key=fp_avgs.get)
            parts.append(f"{len(false_positives)} false positives, usually weak on {weakest}")
        if false_negatives:
            fn_avgs = average_feature_map(false_negatives)
            strongest = max(fn_avgs, key=fn_avgs.get)
            parts.append(f"{len(false_negatives)} false negatives, often strong on {strongest}")
        return ". ".join(parts) + "."

    def _build_memory_note(self, parent: ArchiveEntry, focus_metric: str) -> str:
        fp_count = parent.evaluation.false_positive_count
        fn_count = parent.evaluation.false_negative_count
        if fp_count > fn_count:
            return f"Raise bar on {focus_metric}; weak repos are slipping through as merge-ready."
        if fn_count > fp_count:
            return f"Recover missed healthy repos by rewarding {focus_metric} more explicitly."
        return f"Balance review policy and keep probing {focus_metric}."

    def _signed_noise(self, agent_id: str, feature: str, index: int) -> float:
        seed = f"{agent_id}:{feature}:{index}:{self.iterations_completed}"
        rng = random.Random(seed)
        return (rng.random() * 2.0) - 1.0

    def _record_progress(self, current_entry: ArchiveEntry) -> None:
        best = self.best_entry
        mutation_source = (
            "seed" if self.iterations_completed == 0
            else ("llm" if self._last_mutation_was_llm else "heuristic")
        )
        self.progress.append(
            {
                "iteration": self.iterations_completed,
                # Best-so-far (monotonically non-decreasing)
                "best_fitness": best.evaluation.fitness,
                "best_test_accuracy": best.evaluation.test_accuracy,
                # Per-iteration child scores (shows raw improvement signal)
                "child_train_accuracy": current_entry.evaluation.train_accuracy,
                "child_test_accuracy": current_entry.evaluation.test_accuracy,
                "archive_size": len(self.archive),
                # Meta-policy state at this iteration (shows whether the improver is itself improving)
                "meta_focus_metric": current_entry.agent.meta_policy.focus_metric,
                "meta_weight_step": current_entry.agent.meta_policy.weight_step,
                "meta_threshold_step": current_entry.agent.meta_policy.threshold_step,
                "meta_exploration_scale": current_entry.agent.meta_policy.exploration_scale,
                "mutation_source": mutation_source,
            }
        )

    def _provider_snapshot(self) -> dict[str, Any]:
        if self._llm_service is None:
            return {
                "mode": "heuristic",
                "configured": False,
                "has_api_key": False,
                "client_ready": False,
                "model": "",
                "reason": "OpenAI integration is not configured.",
                "last_error": "",
            }
        return self._llm_service.metadata()

    def _serialize_entry(self, entry: ArchiveEntry) -> dict[str, Any]:
        payload = asdict(entry)
        payload["evaluation"]["summary"] = entry.evaluation.summary
        return payload
