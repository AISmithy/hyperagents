# Hyperagents — Beginner's Guide

> This guide assumes you are new to the project. No prior knowledge of AI research or the codebase is needed.

---

## What Is This Project?

Imagine a hiring manager whose job is to look at job applications and decide: **accept** or **reject**.

Over time, a good hiring manager does not just get better at reviewing applications — they also get better at *how they improve their own reviewing process*. They learn better ways to learn.

That is exactly what this project does, but for **code repositories** instead of job applications.

A **HyperAgent** is an AI reviewer that:
1. Looks at a code repository and scores it on 5 qualities
2. Decides: is this repo good enough to accept or not?
3. After each decision, **updates its own scoring rules** to do better next time
4. Also **updates the rules that control how it updates** — this is the "hyper" part

The project is a proof-of-concept implementation of the ideas from the research paper `arXiv:2603.19461`.

---

## The Core Idea in Plain English

Most AI systems improve their **answers**.

This system also improves its **improvement strategy**.

Think of it in layers:

| Layer | What it does | Called |
|---|---|---|
| Layer 1 | Scores and classifies a repo | **Task Policy** |
| Layer 2 | Controls how Layer 1 changes | **Meta Policy** |

Both layers live inside one agent and both can be changed by the system — that is what makes it a HyperAgent.

---

## What Does It Actually Do?

The system works with a dataset of **30 fake code repositories**:
- 20 are used for **training** (the agent learns from these)
- 10 are used for **testing** (we check if the learning generalised)

Each repository has 5 scores between 0 and 1:

| Feature | What it measures |
|---|---|
| **Maintainability** | Is the code easy to maintain? |
| **Security** | Does it have security vulnerabilities? |
| **Test Coverage** | Does it have tests? |
| **Documentation** | Is it well documented? |
| **Simplicity** | Is the code simple and clean? |

Each repo also has a label: **accept (1)** or **reject (0)**.

The agent learns to predict the label correctly by adjusting how much weight it gives to each feature.

---

## How the Agent Improves — Step by Step

This is the core loop that runs every time you click **Run Iterations**:

```
Step 1 — Pick a parent
         Choose an existing agent from the archive to build upon.
         Better agents are more likely to be chosen, but older variants
         are kept too (they act as stepping stones past dead ends).

Step 2 — Mutate
         Create a child agent by tweaking the parent's weights.
         The meta policy decides HOW MUCH to tweak and in WHICH direction.
         Direction is guided by past mistakes:
           - Too many false positives? Raise the bar.
           - Too many false negatives? Lower the bar.

Step 3 — Evaluate
         Run the child agent over all 30 repos and measure accuracy.
         Count how many mistakes it makes and what kind.

Step 4 — Adjust the meta policy
         If the child improved → reduce exploration (be more focused).
         If the child did not improve → increase exploration (try harder).

Step 5 — Save to archive
         Every child is saved, even bad ones.
         This lets the system revisit earlier paths that might lead somewhere.

Step 6 — Log results
         Write all scores to SQLite database and CSV file.
```

Then repeat from Step 1.

---

## The Three Experiment Modes

You can run the system in three different modes. These exist to prove which parts of the design actually matter.

| Mode | What changes | What it proves |
|---|---|---|
| **HyperAgent** (full) | Both task and meta policy evolve | The complete system |
| **Baseline** (frozen meta) | Meta policy is locked; only task policy evolves | That meta-improvement adds value |
| **No Archive** (greedy) | Always mutates from the single best agent | That keeping old variants adds value |

The key finding: HyperAgent and Baseline both outperform No Archive — keeping the archive of stepping stones matters.

---

## Project Structure

```
hyperagents/
│
├── backend/               ← Python server (the brain)
│   └── app/
│       ├── engine.py          ← Research engine: evolves numerical weights
│       ├── prompt_engine.py   ← Prompt engine: evolves your code-reviewer.md
│       ├── datasets.py        ← The 30 fake repos used for training/testing
│       ├── database.py        ← Saves everything to SQLite
│       ├── main.py            ← Web API (connects UI to both engines)
│       ├── settings.py        ← Configuration (ports, API keys)
│       ├── openai_service.py  ← Optional: use GPT to guide mutations
│       └── prompts/
│           ├── propose_mutation.md       ← LLM prompt for weight mutation
│           └── mutate_reviewer_prompt.md ← LLM prompt for prompt mutation
│
├── frontend/              ← React web dashboard (what you see in browser)
│   └── src/
│       ├── App.jsx        ← The entire UI
│       └── api.js         ← Talks to the backend
│
├── scripts/               ← Run experiments and reviewer cycle from command line
│   ├── run_experiment.py  ← Runs all 3 modes × 5 seeds automatically
│   ├── plot_results.py    ← Generates graphs from results
│   └── reviewer_cycle.py ← CLI for the self-improving reviewer loop
│
├── docs/                  ← Documentation
├── results/               ← CSV files and graphs are saved here
│   ├── runs.csv           ← Per-iteration log from the research engine
│   └── prompt_runs.csv    ← Per-review log from the prompt engine
└── hyperagents.db         ← SQLite database (auto-created on first run)
```

