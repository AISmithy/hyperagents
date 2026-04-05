# Self-Improving Prompt Engine — Full Guide

> For a quick overview and the cycle diagram see [README.md](README.md).

---

## One-time setup

**Step 1 — Tell the backend where your agent file lives**

Add this to `backend/.env.local` (create the file if it does not exist):

```
REVIEWER_PROMPT_PATH=/full/path/to/your-agent.md
```

This is the only configuration needed. After every submission the backend
writes the improved prompt directly to that file — no manual export step.

**Step 2 — Load your current agent into the engine**

```bash
python backend/app/selfimprovingprompt/cli.py init --prompt-file your-agent.md
```

Expected output:
```
Loaded prompt from your-agent.md (843 chars)

Engine initialised.
  Active agent : pagent-000
  Auto write-back configured → /path/to/your-agent.md
```

You only need to run `init` again if you want to start a completely fresh
run (clears the archive).

---

## Each cycle (repeat forever)

**Step 1 — Run your agent, save the output**

Use whatever tool you normally use with your agent file. Save the output:

```bash
cat your-agent.md | your-tool > output.txt
```

**Step 2 — Submit the result**

```bash
python backend/app/selfimprovingprompt/cli.py submit --review-file output.txt
```

The CLI will prompt interactively:

```
Rate this review 1–5 (1=poor, 5=excellent): 3

What did the agent get RIGHT? (one per line, blank line to finish)
  + caught SQL injection in login.py
  +

What did the agent MISS or get wrong? (one per line, blank line to finish)
  - missed missing tests in auth module
  - no coverage of error handling paths
  -

Submitting…

  Iteration    : 1
  Rated agent  : pagent-000
  Fitness      : 0.50  (rating 3/5)
  New agent    : pagent-001

  Prompt written back → /path/to/your-agent.md ✓
```

Your agent file is now updated. Run the next cycle with the new version.

**Or fully non-interactive (for scripted pipelines):**

```bash
python backend/app/selfimprovingprompt/cli.py submit \
  --review-file output.txt \
  --rating 3 \
  --strengths "caught SQL injection" \
  --gaps "missed auth tests" "no error handling coverage" \
  --codebase-ref "my-repo @ main" \
  --non-interactive
```

---

## CLI reference

All commands are in `backend/app/selfimprovingprompt/cli.py`.

### `init`

Load an agent file and start a fresh run.

```bash
python cli.py init [--prompt-file PATH]
```

| Argument | Description |
|---|---|
| `--prompt-file` | Path to your agent `.md` file. Omit to use the built-in default prompt. |

---

### `submit`

Submit the output of one agent run for rating and trigger prompt evolution.

```bash
python cli.py submit --review-file PATH [options]
```

| Argument | Required | Description |
|---|---|---|
| `--review-file PATH` | Yes | File containing the agent's output |
| `--rating 1-5` | No | Quality rating. Omit for interactive prompt. |
| `--strengths TEXT…` | No | What the agent got right (space-separated) |
| `--gaps TEXT…` | No | What the agent missed — drives mutation |
| `--codebase-ref REF` | No | Label for the task context, e.g. `my-repo @ main` |
| `--non-interactive` | No | Skip interactive prompts (for scripts) |

---

### `status`

Show all past iterations, ratings, and the current best agent.

```bash
python cli.py status
```

---

### `best`

Print the best prompt found so far to stdout.

```bash
python cli.py best > your-agent.md
```

---

## API reference

All endpoints are under `/api/promptagent/`.

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/promptagent/reset` | Load seed prompt, start fresh run |
| `POST` | `/api/promptagent/submit` | Submit rating + gaps, get improved prompt |
| `GET` | `/api/promptagent/state` | Full engine state: archive, history, active prompt |
| `GET` | `/api/promptagent/export` | Best prompt as JSON |

### Submit fields

| Field | Required | Description |
|---|---|---|
| `review_text` | Yes | The full output of the agent run |
| `rating` | Yes | 1 (poor) to 5 (excellent) |
| `strengths` | No | List of things the agent got right |
| `gaps` | No | List of things it missed — drives mutation |
| `codebase_ref` | No | Label for the task context |

### Example

```bash
curl -X POST http://localhost:8000/api/promptagent/submit \
  -H "Content-Type: application/json" \
  -d '{
    "review_text": "...agent output...",
    "rating": 3,
    "strengths": ["caught SQL injection"],
    "gaps": ["missed auth tests", "no error handling coverage"],
    "codebase_ref": "my-repo @ main"
  }'
```

Response includes `new_prompt` — the evolved prompt for the next cycle.

---

## Rating guide

| Rating | Meaning |
|---|---|
| 1 | Output was mostly wrong or too vague to be useful |
| 2 | Some useful findings but significant gaps |
| 3 | Decent output, a few important things missed |
| 4 | Good output, minor gaps only |
| 5 | Excellent — caught everything important, clear and actionable |

The gaps you list at rating 3 or below matter most — they directly tell
the engine what to fix in the next prompt version.

---

## FAQ

**Q: Does this work for any agent, not just code reviewers?**
Yes. The engine is domain-agnostic. Pass any agent's prompt as the seed.
The mutation LLM reads the prompt, the rating, and the gaps — it does not
know or care what the agent does.

**Q: What is "fitness"?**
Your rating normalised to 0.0–1.0. Rating 1 = 0.0, rating 5 = 1.0.
The engine keeps the highest-fitness prompt in the archive as "best".

**Q: What if a new prompt version turns out worse?**
Every version is archived — the engine never discards old variants.
The stepping-stones mechanism means it can build on any earlier version,
not just the most recent one.

**Q: What if I forget to submit a rating?**
Nothing is lost. The engine only advances when you call `submit`.
You can use the same active prompt for as many cycles as you like.

**Q: Does the engine use the same archive as the HyperAgents research engine?**
No — they are completely separate. They share the same server but have
independent state, independent archives, and independent history logs.

**Q: Where is the history saved?**
`results/prompt_runs.csv` — one row per submitted review cycle.
