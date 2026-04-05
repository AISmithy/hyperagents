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
├── scripts/               ← Run experiments from the command line
│   ├── run_experiment.py  ← Runs all 3 modes × 5 seeds automatically
│   └── plot_results.py    ← Generates graphs from results
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

## Self-Improving Code Reviewer (Prompt Engine)

This is a second, separate engine built on the same HyperAgent principles — but instead of evolving numerical weights, it evolves the **text of a code reviewer prompt** (like a `code-reviewer.md` file).

### The idea

Every time you use a code reviewer agent on your codebase, you can rate how useful the review was. The engine uses that rating to automatically improve the prompt for next time.

### How it works

```
Step 1 — Load your existing code-reviewer.md as the starting prompt.

Step 2 — Run a review of your codebase using that prompt.

Step 3 — Read the review. Note what it got right and what it missed.

Step 4 — Submit your rating (1–5) and your notes to the engine.

Step 5 — The engine mutates the prompt:
           - With OpenAI: GPT rewrites the prompt, fixing the gaps
           - Without OpenAI: targeted instructions are appended based on your gaps

Step 6 — The improved prompt becomes the active one for next time.

Step 7 — Repeat after your next review cycle.
```

Every version of the prompt is kept in an **archive** — the same stepping-stones mechanism as the research engine. If a new version turns out worse, the system can build from an earlier good version.

---

### Using the Prompt Engine via API

All prompt engine endpoints are under `/api/promptagent/`.

**1. Load your agent**

Pass the contents of your `code-reviewer.md`:

```bash
curl -X POST http://localhost:8000/api/promptagent/reset \
  -H "Content-Type: application/json" \
  -d "{\"seed_prompt\": \"$(cat code-reviewer.md)\"}"
```

Or call it with an empty body to use the built-in default prompt:

```bash
curl -X POST http://localhost:8000/api/promptagent/reset \
  -H "Content-Type: application/json" \
  -d "{}"
```

---

**2. Check the active prompt**

```bash
curl http://localhost:8000/api/promptagent/state
```

Returns the current prompt, full archive of past versions, and review history.

---

**3. Submit a review result**

After running a review, tell the engine how it went:

```bash
curl -X POST http://localhost:8000/api/promptagent/submit \
  -H "Content-Type: application/json" \
  -d '{
    "review_text": "...the actual review output...",
    "rating": 3,
    "strengths": ["caught SQL injection in login.py"],
    "gaps": ["missed missing tests in auth module", "no error handling coverage"],
    "codebase_ref": "my-repo @ main"
  }'
```

| Field | Required | Description |
|---|---|---|
| `review_text` | Yes | The full output of the review (or a summary) |
| `rating` | Yes | 1 (poor) to 5 (excellent) |
| `strengths` | No | List of things the review got right |
| `gaps` | No | List of things it missed — this drives the mutation |
| `codebase_ref` | No | A label for the codebase reviewed (e.g. `my-repo @ main`) |

The response contains `new_prompt` — the evolved version ready for the next review.

---

**4. Export the best prompt back to your file**

```bash
curl http://localhost:8000/api/promptagent/export | python -c "import sys,json; print(json.load(sys.stdin)['prompt'])" > code-reviewer.md
```

This writes the highest-rated prompt version found so far back to your file.

---

### Rating guide

| Rating | Meaning |
|---|---|
| 1 | The review missed most issues or was too vague to be useful |
| 2 | Some useful findings but significant gaps |
| 3 | Decent review, a few important things missed |
| 4 | Good review, minor gaps only |
| 5 | Excellent — caught everything important, clear and actionable |

The gaps you list at rating 3 or below are the most important input — they directly tell the engine what to fix in the next prompt version.

---

### With vs without OpenAI

| | Without OpenAI | With OpenAI |
|---|---|---|
| **How mutation works** | Appends gap-targeted instructions to the prompt | GPT rewrites the full prompt guided by your feedback |
| **Result** | Prompt grows slightly each iteration | Prompt is restructured and tightened each iteration |
| **Cost** | Free, fully offline | One API call per review cycle |

Both modes keep the full archive and stepping-stones mechanism.

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

**Q: What is "fitness" in the prompt engine?**
Your rating normalised to 0.0–1.0. Rating 1 = fitness 0.0, rating 5 = fitness 1.0. The engine always keeps the highest-fitness prompt as the "best" and exports that.

**Q: Does the prompt engine use the same archive as the research engine?**
No — they are completely separate. The research engine evolves numerical weights; the prompt engine evolves prompt text. They share the same server but have independent state.

**Q: What if I forget to submit a rating?**
Nothing is lost — the prompt engine only advances when you call `/submit`. You can use the same active prompt for as many review cycles as you like before submitting.

---

## Key Files to Read First

If you want to understand the code, read these in order:

**Research engine (numerical weights):**
1. [backend/app/datasets.py](../backend/app/datasets.py) — the 30 repos used for training/testing (short, no dependencies)
2. [backend/app/engine.py](../backend/app/engine.py) — the full evolutionary loop (the heart of the project)

**Prompt engine (code-reviewer evolution):**

3. [backend/app/prompt_engine.py](../backend/app/prompt_engine.py) — the prompt evolution loop
4. [backend/app/prompts/mutate_reviewer_prompt.md](../backend/app/prompts/mutate_reviewer_prompt.md) — what the LLM is asked to do when mutating a prompt

**Shared infrastructure:**

5. [backend/app/main.py](../backend/app/main.py) — the API that connects everything
6. [frontend/src/api.js](../frontend/src/api.js) — how the UI talks to the backend
7. [scripts/run_experiment.py](../scripts/run_experiment.py) — how experiments are run in batch
