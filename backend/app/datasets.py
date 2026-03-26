# Synthetic code-repository quality dataset.
#
# Label = 1  →  repo is merge-ready / production-quality
# Label = 0  →  repo should be rejected
#
# The first 10 training examples are cleanly separated.
# Examples train-11 through train-18 are deliberately borderline so the initial
# seed agent (~72 % accuracy) has meaningful room to improve across iterations.
# This makes the ablation learning curves informative.

TRAIN_REPOS = [
    # ── Original 10: clearly separated, seed gets all correct ────────────────
    {
        "id": "train-01",
        "name": "well-maintained-api-service",
        "maintainability": 0.85,
        "security": 0.80,
        "test_coverage": 0.90,
        "documentation": 0.82,
        "simplicity": 0.75,
        "label": 1,
    },
    {
        "id": "train-02",
        "name": "spaghetti-code-no-tests",
        "maintainability": 0.30,
        "security": 0.45,
        "test_coverage": 0.15,
        "documentation": 0.25,
        "simplicity": 0.20,
        "label": 0,
    },
    {
        "id": "train-03",
        "name": "clean-api-with-ci-cd",
        "maintainability": 0.78,
        "security": 0.88,
        "test_coverage": 0.82,
        "documentation": 0.70,
        "simplicity": 0.72,
        "label": 1,
    },
    {
        "id": "train-04",
        "name": "hardcoded-secrets-no-docs",
        "maintainability": 0.55,
        "security": 0.18,
        "test_coverage": 0.40,
        "documentation": 0.22,
        "simplicity": 0.48,
        "label": 0,
    },
    {
        "id": "train-05",
        "name": "well-documented-library",
        "maintainability": 0.80,
        "security": 0.75,
        "test_coverage": 0.85,
        "documentation": 0.90,
        "simplicity": 0.70,
        "label": 1,
    },
    {
        "id": "train-06",
        "name": "giant-functions-no-tests",
        "maintainability": 0.28,
        "security": 0.55,
        "test_coverage": 0.10,
        "documentation": 0.35,
        "simplicity": 0.15,
        "label": 0,
    },
    {
        "id": "train-07",
        "name": "secure-auth-service",
        "maintainability": 0.72,
        "security": 0.92,
        "test_coverage": 0.80,
        "documentation": 0.68,
        "simplicity": 0.65,
        "label": 1,
    },
    {
        "id": "train-08",
        "name": "deprecated-deps-poor-structure",
        "maintainability": 0.35,
        "security": 0.40,
        "test_coverage": 0.55,
        "documentation": 0.60,
        "simplicity": 0.42,
        "label": 0,
    },
    {
        "id": "train-09",
        "name": "microservice-clean-patterns",
        "maintainability": 0.82,
        "security": 0.78,
        "test_coverage": 0.75,
        "documentation": 0.72,
        "simplicity": 0.80,
        "label": 1,
    },
    {
        "id": "train-10",
        "name": "large-monolith-tangled-deps",
        "maintainability": 0.38,
        "security": 0.62,
        "test_coverage": 0.28,
        "documentation": 0.45,
        "simplicity": 0.22,
        "label": 0,
    },
    # ── Borderline positives: good repos the seed agent MISSES (false negatives)
    # Score with seed weights < 3.05 despite label=1 ─────────────────────────
    {
        "id": "train-11",
        "name": "good-but-undertested",          # solid but test_coverage only 0.55
        "maintainability": 0.78,
        "security": 0.72,
        "test_coverage": 0.55,
        "documentation": 0.75,
        "simplicity": 0.70,
        "label": 1,                              # seed score ≈ 2.884 → missed
    },
    {
        "id": "train-12",
        "name": "legacy-but-stable",             # older codebase, low simplicity
        "maintainability": 0.65,
        "security": 0.80,
        "test_coverage": 0.70,
        "documentation": 0.55,
        "simplicity": 0.62,
        "label": 1,                              # seed score ≈ 2.761 → missed
    },
    {
        "id": "train-13",
        "name": "minimal-but-solid",             # lean repo, sparse docs
        "maintainability": 0.70,
        "security": 0.76,
        "test_coverage": 0.65,
        "documentation": 0.62,
        "simplicity": 0.80,
        "label": 1,                              # seed score ≈ 2.918 → missed
    },
    {
        "id": "train-14",
        "name": "senior-dev-light-docs",         # expert code, minimal documentation
        "maintainability": 0.75,
        "security": 0.82,
        "test_coverage": 0.72,
        "documentation": 0.48,
        "simplicity": 0.74,
        "label": 1,                              # seed score ≈ 2.928 → missed
    },
    # ── Borderline negatives: bad repos the seed FALSELY ACCEPTS (false positives)
    # Score with seed weights >= 3.05 despite label=0 ─────────────────────────
    {
        "id": "train-15",
        "name": "beautiful-but-insecure",        # glossy repo with hidden CVEs
        "maintainability": 0.85,
        "security": 0.38,
        "test_coverage": 0.82,
        "documentation": 0.90,
        "simplicity": 0.88,
        "label": 0,                              # seed score ≈ 3.144 → false accept
    },
    {
        "id": "train-16",
        "name": "polished-deprecated-stack",     # well-structured but unmaintained deps
        "maintainability": 0.90,
        "security": 0.45,
        "test_coverage": 0.85,
        "documentation": 0.88,
        "simplicity": 0.78,
        "label": 0,                              # seed score ≈ 3.183 → false accept
    },
    {
        "id": "train-17",
        "name": "high-complexity-risky-patterns",# looks clean, known bad patterns
        "maintainability": 0.88,
        "security": 0.72,
        "test_coverage": 0.78,
        "documentation": 0.85,
        "simplicity": 0.52,
        "label": 0,                              # seed score ≈ 3.108 → false accept
    },
    # ── Additional clearly-classified examples for balance ────────────────────
    {
        "id": "train-18",
        "name": "clean-typed-api-v2",
        "maintainability": 0.84,
        "security": 0.82,
        "test_coverage": 0.88,
        "documentation": 0.78,
        "simplicity": 0.76,
        "label": 1,                              # seed score ≈ 3.462 → correct
    },
    {
        "id": "train-19",
        "name": "quick-hack-no-tests",
        "maintainability": 0.35,
        "security": 0.50,
        "test_coverage": 0.12,
        "documentation": 0.30,
        "simplicity": 0.28,
        "label": 0,                              # seed score ≈ 1.200 → correct
    },
    {
        "id": "train-20",
        "name": "overengineered-no-docs",
        "maintainability": 0.42,
        "security": 0.60,
        "test_coverage": 0.48,
        "documentation": 0.18,
        "simplicity": 0.25,
        "label": 0,                              # seed score ≈ 1.635 → correct
    },
]

