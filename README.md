# hyperagents

`hyperagents` is a Python + React research artifact inspired by the HyperAgents paper (`arXiv:2603.19461v1`).

The core idea: an agent that improves not just its task behavior but also the policy that *produces* future improvements.

- A **task policy** solves a domain task (code-repository quality classification).
- A **meta policy** controls how the task policy mutates each iteration.
- A **hyperagent** bundles both into one editable record — so the mutation procedure is itself an evolvable artefact.
- An **archive** stores every discovered variant, enabling stepping-stone exploration past local optima.

## Architecture

### System Components

```mermaid
graph TB
  subgraph FE ["Frontend  (React + Vite · :4173)"]
    UI["Dashboard\nOverview · Archive · Agent Detail · Events · Runs · Live Review"]
  end

  subgraph BE ["Backend  (FastAPI · :8011)"]
    API["REST API\n/api/reset · /api/run · /api/archive\n/api/metrics · /api/runs"]
    ENGINE["HyperAgentEngine"]
    OAI["OpenAI Service\n(optional)"]
  end

  subgraph CORE ["Core Engine"]
    HA["HyperAgent\ntask_policy + meta_policy"]
    ARCHIVE["Archive\nall variants + lineage"]
    DS["Dataset\n20 train · 10 test repos"]
  end

  subgraph PERSIST ["Persistence"]
    DB[("SQLite\nhyperagents.db")]
    CSV["results/raw_metrics.csv"]
  end

  SCRIPTS["scripts/\nrun_experiment.py · plot_results.py"]

  UI        <-->|"HTTP / JSON"| API
  API       --> ENGINE
  ENGINE    --> HA
  ENGINE    --> ARCHIVE
  ENGINE    --> DS
  ENGINE    -.->|"optional"| OAI
  ENGINE    -->|"persist"| DB
  SCRIPTS   -->|"direct import"| ENGINE
  SCRIPTS   --> CSV
```

### Evolutionary Loop

```mermaid
flowchart TD
  SEED["Seed HyperAgent\nweights · threshold · style\nfocus · steps · exploration"]
  SEED --> ARC

  ARC["Archive\nall variants + scores + parent links"]
  ARC -->|"weighted selection\nfitness × exploration × novelty"| PARENT["Parent Agent"]
  PARENT -->|"meta_policy drives"| MUT

  MUT["Mutation\n① error-pressure weight update\n② stochastic noise\n③ threshold adjustment\n④ meta-param update"]
  MUT --> CHILD["Child HyperAgent"]
  CHILD --> EVAL

  EVAL["Evaluation\ntrain accuracy  ·  test accuracy\nFP count  ·  FN count"]
  EVAL -->|"improved → shrink exploration\nno change → grow exploration"| ADJUST["Meta Adjustment"]
  ADJUST --> ARC
  EVAL -->|"record"| LOG["Progress Log  →  SQLite + CSV"]
```

### Ablation Conditions

```mermaid
graph LR
  subgraph HA ["HyperAgent  (full system)"]
    direction TB
    HA1["Weighted archive\nparent selection"] --> HA2["Adaptive meta policy"]
  end
  subgraph BL ["Baseline  (frozen meta)"]
    direction TB
    BL1["Weighted archive\nparent selection"] --> BL2["Fixed meta policy"]
  end
  subgraph NA ["No Archive  (greedy)"]
    direction TB
    NA1["Always current\nbest agent"] --> NA2["Adaptive meta policy"]
  end
```

> Full diagrams, database schema, API reference, and directory layout: [`docs/architecture.md`](docs/architecture.md).

---

## What Is Implemented

**Core loop**
- Evolutionary hyperagent loop with weighted archive parent selection
- Task policy self-modification: per-feature weights, decision threshold, review style
- Meta policy self-modification: step sizes, focus metric, exploration scale, memory notes
- Error-pressure mutation: false-positive and false-negative feature averages drive directional updates

**Ablation conditions** (selectable from the UI or experiment runner)
- `hyperagent` — full system (adaptive meta policy + archive)
- `baseline` — frozen meta policy, archive enabled (isolates meta-policy contribution)
- `no_archive` — adaptive meta policy, greedy parent selection (isolates archive contribution)

**Experiment infrastructure**
- Multi-seed runner (`scripts/run_experiment.py`): 3 conditions × 5 seeds × N iterations → `results/raw_metrics.csv`
- Learning curve plots (`scripts/plot_results.py`): mean ± std across seeds, train + test panels, meta-policy drift
- SQLite persistence: every run, agent variant, per-iteration metric, and mutation event is stored immediately

