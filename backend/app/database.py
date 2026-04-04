"""SQLite persistence layer using SQLModel.

Each call to engine.reset() creates a new Run row. Every agent variant,
progress snapshot, and mutation event is saved immediately so runs survive
restarts and can be loaded back into the engine for inspection or continuation.
"""
from __future__ import annotations

import json
import secrets
from datetime import datetime, timezone
from typing import Any, Optional

from sqlmodel import Field, Session, SQLModel, create_engine, select


# ── Table models ──────────────────────────────────────────────────────────────

class Run(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    run_uuid: str = Field(index=True)
    mode: str                        # "hyperagent" | "baseline" | "no_archive"
    seed: int
    created_at: str                  # ISO-8601 UTC
    iterations_completed: int = 0
    best_fitness: float = 0.0
    best_test_accuracy: float = 0.0


class AgentRecord(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    run_id: int = Field(foreign_key="run.id", index=True)
    agent_id: str
    parent_id: Optional[str] = None
    generation: int
    created_iteration: int
    task_policy_json: str
    meta_policy_json: str
    lineage_notes_json: str
    fitness: float
    train_accuracy: float
    test_accuracy: float
    false_positive_count: int
    false_negative_count: int
    false_positive_feature_avgs_json: str
    false_negative_feature_avgs_json: str
    evaluation_summary: str


class ProgressRecord(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    run_id: int = Field(foreign_key="run.id", index=True)
    iteration: int
    best_fitness: float
    best_test_accuracy: float
    child_train_accuracy: float
    child_test_accuracy: float
    archive_size: int
    meta_focus_metric: str
    meta_weight_step: float
    meta_threshold_step: float
    meta_exploration_scale: float
    mutation_source: str


class EventRecord(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    run_id: int = Field(foreign_key="run.id", index=True)
    iteration: int
    parent_agent_id: str
    child_agent_id: str
    fitness_delta: float
    summary: str


class Account(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    platform: str        # "synthetic" | "github"
    profile: str         # one of account_service.VALID_PROFILES, or "inferred" for github
    created_at: str      # ISO-8601 UTC


class AccountRepo(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    account_id: int = Field(foreign_key="account.id", index=True)
    repo_ref: str        # original id from generator (e.g. "syn-acme-01")
    name: str
    maintainability: float
    security: float
    test_coverage: float
    documentation: float
    simplicity: float
    label: int           # 0 or 1


# ── Database class ────────────────────────────────────────────────────────────

class Database:
    def __init__(self, db_path: str) -> None:
        self._engine = create_engine(f"sqlite:///{db_path}", echo=False)
        SQLModel.metadata.create_all(self._engine)

    # ── write ─────────────────────────────────────────────────────────────────

    def create_run(self, mode: str, seed: int) -> int:
        run = Run(
            run_uuid=secrets.token_hex(4),
            mode=mode,
            seed=seed,
            created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )
        with Session(self._engine) as session:
            session.add(run)
            session.commit()
            session.refresh(run)
            return run.id  # type: ignore[return-value]

    def update_run(
        self,
        run_id: int,
        iterations_completed: int,
        best_fitness: float,
        best_test_accuracy: float,
    ) -> None:
        with Session(self._engine) as session:
            run = session.get(Run, run_id)
            if run:
                run.iterations_completed = iterations_completed
                run.best_fitness = best_fitness
                run.best_test_accuracy = best_test_accuracy
                session.add(run)
                session.commit()

    def save_archive_entry(self, run_id: int, entry: dict[str, Any]) -> None:
        agent = entry["agent"]
        ev = entry["evaluation"]
        record = AgentRecord(
            run_id=run_id,
            agent_id=agent["agent_id"],
            parent_id=agent.get("parent_id"),
            generation=agent["generation"],
            created_iteration=entry["created_iteration"],
            task_policy_json=json.dumps(agent["task_policy"]),
            meta_policy_json=json.dumps(agent["meta_policy"]),
            lineage_notes_json=json.dumps(agent.get("lineage_notes", [])),
            fitness=ev["fitness"],
            train_accuracy=ev["train_accuracy"],
            test_accuracy=ev["test_accuracy"],
            false_positive_count=ev["false_positive_count"],
            false_negative_count=ev["false_negative_count"],
            false_positive_feature_avgs_json=json.dumps(ev["false_positive_feature_avgs"]),
            false_negative_feature_avgs_json=json.dumps(ev["false_negative_feature_avgs"]),
            evaluation_summary=ev["summary"],
        )
        with Session(self._engine) as session:
            session.add(record)
            session.commit()

    def save_progress(self, run_id: int, record: dict[str, Any]) -> None:
        with Session(self._engine) as session:
            session.add(ProgressRecord(
                run_id=run_id,
                iteration=record["iteration"],
                best_fitness=record["best_fitness"],
                best_test_accuracy=record["best_test_accuracy"],
                child_train_accuracy=record["child_train_accuracy"],
                child_test_accuracy=record["child_test_accuracy"],
                archive_size=record["archive_size"],
                meta_focus_metric=record["meta_focus_metric"],
                meta_weight_step=record["meta_weight_step"],
                meta_threshold_step=record["meta_threshold_step"],
                meta_exploration_scale=record["meta_exploration_scale"],
                mutation_source=record["mutation_source"],
            ))
            session.commit()

    def save_event(self, run_id: int, event: dict[str, Any]) -> None:
        with Session(self._engine) as session:
            session.add(EventRecord(
                run_id=run_id,
                iteration=event["iteration"],
                parent_agent_id=event["parent_id"],
                child_agent_id=event["child_id"],
                fitness_delta=event["fitness_delta"],
                summary=event["summary"],
            ))
            session.commit()

    def delete_run(self, run_id: int) -> bool:
        with Session(self._engine) as session:
            run = session.get(Run, run_id)
            if not run:
                return False
            for model in (AgentRecord, ProgressRecord, EventRecord):
                for rec in session.exec(select(model).where(model.run_id == run_id)).all():  # type: ignore[arg-type]
                    session.delete(rec)
            session.delete(run)
            session.commit()
            return True

    # ── read ──────────────────────────────────────────────────────────────────

    def list_runs(self) -> list[dict[str, Any]]:
        with Session(self._engine) as session:
            runs = session.exec(select(Run).order_by(Run.id.desc())).all()
            return [
                {
                    "run_id": r.id,
                    "run_uuid": r.run_uuid,
                    "mode": r.mode,
                    "created_at": r.created_at,
                    "iterations_completed": r.iterations_completed,
                    "best_fitness": r.best_fitness,
                    "best_test_accuracy": r.best_test_accuracy,
                }
                for r in runs
            ]

    # ── account management ────────────────────────────────────────────────────

    def create_account(self, name: str, platform: str, profile: str) -> int:
        account = Account(
            name=name,
            platform=platform,
            profile=profile,
            created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )
        with Session(self._engine) as session:
            session.add(account)
            session.commit()
            session.refresh(account)
            return account.id  # type: ignore[return-value]

    def save_account_repo(self, account_id: int, repo: dict[str, Any]) -> int:
        record = AccountRepo(
            account_id=account_id,
            repo_ref=repo.get("id", ""),
            name=repo["name"],
            maintainability=repo["maintainability"],
            security=repo["security"],
            test_coverage=repo["test_coverage"],
            documentation=repo["documentation"],
            simplicity=repo["simplicity"],
            label=repo["label"],
        )
        with Session(self._engine) as session:
            session.add(record)
            session.commit()
            session.refresh(record)
            return record.id  # type: ignore[return-value]

    def list_accounts(self) -> list[dict[str, Any]]:
        with Session(self._engine) as session:
            accounts = session.exec(select(Account).order_by(Account.id.desc())).all()
            result = []
            for a in accounts:
                repo_count = len(session.exec(
                    select(AccountRepo).where(AccountRepo.account_id == a.id)
                ).all())
                result.append({
                    "id": a.id,
                    "name": a.name,
                    "platform": a.platform,
                    "profile": a.profile,
                    "created_at": a.created_at,
                    "repo_count": repo_count,
                })
            return result

    def get_account_repos(self, account_id: int) -> list[dict[str, Any]]:
        with Session(self._engine) as session:
            rows = session.exec(
                select(AccountRepo).where(AccountRepo.account_id == account_id)
            ).all()
            return [
                {
                    "id": r.id,
                    "account_id": r.account_id,
                    "repo_ref": r.repo_ref,
                    "name": r.name,
                    "maintainability": r.maintainability,
                    "security": r.security,
                    "test_coverage": r.test_coverage,
                    "documentation": r.documentation,
                    "simplicity": r.simplicity,
                    "label": r.label,
                }
                for r in rows
            ]

    def list_all_account_repos(self) -> list[dict[str, Any]]:
        """Return all repos across all accounts (for bulk dataset apply)."""
        with Session(self._engine) as session:
            rows = session.exec(select(AccountRepo)).all()
            return [
                {
                    "id": r.repo_ref,
                    "name": r.name,
                    "maintainability": r.maintainability,
                    "security": r.security,
                    "test_coverage": r.test_coverage,
                    "documentation": r.documentation,
                    "simplicity": r.simplicity,
                    "label": r.label,
                }
                for r in rows
            ]

    def get_all_progress(self) -> list[dict[str, Any]]:
        """Return every progress row joined with its run's condition (mode).

        The ``condition`` column uses the internal mode name
        ("hyperagent" | "baseline" | "no_archive").  Callers that need the
        paper-facing label ("full" | "frozen_meta" | "no_archive") can map
        via ``engine.CONDITION_LABELS``.  Suitable for direct DataFrame
        construction for analysis and plotting.
        """
        from app.engine import CONDITION_LABELS  # local import avoids circular dep

        with Session(self._engine) as session:
            runs = {r.id: r for r in session.exec(select(Run)).all()}
            progress_rows = session.exec(
                select(ProgressRecord).order_by(ProgressRecord.run_id, ProgressRecord.iteration)
            ).all()
            return [
                {
                    "run_id": p.run_id,
                    "run_uuid": runs[p.run_id].run_uuid if p.run_id in runs else None,
                    "condition": runs[p.run_id].mode if p.run_id in runs else None,
                    "condition_label": CONDITION_LABELS.get(
                        runs[p.run_id].mode if p.run_id in runs else "", ""
                    ),
                    "seed": runs[p.run_id].seed if p.run_id in runs else None,
                    "iteration": p.iteration,
                    "best_fitness": p.best_fitness,
                    "best_test_accuracy": p.best_test_accuracy,
                    "child_train_accuracy": p.child_train_accuracy,
                    "child_test_accuracy": p.child_test_accuracy,
                    "archive_size": p.archive_size,
                    "meta_focus_metric": p.meta_focus_metric,
                    "meta_weight_step": p.meta_weight_step,
                    "meta_threshold_step": p.meta_threshold_step,
                    "meta_exploration_scale": p.meta_exploration_scale,
                    "mutation_source": p.mutation_source,
                }
                for p in progress_rows
            ]

    def delete_account(self, account_id: int) -> bool:
        with Session(self._engine) as session:
            account = session.get(Account, account_id)
            if not account:
                return False
            for repo in session.exec(
                select(AccountRepo).where(AccountRepo.account_id == account_id)
            ).all():
                session.delete(repo)
            session.delete(account)
            session.commit()
            return True

    def load_run(self, run_id: int) -> dict[str, Any] | None:
        with Session(self._engine) as session:
            run = session.get(Run, run_id)
            if not run:
                return None

            agent_rows = session.exec(
                select(AgentRecord)
                .where(AgentRecord.run_id == run_id)
                .order_by(AgentRecord.created_iteration)
            ).all()

            archive = [
                {
                    "agent": {
                        "agent_id": r.agent_id,
                        "parent_id": r.parent_id,
                        "generation": r.generation,
                        "task_policy": json.loads(r.task_policy_json),
                        "meta_policy": json.loads(r.meta_policy_json),
                        "lineage_notes": json.loads(r.lineage_notes_json),
                    },
                    "evaluation": {
                        "fitness": r.fitness,
                        "train_accuracy": r.train_accuracy,
                        "test_accuracy": r.test_accuracy,
                        "false_positive_count": r.false_positive_count,
                        "false_negative_count": r.false_negative_count,
                        "false_positive_feature_avgs": json.loads(r.false_positive_feature_avgs_json),
                        "false_negative_feature_avgs": json.loads(r.false_negative_feature_avgs_json),
                        "summary": r.evaluation_summary,
                    },
                    "created_iteration": r.created_iteration,
                }
                for r in agent_rows
            ]

            progress_rows = session.exec(
                select(ProgressRecord)
                .where(ProgressRecord.run_id == run_id)
                .order_by(ProgressRecord.iteration)
            ).all()

            progress = [
                {
                    "iteration": p.iteration,
                    "best_fitness": p.best_fitness,
                    "best_test_accuracy": p.best_test_accuracy,
                    "child_train_accuracy": p.child_train_accuracy,
                    "child_test_accuracy": p.child_test_accuracy,
                    "archive_size": p.archive_size,
                    "meta_focus_metric": p.meta_focus_metric,
                    "meta_weight_step": p.meta_weight_step,
                    "meta_threshold_step": p.meta_threshold_step,
                    "meta_exploration_scale": p.meta_exploration_scale,
                    "mutation_source": p.mutation_source,
                    "mode": run.mode,
                }
                for p in progress_rows
            ]

            event_rows = session.exec(
                select(EventRecord)
                .where(EventRecord.run_id == run_id)
                .order_by(EventRecord.iteration.desc())
                .limit(12)
            ).all()

            recent_events = list(reversed([
                {
                    "iteration": e.iteration,
                    "parent_id": e.parent_agent_id,
                    "child_id": e.child_agent_id,
                    "fitness_delta": e.fitness_delta,
                    "summary": e.summary,
                }
                for e in event_rows
            ]))

            best = (
                max(archive, key=lambda e: (e["evaluation"]["fitness"], e["evaluation"]["test_accuracy"]))
                if archive else None
            )

            return {
                "run_id": run.id,
                "run_uuid": run.run_uuid,
                "mode": run.mode,
                "created_at": run.created_at,
                "iterations_completed": run.iterations_completed,
                "archive": archive,
                "progress": progress,
                "recent_events": recent_events,
                "best_agent": best,
            }