TEST_REPOS = [
    # ── Original 6 ────────────────────────────────────────────────────────────
    {
        "id": "test-01",
        "name": "well-structured-cli-tool",
        "maintainability": 0.76,
        "security": 0.82,
        "test_coverage": 0.78,
        "documentation": 0.74,
        "simplicity": 0.72,
        "label": 1,
    },
    {
        "id": "test-02",
        "name": "injection-vulnerabilities-no-tests",
        "maintainability": 0.48,
        "security": 0.20,
        "test_coverage": 0.25,
        "documentation": 0.38,
        "simplicity": 0.44,
        "label": 0,
    },
    {
        "id": "test-03",
        "name": "typed-library-95pct-coverage",
        "maintainability": 0.84,
        "security": 0.80,
        "test_coverage": 0.92,
        "documentation": 0.78,
        "simplicity": 0.76,
        "label": 1,
    },
    {
        "id": "test-04",
        "name": "cosmetic-commits-no-ci",
        "maintainability": 0.50,
        "security": 0.55,
        "test_coverage": 0.30,
        "documentation": 0.65,
        "simplicity": 0.58,
        "label": 0,
    },
    {
        "id": "test-05",
        "name": "insecure-defaults-poor-docs",
        "maintainability": 0.42,
        "security": 0.28,
        "test_coverage": 0.35,
        "documentation": 0.32,
        "simplicity": 0.45,
        "label": 0,
    },
    {
        "id": "test-06",
        "name": "production-grade-service",
        "maintainability": 0.88,
        "security": 0.85,
        "test_coverage": 0.80,
        "documentation": 0.82,
        "simplicity": 0.78,
        "label": 1,
    },
    # ── Borderline test examples ───────────────────────────────────────────────
    {
        "id": "test-07",
        "name": "borderline-positive-startup",  # good quality, sparse docs
        "maintainability": 0.72,
        "security": 0.75,
        "test_coverage": 0.68,
        "documentation": 0.65,
        "simplicity": 0.70,
        "label": 1,                             # seed score ≈ 2.898 → missed
    },
    {
        "id": "test-08",
        "name": "deceptive-codebase",           # polished surface, security holes
        "maintainability": 0.82,
        "security": 0.40,
        "test_coverage": 0.80,
        "documentation": 0.88,
        "simplicity": 0.84,
        "label": 0,                             # seed score ≈ 3.071 → false accept
    },
    {
        "id": "test-09",
        "name": "strong-open-source-project",
        "maintainability": 0.86,
        "security": 0.84,
        "test_coverage": 0.92,
        "documentation": 0.80,
        "simplicity": 0.82,
        "label": 1,                             # seed score → correct
    },
    {
        "id": "test-10",
        "name": "sql-injection-everywhere",
        "maintainability": 0.58,
        "security": 0.22,
        "test_coverage": 0.55,
        "documentation": 0.60,
        "simplicity": 0.62,
        "label": 0,                             # seed score → correct (security penalty)
    },
]