---

## How to Run It

### Prerequisites

You need:
- **Python 3.11 or newer** — [python.org/downloads](https://python.org/downloads)
- **Node.js 20 or newer** — [nodejs.org](https://nodejs.org)

Check you have them:
```bash
python --version   # should say 3.11+
node --version     # should say v20+
```

---

### Step 1 — Get the code

```bash
git clone https://github.com/AISmithy/hyperagents.git
cd hyperagents
```

---

### Step 2 — Start the backend (Python server)

```bash
cd backend
pip install -e .
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Leave this terminal open. You should see:
```
Application startup complete.
```

---

### Step 3 — Start the frontend (browser UI)

Open a **new terminal**:

```bash
cd frontend
npm install
npm run dev -- --port 5173
```

You should see:
```
Local: http://localhost:5173/
```

---

### Step 4 — Open the app

Go to **http://localhost:5173** in your browser.

You should see the hyperagents dashboard with the agent overview and controls.

---

## Using the Dashboard

The UI has 7 tabs across the top:

### Overview tab
The main screen. Shows:
- The **best agent** found so far and its accuracy scores
- Controls to **Run Iterations** (how many steps to evolve)
- A **mode selector** (HyperAgent / Baseline / No Archive)
- A **progress chart** showing accuracy improving over time
- A **Reset** button to start a fresh run

**To run an experiment:**
1. Pick a mode (start with HyperAgent)
2. Set iterations to `10`
3. Click **Run Iterations**
4. Watch the chart update

---

### Archive tab
Shows every agent variant ever created in this run, sorted by performance.

Each row shows:
- Agent ID (e.g. `agent-007`)
- Which generation it is
- Its review style (strict / balanced / lenient)
- Train and test accuracy
- Which feature it focused on
- How many mistakes it made

Click any row to inspect that agent in detail.

---

### Agent Detail tab
Deep dive into one agent:
- **Task Policy** — the 5 feature weights and decision threshold
- **Meta Policy** — the step sizes and focus metric
- **Evaluation** — how many repos it got wrong and why

---

### Events tab
A log of recent mutations showing:
- Which agent was the parent
- Which agent was the child
- Whether accuracy went up or down (Δ fitness)
- A plain-English summary of what changed

---

### Runs tab
Every time you click Reset, a new **run** is created and saved to the database.

Here you can:
- See all past runs with their final scores
- **Load** an old run to inspect or continue it
- **Delete** runs you no longer need
- **Export CSV** to download the metrics for analysis

---

### Accounts tab
Add synthetic organisations or GitHub accounts to expand the training dataset.

Each account generates extra repos with feature scores that get mixed into the training data.

After adding accounts, click **Apply All to Dataset** then **Reset** to start a new run with the bigger dataset.

---

### Live Review tab
Paste a GitHub repository URL and the system will score it using the best agent.

Requires an OpenAI API key (optional — see below).

---

## Running the Full Experiment (Command Line)

To reproduce the paper results (all 3 modes × 5 seeds × 30 iterations):

```bash
# from the repo root, with the backend venv active
python scripts/run_experiment.py --iterations 30 --seeds 5
```

This takes a few minutes and saves results to `results/raw_metrics.csv`.

To generate the graphs:
```bash
python scripts/plot_results.py
```

This saves two images to `results/`:
- `learning_curves.png` — accuracy over iterations for all 3 conditions
- `meta_policy_drift.png` — how the meta policy parameters change over time

---

## Optional: Enable OpenAI

By default the system runs fully offline using a deterministic heuristic engine.

To use GPT to guide mutations and enable the Live Review tab:

1. Create a file called `.env.local` in the `frontend/` folder
2. Add:

```
VITE_API_BASE=http://127.0.0.1:8000/api
```

3. Create a file called `.env.local` in the `backend/` folder (or set environment variables):

```
OPENAI_API_KEY=your_key_here
OPENAI_MODEL=gpt-4o-mini
HYPERAGENTS_USE_OPENAI=1
```

> Never commit API keys to git. If a key is exposed, revoke it immediately.

---

## Self-Improving Prompt Engine

> Full documentation, CLI reference, API reference, and FAQ are in
> [backend/app/selfimprovingprompt/docs/](../backend/app/selfimprovingprompt/docs/)

This is a second, separate engine built on the same HyperAgent principles — but instead of evolving numerical weights, it evolves the **text of any agent prompt** (like a `code-reviewer.md` or any other `.md` agent file).

### The cycle — as a diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                  YOUR code-reviewer.md                          │
│              (the prompt your agent uses)                       │
└───────────────────────────┬─────────────────────────────────────┘
                            │  reviewer_cycle.py init
                            │  (first time only)
                            ▼
                    ┌───────────────┐
                    │  PromptEngine │  ◄── archive of all
                    │  (backend)    │       past versions
                    └───────┬───────┘
                            │  active prompt
                            ▼
              ┌─────────────────────────────┐
              │  Run review on your codebase │
              │  (Claude, GPT, local LLM…)  │
              └─────────────┬───────────────┘
                            │  review output saved to file
                            ▼
              ┌─────────────────────────────┐
              │  reviewer_cycle.py submit   │
              │  --review-file review.txt   │
              │  --rating 3                 │
              │  --gaps "missed auth tests" │
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
│                  YOUR code-reviewer.md                          │
│              (automatically updated ✓)                          │
└─────────────────────────────────────────────────────────────────┘
                            │
                            └──► repeat from "Run review"
```

Every version of the prompt is kept in the **archive** — the same stepping-stones mechanism as the research engine. If a new version turns out worse, the system can build on an earlier good version rather than getting stuck.


For setup, CLI usage, API reference, and FAQ see
[backend/app/selfimprovingprompt/docs/GUIDE.md](../backend/app/selfimprovingprompt/docs/GUIDE.md).

---

## Common Questions

**Q: What is "fitness"?**
The agent's accuracy on the training set. Higher is better. Starts around 65% and can reach 85%+.

**Q: Why does the archive keep bad agents?**
Bad agents are stepping stones. A bad agent at generation 5 might lead to a great agent at generation 10 via a path the greedy approach would never explore.

**Q: What is train vs test accuracy?**
Train accuracy = how well the agent does on the 20 repos it learned from.
Test accuracy = how well it does on the 10 repos it has never seen. Test accuracy tells you if the learning generalised or just memorised.

**Q: What happens when I click Reset?**
The engine starts fresh with a new seed agent. The previous run is saved to the database and visible in the Runs tab.

**Q: Can I run multiple conditions and compare them?**
Yes — use the experiment script (`run_experiment.py`) which runs all 3 conditions automatically and writes a single CSV you can analyse or plot.

---

---

## Key Files to Read First

If you want to understand the code, read these in order:

**Research engine (numerical weights):**
1. [backend/app/datasets.py](../backend/app/datasets.py) — the 30 repos used for training/testing (short, no dependencies)
2. [backend/app/engine.py](../backend/app/engine.py) — the full evolutionary loop (the heart of the project)

**Prompt engine (self-improving agent prompts):**

3. [backend/app/selfimprovingprompt/engine.py](../backend/app/selfimprovingprompt/engine.py) — the prompt evolution loop
4. [backend/app/selfimprovingprompt/prompts/mutate_agent_prompt.md](../backend/app/selfimprovingprompt/prompts/mutate_agent_prompt.md) — what the LLM is asked to do when mutating a prompt
5. [backend/app/selfimprovingprompt/cli.py](../backend/app/selfimprovingprompt/cli.py) — the CLI tool
6. [backend/app/selfimprovingprompt/docs/GUIDE.md](../backend/app/selfimprovingprompt/docs/GUIDE.md) — full prompt engine guide

**Shared infrastructure:**

7. [backend/app/main.py](../backend/app/main.py) — the API that connects everything
8. [frontend/src/api.js](../frontend/src/api.js) — how the UI talks to the backend
9. [scripts/run_experiment.py](../scripts/run_experiment.py) — how experiments are run in batch
