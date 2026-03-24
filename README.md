# hyperagents

`hyperagents` is a Python + React proof-of-concept inspired by the HyperAgents paper (`arXiv:2603.19461v1`).

This implementation does not try to reproduce the full research stack. Instead, it captures the core idea in a form that is small, inspectable, and easy to extend:

- A `task agent` solves a domain task.
- A `meta agent` modifies the task agent and itself.
- A `hyperagent` bundles both into one editable artifact.
- An `archive` stores past variants so promising lineages can keep improving.

The first domain is a deterministic paper-review simulator. That keeps the framework easy to run locally while still showing the main research concept: the system improves both its task behavior and its own improvement policy over time.

## What Is Implemented

- FastAPI backend for running hyperagent iterations
- In-memory archive of agent variants
- Parent selection from the archive
- Self-modification of task policy and meta policy
- Evaluation on train and test review examples
- React dashboard to inspect archive state, progress, and the best agent

## Project Structure

```text
backend/
  app/
    datasets.py
    engine.py
    main.py
  pyproject.toml
frontend/
  src/
    api.js
    App.jsx
    main.jsx
    styles.css
  index.html
  package.json
  vite.config.js
docs/
  architecture.md
```

## Step By Step

### 0. One-command local run

If you want the backend and frontend started together:

```powershell
./run.ps1
```

To stop both services later:

```powershell
./stop.ps1
```

Default URLs:

- Frontend: `http://127.0.0.1:4173`
- Backend: `http://127.0.0.1:8011/api`

The script will:

- find Python 3.11+ and Node.js
- install missing backend/frontend dependencies
- write `frontend/.env.local` with the backend API URL
- start both services
- save logs and PID files under `.run/`

### 1. Backend setup

Requirements:

- Python 3.11+

Commands:

```powershell
cd backend
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e .
uvicorn app.main:app --reload
```

If your machine uses `python` instead of `py`, replace the launcher accordingly.

The API will start on `http://localhost:8000`.

### 2. Frontend setup

Requirements:

- Node.js 20+

Commands:

```powershell
cd frontend
npm install
npm run dev
```

The UI expects the backend at `http://localhost:8000/api`. Override it with `VITE_API_BASE` if needed.

### 3. Run the proof-of-concept

1. Open the frontend.
2. Click `Run Iterations`.
3. Inspect how new child agents change:
   - task weights
   - decision threshold
   - review persona
   - meta focus metric
   - exploration strength
   - memory notes

### 4. Next extension points

- Replace the deterministic task agent with an LLM-backed task runner
- Replace the heuristic meta agent with an LLM-driven code or prompt editor
- Persist runs to SQLite or Postgres
- Add multiple domains and cross-domain transfer runs
- Add baseline modes such as `no self-improvement` and `no archive`

## Why This Matches The Paper

The paper’s key mechanism is not just recursive optimization. It is metacognitive self-modification: the procedure that creates future improvements is itself editable. In this project:

- `task_policy` controls how an agent reviews papers
- `meta_policy` controls how future mutations are proposed
- both live inside the same agent record
- both can be changed by the system during the run

That is the smallest practical version of the hyperagent idea.

## Current Limitations

- The initial implementation uses a simulated task domain, not a live FM-backed agent
- State is stored in memory only
- The UI is intended for local experimentation, not production deployment
- I could not run dependency installation in this environment because Python and Node runtimes are not installed here

## Recommended Next Step

Start the backend and frontend, verify the loop works locally, then choose one of these directions:

1. Add real LLM calls for the task agent
2. Add real LLM calls for the meta agent
3. Add a second benchmark domain to test transfer