**Dataset**
- 20 training repositories (8 accepted, 12 rejected) — 10 clearly separated + 10 borderline
- 10 held-out test repositories (4 accepted, 6 rejected) — 6 clearly separated + 4 borderline
- Seed agent starts at ~65% train accuracy, leaving meaningful room for improvement

**UI (React, tabbed)**
- Overview: best agent stats, mode selector, run controls
- Archive: sortable table of all variants with fitness and parent links
- Agent Detail: weights, meta parameters, lineage notes, evaluation breakdown
- Events: mutation log
- Runs: saved experiment list with load / delete / CSV export
- Live Review: manual repository scoring (optional OpenAI)

---

## Project Structure

```text
hyperagents/
├── backend/
│   ├── app/
│   │   ├── datasets.py          # 20 train + 10 test repo fixtures
│   │   ├── database.py          # SQLModel tables + Database class
│   │   ├── engine.py            # HyperAgentEngine — core evolutionary loop
│   │   ├── main.py              # FastAPI app + route handlers
│   │   ├── openai_service.py    # Optional LLM mutation planner
│   │   ├── settings.py          # Env-driven config
│   │   └── prompts/             # Prompt templates for OpenAI calls
│   └── pyproject.toml
├── frontend/
│   └── src/
│       ├── App.jsx              # Tabbed dashboard
│       ├── api.js               # Fetch wrappers
│       └── styles.css
├── scripts/
│   ├── run_experiment.py        # Multi-seed ablation runner
│   └── plot_results.py          # Matplotlib learning curves + meta drift
├── docs/
│   ├── architecture.md          # Full architecture reference
│   └── methods.md               # Methods section draft (arXiv paper)
├── results/
│   ├── raw_metrics.csv          # Pre-generated: 3 conditions × 5 seeds × 30 iter
│   ├── learning_curves.png      # Train + test accuracy panels
│   └── meta_policy_drift.png    # Weight step / threshold step / exploration scale
├── run.ps1                      # One-command local start (Windows)
└── stop.ps1                     # One-command local stop
```

---

## Quick Start

### Option A — one command (Windows)

```powershell
./run.ps1
```

Starts backend and frontend together. To stop:

```powershell
./stop.ps1
```

Default URLs:
- Frontend: `http://127.0.0.1:4173`
- Backend API: `http://127.0.0.1:8011/api`

The script finds Python 3.11+ and Node.js, installs missing dependencies, loads `.env.local` if present, and saves logs and PIDs under `.run/`.

### Option B — manual

**Backend** (Python 3.11+):

```powershell
cd backend
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e .
uvicorn app.main:app --reload --port 8011
```

**Frontend** (Node.js 20+):

```powershell
cd frontend
npm install
$env:VITE_API_BASE="http://127.0.0.1:8011/api"
npm run dev -- --port 4173
```

---

## Running the Ablation Experiment

Generate the CSV and plots used in the paper:

```powershell
# from repo root, with backend venv active
python scripts/run_experiment.py --iterations 30 --seeds 5
python scripts/plot_results.py
```

Outputs:
- `results/raw_metrics.csv` — per-iteration scores for all conditions and seeds
- `results/learning_curves.png` — train + test accuracy learning curves
- `results/meta_policy_drift.png` — meta-policy parameter trajectories

Key result: the **No Archive** condition plateaus at 80% train accuracy while both archive conditions reach 85%, demonstrating the stepping-stones contribution of the archive.

---

## OpenAI Integration (optional)

Copy `.env.example` to `.env.local` and set:

```powershell
OPENAI_API_KEY=your_key_here
OPENAI_MODEL=gpt-4o-mini
HYPERAGENTS_USE_OPENAI=1
```

When enabled, the backend uses the OpenAI API for mutation planning and the Live Review tab. Without those variables the system runs fully offline using the deterministic heuristic engine.

> Do not paste API keys into chat, code, or git history. If a key has been exposed, revoke it immediately.

---

## Why This Matches The Paper

The paper's key mechanism is not just recursive optimization — it is **metacognitive self-modification**: the procedure that creates future improvements is itself editable. In this implementation:

- `task_policy` controls how a repository is scored and classified
- `meta_policy` controls how future mutations are proposed
- both live inside the same mutable agent record
- both can be modified by the system during a run

That is the minimal practical instantiation of the hyperagent idea.

---

## Extending the Project

- Replace the heuristic mutation operator with an LLM-driven one (prompts are already templated in `backend/app/prompts/`)
- Swap the synthetic dataset for a real code-quality benchmark
- Add MAP-Elites or quality-diversity selection for broader archive coverage
- Port to a multi-domain setting to study cross-domain transfer of meta policies
