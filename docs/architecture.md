# Architecture

## 1. System Overview

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

  SCRIPTS["scripts/\nrun_experiment.py\nplot_results.py"]

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

---

## 2. HyperAgent Structure

```mermaid
classDiagram
  class HyperAgent {
    +agent_id : str
    +parent_id : str
    +generation : int
    +task_policy : TaskPolicy
    +meta_policy : MetaPolicy
    +lineage_notes : list[str]
  }

  class TaskPolicy {
    +weights : dict[str, float]
    +threshold : float
    +review_style : str
    +score(repo) float
    +classify(repo) int
  }

  class MetaPolicy {
    +focus_metric : str
    +weight_step : float
    +threshold_step : float
    +exploration_scale : float
    +memory : list[str]
  }

  class Evaluation {
    +fitness : float
    +train_accuracy : float
    +test_accuracy : float
    +false_positive_count : int
    +false_negative_count : int
    +false_positive_feature_avgs : dict
    +false_negative_feature_avgs : dict
  }

  class ArchiveEntry {
    +agent : HyperAgent
    +evaluation : Evaluation
    +created_iteration : int
  }

  HyperAgent *-- TaskPolicy
  HyperAgent *-- MetaPolicy
  ArchiveEntry *-- HyperAgent
  ArchiveEntry *-- Evaluation
```

The key structural property from the paper (arXiv:2603.19461v1): **both policies reside
in the same mutable record** — the procedure that produces future variants is itself
an editable artefact.

---

## 3. Evolutionary Loop

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

  EVAL -->|"improved?\nyes → shrink exploration\nno  → grow  exploration"| ADJUST["Meta Adjustment"]
  ADJUST --> ARC

  EVAL -->|"record"| LOG["Progress Log\nSQLite + CSV"]
```

### Loop Steps (numbered)

| # | Step | Key action |
|---|------|------------|
| 1 | Parent selection | Weighted sample from archive: `P ∝ fitness × exploration_scale × (1 + generation)⁻¹` |
| 2 | Mutation | Error-pressure drives weight direction; `exploration_scale` sets noise amplitude |
| 3 | Evaluation | Score child on all 20 train + 10 test repos |
| 4 | Post-eval meta-adjust | `exploration_scale ↓` on improvement, `↑` otherwise |
| 5 | Archive update | Child unconditionally added (stepping-stones property) |
| 6 | Progress record | Metrics written to SQLite and in-memory log |

---

## 4. Ablation Conditions

```mermaid
graph LR
  subgraph HA ["HyperAgent  (full system)"]
    direction TB
    HA1["Weighted archive\nparent selection"]
    HA2["Adaptive meta policy\n(self-modifying)"]
    HA1 --> HA2
  end

  subgraph BL ["Baseline  (frozen meta)"]
    direction TB
    BL1["Weighted archive\nparent selection"]
    BL2["Fixed meta policy\n(seed values only)"]
    BL1 --> BL2
  end

  subgraph NA ["No Archive  (greedy)"]
    direction TB
    NA1["Always current\nbest agent only"]
    NA2["Adaptive meta policy\n(self-modifying)"]
    NA1 --> NA2
  end
```

| Condition | Archive selection | Meta-policy update | Isolates |
|-----------|-------------------|--------------------|----------|
| **HyperAgent** | Weighted full archive | Adaptive | — (full system) |
| **Baseline** | Weighted full archive | Frozen at seed | Meta-policy contribution |
| **No Archive** | Always current best | Adaptive | Archive contribution |

---

## 5. Database Schema

```mermaid
erDiagram
  Run {
    int    id PK
    string uuid
    string mode
    int    seed
    string status
    int    iterations_completed
    float  best_train_accuracy
    float  best_test_accuracy
    string created_at
    string updated_at
  }

  AgentRecord {
    int    id PK
    int    run_id FK
    string agent_id
    string parent_id
    int    generation
    string task_policy_json
    string meta_policy_json
    float  train_accuracy
    float  test_accuracy
    float  fitness
    int    iteration
  }

  ProgressRecord {
    int    id PK
    int    run_id FK
    int    iteration
    float  child_train_accuracy
    float  child_test_accuracy
    float  best_fitness
    float  best_test_accuracy
    string meta_focus_metric
    float  meta_weight_step
    float  meta_threshold_step
    float  meta_exploration_scale
    string mutation_source
  }

  EventRecord {
    int    id PK
    int    run_id FK
    string event_type
    string payload_json
    string created_at
  }

  Run ||--o{ AgentRecord    : "contains"
  Run ||--o{ ProgressRecord : "tracks"
  Run ||--o{ EventRecord    : "logs"
```

---

## 6. API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/reset` | Initialise a new run; body: `{mode}` |
| `POST` | `/api/run` | Execute N iterations; body: `{iterations}` |
| `GET`  | `/api/status` | Current engine state |
| `GET`  | `/api/archive` | All archive entries |
| `GET`  | `/api/metrics/json` | Per-iteration metrics as JSON |
| `GET`  | `/api/metrics/csv` | Per-iteration metrics as CSV download |
| `GET`  | `/api/runs` | Saved run list |
| `GET`  | `/api/runs/{id}` | Single run snapshot |
| `POST` | `/api/runs/{id}/load` | Restore a saved run into engine |
| `DELETE` | `/api/runs/{id}` | Delete a saved run |
| `POST` | `/api/review` | Live repo review (optional OpenAI) |

---

## 7. Frontend Tab Map

```mermaid
graph LR
  NAV["Tab Navigation (sticky)"]

  NAV --> OV["Overview\nbest agent · stats bar\nmode selector · run controls"]
  NAV --> AR["Archive\nsortable agent table\nparent links"]
  NAV --> AD["Agent Detail\nweights · meta params\nlineage notes · eval breakdown"]
  NAV --> EV["Events\nmutation log"]
  NAV --> RU["Runs\nsaved experiments\nload / delete / compare"]
  NAV --> LR["Live Review\nmanual repo scoring"]
```

---

## 8. Directory Layout

```text
hyperagents/
├── backend/
│   ├── app/
│   │   ├── datasets.py          # 20 train + 10 test repo fixtures
│   │   ├── database.py          # SQLModel tables + Database class
│   │   ├── engine.py            # HyperAgentEngine (core loop)
│   │   ├── main.py              # FastAPI app + route handlers
│   │   ├── openai_service.py    # Optional LLM mutation planner
│   │   ├── settings.py          # Env-driven config (port, db path, OpenAI)
│   │   └── prompts/             # .md prompt templates for OpenAI calls
│   └── pyproject.toml
├── frontend/
│   └── src/
│       ├── App.jsx              # Tabbed dashboard
│       ├── api.js               # Typed fetch wrappers
│       └── styles.css
├── scripts/
│   ├── run_experiment.py        # Multi-seed ablation runner → CSV
│   └── plot_results.py          # Matplotlib learning curves + meta drift
├── docs/
│   ├── architecture.md          # This file
│   └── methods.md               # Methods section draft (arXiv paper)
├── results/
│   ├── raw_metrics.csv          # 3 conditions × 5 seeds × 30 iterations
│   ├── learning_curves.png      # Train + test accuracy panels
│   └── meta_policy_drift.png    # Weight step / threshold step / exploration
├── run.ps1                      # One-command local start (Windows)
└── stop.ps1                     # One-command local stop
```
