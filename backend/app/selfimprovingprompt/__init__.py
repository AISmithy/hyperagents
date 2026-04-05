"""selfimprovingprompt
====================
Self-improving agent prompt engine.

Evolves any agent defined as a text prompt (.md file) based on human
feedback ratings after each real usage cycle.

Public API
----------
    from app.selfimprovingprompt import PromptEngine

    engine = PromptEngine(llm_service=..., write_back_path="my-agent.md")
    engine.reset(seed_prompt="You are a ...")

    engine.submit_review(
        review_text="...",
        rating=4,
        strengths=["caught XSS"],
        gaps=["missed auth tests"],
        codebase_ref="my-repo @ main",
    )
"""
from .engine import PromptEngine, PromptAgent, PromptEvaluation, PromptArchiveEntry

__all__ = ["PromptEngine", "PromptAgent", "PromptEvaluation", "PromptArchiveEntry"]
