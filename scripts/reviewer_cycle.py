"""reviewer_cycle.py
===================
CLI for the self-improving code-reviewer prompt loop.

Eliminates all manual steps: reads your review file, submits the rating,
and the backend writes the improved prompt back to your code-reviewer.md
automatically.

Commands
--------
    init   [--prompt-file PATH]          Load your agent file into the engine
    submit --review-file PATH            Submit a completed review for rating
    status                               Show current engine state
    best                                 Print the best prompt found so far

Quick start
-----------
    # 1. Point the backend at your agent file (in backend/.env.local):
    #    REVIEWER_PROMPT_PATH=/path/to/code-reviewer.md

    # 2. Load your current agent:
    python scripts/reviewer_cycle.py init --prompt-file code-reviewer.md

    # 3. Run your review, save the output to a file, then submit:
    python scripts/reviewer_cycle.py submit --review-file review_output.txt

    # The improved prompt is written back to code-reviewer.md automatically.
    # Repeat from step 3 after your next review cycle.
"""
from __future__ import annotations

import argparse
import json
import sys
import textwrap
from pathlib import Path

try:
    import urllib.request
    import urllib.error
except ImportError:
    pass  # always available in stdlib

API_BASE = "http://127.0.0.1:8000/api/promptagent"


# ── HTTP helpers ──────────────────────────────────────────────────────────────

