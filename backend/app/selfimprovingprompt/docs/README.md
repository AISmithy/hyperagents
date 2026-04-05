# Self-Improving Prompt Engine

Evolves any agent defined as a text prompt file (`.md`) based on human
feedback ratings after each real usage cycle. Built on the same
HyperAgent principles as the research engine — archive of stepping stones,
meta-policy, LLM-guided mutation — but the TaskPolicy is a **text prompt**
rather than numerical weights.

---

## The idea

Every time you run an agent (code reviewer, PR summariser, test generator,
any agent) you rate how useful the output was. The engine uses that signal
to automatically improve the prompt for next time. Every version is archived
so the system never gets stuck in a local optimum.

---

## The cycle

```
┌─────────────────────────────────────────────────────────────────┐
│                    YOUR agent-name.md                           │
│              (the prompt your agent uses)                       │
└───────────────────────────┬─────────────────────────────────────┘
                            │  cli.py init
                            │  (first time only)
                            ▼
                    ┌───────────────┐
                    │  PromptEngine │  ◄── archive of all
                    │  (backend)    │       past versions
                    └───────┬───────┘
                            │  active prompt
                            ▼
              ┌─────────────────────────────┐
              │  Run your agent on any task  │
              │  (Claude, GPT, local LLM…)  │
              └─────────────┬───────────────┘
                            │  output saved to file
                            ▼
              ┌─────────────────────────────┐
              │  cli.py submit              │
              │  --review-file output.txt   │
              │  --rating 3                 │
              │  --gaps "missed X"          │
              └─────────────┬───────────────┘
                            │
              ┌─────────────▼───────────────┐
              │     Mutation (engine)        │
              │  Without OpenAI:             │
              │    append gap instructions   │
              │  With OpenAI:                │
              │    GPT rewrites full prompt  │
              └─────────────┬───────────────┘
                            │  improved prompt
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    YOUR agent-name.md                           │
│              (automatically updated ✓)                          │
└─────────────────────────────────────────────────────────────────┘
                            │
                            └──► repeat from "Run your agent"
```

---

## Files in this package

```
selfimprovingprompt/
├── __init__.py              ← public API: from app.selfimprovingprompt import PromptEngine
├── engine.py                ← PromptEngine, PromptAgent, PromptEvaluation, PromptArchiveEntry
├── cli.py                   ← CLI: init / submit / status / best
├── prompts/
│   ├── __init__.py
│   └── mutate_agent_prompt.md  ← LLM system prompt for mutation
└── docs/
    ├── README.md            ← this file
    └── GUIDE.md             ← full usage guide with setup, CLI, API reference
```

---

## One-time setup

**Step 1 — Tell the backend where your agent file lives**

Add to `backend/.env.local`:

```
REVIEWER_PROMPT_PATH=/full/path/to/your-agent.md
```

After every submission the backend writes the improved prompt directly to
that file — no manual export step.

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

---

## Each cycle

```bash
# 1. Run your agent, save output
your-agent-tool > output.txt

# 2. Submit rating and feedback
python backend/app/selfimprovingprompt/cli.py submit \
  --review-file output.txt \
  --rating 3 \
  --gaps "missed auth tests" "no error handling coverage" \
  --non-interactive

# your-agent.md is updated automatically ✓
```

For full CLI options, API reference, rating guide, and FAQ see [GUIDE.md](GUIDE.md).

---

## With vs without OpenAI

| | Without OpenAI | With OpenAI |
|---|---|---|
| Mutation | Appends gap-targeted instructions | GPT rewrites the full prompt |
| Result | Prompt grows incrementally | Prompt is restructured each iteration |
| Cost | Free, fully offline | One API call per cycle |

Both modes keep the full archive and stepping-stones mechanism.

Enable OpenAI in `backend/.env.local`:
```
OPENAI_API_KEY=your_key_here
OPENAI_MODEL=gpt-4o-mini
HYPERAGENTS_USE_OPENAI=1
```
