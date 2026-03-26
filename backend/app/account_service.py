"""
account_service.py
==================
Generates synthetic or GitHub-backed repo feature vectors for accounts.

Two modes:
  synthetic  --  deterministic RNG from a named quality profile
  github     --  real GitHub API metadata mapped to 5 feature scores
"""
from __future__ import annotations

import random
from typing import Any

FEATURES = ("maintainability", "security", "test_coverage", "documentation", "simplicity")

# ── Quality profiles ───────────────────────────────────────────────────────────
# Each profile defines mean feature values (in FEATURES order) + std deviation.

PROFILES: dict[str, dict[str, Any]] = {
    "premium": {
        "means": (0.78, 0.82, 0.80, 0.75, 0.72),
        "std": 0.10,
        "description": "Well-run org with consistently high standards.",
    },
    "startup": {
        "means": (0.60, 0.52, 0.48, 0.55, 0.65),
        "std": 0.18,
        "description": "Moving fast; quality varies widely across repos.",
    },
    "legacy": {
        "means": (0.50, 0.42, 0.38, 0.52, 0.40),
        "std": 0.14,
        "description": "Older codebase — lower security and test coverage.",
    },
    "academic": {
        "means": (0.62, 0.58, 0.55, 0.82, 0.65),
        "std": 0.15,
        "description": "Research code: excellent docs, uneven security and tests.",
    },
    "security_focused": {
        "means": (0.70, 0.90, 0.72, 0.68, 0.64),
        "std": 0.10,
        "description": "Security-first: audit-grade security across all repos.",
    },
    "mixed": {
        "means": (0.60, 0.60, 0.60, 0.60, 0.60),
        "std": 0.22,
        "description": "Uniform distribution with high variance.",
    },
}

VALID_PROFILES = list(PROFILES.keys())
VALID_PLATFORMS = ("synthetic", "github")

_REPO_SUFFIXES = [
    "api", "service", "lib", "sdk", "cli", "core", "utils", "client",
    "server", "worker", "proxy", "gateway", "dashboard", "pipeline",
    "processor", "handler", "manager", "controller", "module", "plugin",
    "auth", "data", "config", "build", "deploy", "monitor", "cache",
    "parser", "formatter", "validator", "scheduler", "notifier", "router",
]


# ── Synthetic generation ───────────────────────────────────────────────────────

def generate_synthetic_repos(
    account_name: str,
    profile_name: str,
    n_repos: int,
) -> list[dict[str, Any]]:
    """Return n_repos synthetic repo dicts for account_name using profile_name.

    Deterministic: same account_name + profile_name always produces the same set.
    """
    profile = PROFILES.get(profile_name, PROFILES["mixed"])
    means: tuple[float, ...] = profile["means"]
    std: float = profile["std"]
    rng = random.Random(f"{account_name}:{profile_name}")

    repos: list[dict[str, Any]] = []
    for i in range(n_repos):
        suffix = _REPO_SUFFIXES[i % len(_REPO_SUFFIXES)]
        name = f"{account_name}-{suffix}" if i < len(_REPO_SUFFIXES) else f"{account_name}-{suffix}-{i - len(_REPO_SUFFIXES) + 2}"

        features: dict[str, float] = {}
        for j, feature in enumerate(FEATURES):
            raw = rng.gauss(means[j], std)
            features[feature] = round(max(0.02, min(0.98, raw)), 3)

        repos.append({
            "id": f"syn-{account_name}-{i + 1:02d}",
            "name": name,
            **features,
            "label": oracle_label(features),
        })

    return repos


# ── GitHub feature inference ───────────────────────────────────────────────────

def infer_features_from_github(repo_meta: dict[str, Any]) -> dict[str, float]:
    """Map GitHub API repo metadata to 5 feature scores in [0, 1].

    Uses lightweight heuristics that don't require per-file content fetching.
    """
    import math

    stars: int = repo_meta.get("stargazers_count", 0)
    open_issues: int = repo_meta.get("open_issues_count", 0)
    archived: bool = repo_meta.get("archived", False)
    has_wiki: bool = repo_meta.get("has_wiki", False)
    has_pages: bool = repo_meta.get("has_pages", False)
    description: str = repo_meta.get("description") or ""
    topics: list[str] = [t.lower() for t in (repo_meta.get("topics") or [])]
    topic_set = set(topics)

    star_score = min(1.0, math.log1p(stars) / math.log1p(1000))
    issue_penalty = min(0.25, open_issues / max(stars + 1, 1) * 0.1)

    ci_kw   = {"ci", "cd", "devops", "github-actions", "automation", "continuous-integration"}
    sec_kw  = {"security", "vulnerability", "cve", "pentest", "crypto", "authentication",
               "authorization", "owasp", "audit", "hardening"}
    test_kw = {"testing", "tests", "tdd", "bdd", "coverage", "pytest", "jest", "mocha",
               "unittest", "integration-testing", "e2e"}
    doc_kw  = {"documentation", "docs", "api-documentation", "sdk", "library", "reference",
               "guide", "tutorial"}

    maintainability = (
        0.35 * star_score
        + 0.30 * (0.0 if archived else 1.0)
        + 0.20 * bool(ci_kw & topic_set)
        + 0.15
    )
    security = (
        0.45
        + 0.30 * bool(sec_kw & topic_set)
        + 0.15 * star_score
        - issue_penalty
    )
    test_coverage = (
        0.40
        + 0.35 * bool(test_kw & topic_set)
        + 0.25 * star_score
    )
    documentation = (
        0.10 * (len(description) > 30)
        + 0.25 * has_wiki
        + 0.20 * has_pages
        + 0.25 * bool(doc_kw & topic_set)
        + 0.20 * star_score
    )
    simplicity = max(0.25, 0.80 - len(topics) * 0.03)

    def clamp(v: float) -> float:
        return round(max(0.02, min(0.98, v)), 3)

    return {
        "maintainability": clamp(maintainability),
        "security":        clamp(security),
        "test_coverage":   clamp(test_coverage),
        "documentation":   clamp(documentation),
        "simplicity":      clamp(simplicity),
    }


# ── Ground-truth label ────────────────────────────────────────────────────────

def oracle_label(features: dict[str, float]) -> int:
    """Assign a ground-truth quality label.

    Intentionally uses different thresholds from the agent's scoring function
    so the agent must genuinely learn the decision boundary.

    Rules (all must pass for label = 1):
      - security      >= 0.38  (hard security floor)
      - test_coverage >= 0.33  (minimum test presence)
      - mean(all)     >= 0.60  (overall quality threshold)
    """
    if features["security"] < 0.38:
        return 0
    if features["test_coverage"] < 0.33:
        return 0
    mean_score = sum(features[f] for f in FEATURES) / len(FEATURES)
    return 1 if mean_score >= 0.60 else 0