def _request(method: str, path: str, body: dict | None = None) -> dict:
    url = f"{API_BASE}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = json.loads(exc.read()).get("detail", "")
        except Exception:
            pass
        print(f"Error {exc.code}: {detail or exc.reason}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as exc:
        print(f"Cannot reach backend at {url}\n{exc.reason}", file=sys.stderr)
        print("Is the backend running?  uvicorn app.main:app --host 0.0.0.0 --port 8000", file=sys.stderr)
        sys.exit(1)


def _get(path: str) -> dict:
    return _request("GET", path)


def _post(path: str, body: dict | None = None) -> dict:
    return _request("POST", path, body or {})


# ── Commands ──────────────────────────────────────────────────────────────────

def cmd_init(args: argparse.Namespace) -> None:
    """Load a prompt file into the engine and start a fresh run."""
    seed_prompt = ""
    if args.prompt_file:
        p = Path(args.prompt_file)
        if not p.exists():
            print(f"File not found: {p}", file=sys.stderr)
            sys.exit(1)
        seed_prompt = p.read_text(encoding="utf-8")
        print(f"Loaded prompt from {p} ({len(seed_prompt)} chars)")
    else:
        print("No --prompt-file given. Using built-in default prompt.")

    result = _post("/reset", {"seed_prompt": seed_prompt})
    write_back = result.get("write_back_path")

    print(f"\nEngine initialised.")
    print(f"  Active agent : {result['active_agent_id']}")
    if write_back:
        print(f"  Auto write-back configured → {write_back}")
    else:
        print("  Auto write-back: NOT configured")
        print("  Set REVIEWER_PROMPT_PATH in backend/.env.local to enable.")
    print(f"\nActive prompt preview:")
    print(textwrap.indent(result["active_prompt"][:300] + ("…" if len(result["active_prompt"]) > 300 else ""), "  "))


def cmd_submit(args: argparse.Namespace) -> None:
    """Submit a completed review for rating and trigger prompt evolution."""
    review_file = Path(args.review_file)
    if not review_file.exists():
        print(f"Review file not found: {review_file}", file=sys.stderr)
        sys.exit(1)

    review_text = review_file.read_text(encoding="utf-8")
    print(f"Review file: {review_file} ({len(review_text)} chars)")

    # Rating
    rating = args.rating
    if rating is None:
        while True:
            try:
                rating = int(input("\nRate this review 1–5 (1=poor, 5=excellent): ").strip())
                if 1 <= rating <= 5:
                    break
                print("Please enter a number between 1 and 5.")
            except (ValueError, KeyboardInterrupt):
                print("\nAborted.", file=sys.stderr)
                sys.exit(0)

    # Strengths
    strengths = args.strengths or []
    if not strengths and not args.non_interactive:
        print("\nWhat did the review get RIGHT? (one per line, blank line to finish)")
        while True:
            line = input("  + ").strip()
            if not line:
                break
            strengths.append(line)

    # Gaps
    gaps = args.gaps or []
    if not gaps and not args.non_interactive:
        print("\nWhat did the review MISS or get wrong? (one per line, blank line to finish)")
        while True:
            line = input("  - ").strip()
            if not line:
                break
            gaps.append(line)

    codebase_ref = args.codebase_ref or ""

    print("\nSubmitting…")
    result = _post("/submit", {
        "review_text": review_text,
        "rating": rating,
        "strengths": strengths,
        "gaps": gaps,
        "codebase_ref": codebase_ref,
    })

    # Report
    print(f"\n  Iteration    : {result['iteration']}")
    print(f"  Rated agent  : {result['rated_agent_id']}")
    print(f"  Fitness      : {result['fitness']:.2f}  (rating {result['rating']}/5)")
    print(f"  New agent    : {result['new_agent_id']}")

    # Check if write-back happened
    state = _get("/state")
    write_back = state.get("write_back_path")
    if write_back:
        print(f"\n  Prompt written back → {write_back}")
    else:
        print("\n  Write-back not configured. To enable, set REVIEWER_PROMPT_PATH in backend/.env.local")
        print("  To manually export:")
        print("    python scripts/reviewer_cycle.py best > code-reviewer.md")

    print(f"\nNext prompt preview:")
    print(textwrap.indent(result["new_prompt"][:300] + ("…" if len(result["new_prompt"]) > 300 else ""), "  "))

    if result.get("meta_notes"):
        print(f"\nMeta notes:")
        for note in result["meta_notes"][-2:]:
            print(f"  • {note}")


def cmd_status(args: argparse.Namespace) -> None:
    """Show current engine state."""
    state = _get("/state")
    print(f"Iterations completed : {state['iterations_completed']}")
    print(f"Archive size         : {len(state['archive'])}")
    print(f"Active agent         : {state['active_agent_id']}")
    write_back = state.get("write_back_path")
    print(f"Write-back path      : {write_back or '(not configured)'}")

    if state["history"]:
        print(f"\nReview history:")
        print(f"  {'Iter':>4}  {'Agent':<12}  {'Rating':>6}  {'Fitness':>7}  Codebase")
        for row in state["history"]:
            print(
                f"  {row['iteration']:>4}  {row['rated_agent_id']:<12}  "
                f"{row['rating']:>6}  {row['fitness']:>7.2f}  {row['codebase_ref'] or '—'}"
            )

    best = state.get("best_agent")
    if best:
        ev = best["evaluation"]
        print(f"\nBest agent: {best['agent']['agent_id']}"
              f"  gen {best['agent']['generation']}"
              f"  fitness {ev['fitness']:.2f}  (rating {ev['rating']}/5)")


def cmd_best(args: argparse.Namespace) -> None:
    """Print the best prompt to stdout (pipe to your agent file)."""
    result = _get("/export")
    # Raw print — suitable for piping: python reviewer_cycle.py best > code-reviewer.md
    print(result["prompt"], end="")


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Self-improving code-reviewer CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Examples:
              python scripts/reviewer_cycle.py init --prompt-file code-reviewer.md
              python scripts/reviewer_cycle.py submit --review-file review.txt --rating 3
              python scripts/reviewer_cycle.py submit --review-file review.txt \\
                  --rating 4 --strengths "caught XSS" --gaps "missed auth tests" \\
                  --codebase-ref "my-repo @ main" --non-interactive
              python scripts/reviewer_cycle.py status
              python scripts/reviewer_cycle.py best > code-reviewer.md
        """),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # init
    p_init = sub.add_parser("init", help="Load your agent file into the engine")
    p_init.add_argument("--prompt-file", metavar="PATH",
                        help="Path to your code-reviewer.md (omit to use built-in default)")

    # submit
    p_sub = sub.add_parser("submit", help="Submit a completed review for rating")
    p_sub.add_argument("--review-file", metavar="PATH", required=True,
                       help="File containing the review output")
    p_sub.add_argument("--rating", type=int, choices=range(1, 6), metavar="1-5",
                       help="Quality rating (omit for interactive prompt)")
    p_sub.add_argument("--strengths", nargs="+", metavar="TEXT",
                       help="What the review got right (space-separated strings)")
    p_sub.add_argument("--gaps", nargs="+", metavar="TEXT",
                       help="What the review missed (space-separated strings)")
    p_sub.add_argument("--codebase-ref", metavar="REF", default="",
                       help="Label for the reviewed codebase, e.g. 'my-repo @ main'")
    p_sub.add_argument("--non-interactive", action="store_true",
                       help="Skip interactive prompts for strengths/gaps")

    # status
    sub.add_parser("status", help="Show engine state and review history")

    # best
    sub.add_parser("best", help="Print the best prompt to stdout")

    args = parser.parse_args()
    {"init": cmd_init, "submit": cmd_submit, "status": cmd_status, "best": cmd_best}[args.command](args)


if __name__ == "__main__":
    main()
