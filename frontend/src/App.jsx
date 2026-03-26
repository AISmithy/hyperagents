import { startTransition, useEffect, useState } from "react";
import { fetchMetricsCsv, fetchState, resetState, reviewRepository, runIterations } from "./api";

function formatPercent(value) {
  return `${Math.round(value * 100)}%`;
}

function formatNumber(value) {
  return Number(value).toFixed(3);
}

function ProgressChart({ points }) {
  if (!points.length) {
    return null;
  }

  const width = 560;
  const height = 220;
  const padding = 18;
  const maxX = Math.max(...points.map((point) => point.iteration), 1);
  const maxY = 1;

  const toX = (value) =>
    padding + (value / maxX) * Math.max(width - padding * 2, 1);
  const toY = (value) =>
    height - padding - (value / maxY) * Math.max(height - padding * 2, 1);

  const line = points
    .map((point) => `${toX(point.iteration)},${toY(point.best_fitness)}`)
    .join(" ");

  const testLine = points
    .map((point) => `${toX(point.iteration)},${toY(point.best_test_accuracy)}`)
    .join(" ");

  return (
    <div className="chart-shell">
      <div className="chart-header">
        <h3>Progress</h3>
        <p>Best train fitness and best test accuracy over time.</p>
      </div>
      <svg viewBox={`0 0 ${width} ${height}`} className="chart">
        <rect x="0" y="0" width={width} height={height} rx="18" className="chart-bg" />
        {[0.25, 0.5, 0.75].map((tick) => (
          <line
            key={tick}
            x1={padding}
            x2={width - padding}
            y1={toY(tick)}
            y2={toY(tick)}
            className="chart-grid"
          />
        ))}
        <polyline fill="none" strokeWidth="4" points={line} className="chart-line-primary" />
        <polyline fill="none" strokeWidth="3" points={testLine} className="chart-line-secondary" />
        {points.map((point) => (
          <g key={point.iteration}>
            <circle
              cx={toX(point.iteration)}
              cy={toY(point.best_fitness)}
              r="4"
              className="chart-dot-primary"
            />
            <circle
              cx={toX(point.iteration)}
              cy={toY(point.best_test_accuracy)}
              r="3"
              className="chart-dot-secondary"
            />
          </g>
        ))}
      </svg>
      <div className="chart-legend">
        <span>
          <i className="legend-swatch legend-primary" />
          Best train fitness
        </span>
        <span>
          <i className="legend-swatch legend-secondary" />
          Best test accuracy
        </span>
      </div>
    </div>
  );
}

function AgentCard({ entry, selected, onSelect }) {
  const { agent, evaluation } = entry;
  return (
    <button
      type="button"
      className={`agent-card ${selected ? "selected" : ""}`}
      onClick={() => onSelect(agent.agent_id)}
    >
      <div className="agent-card-top">
        <strong>{agent.agent_id}</strong>
        <span>{formatPercent(evaluation.train_accuracy)} train</span>
      </div>
      <div className="agent-card-meta">
        <span>gen {agent.generation}</span>
        <span>{agent.task_policy.review_style}</span>
      </div>
      <p>{evaluation.summary}</p>
    </button>
  );
}

function ProviderBadge({ provider }) {
  const statusClass = provider.client_ready ? "provider-live" : "provider-fallback";

  return (
    <div className={`provider-badge ${statusClass}`}>
      <strong>{provider.client_ready ? "OpenAI live" : "Heuristic fallback"}</strong>
      <span>{provider.model || "no model configured"}</span>
      <p>{provider.reason}</p>
      {provider.last_error ? <p className="provider-error">{provider.last_error}</p> : null}
    </div>
  );
}

function App() {
  const [state, setState] = useState(null);
  const [iterations, setIterations] = useState(5);
  const [error, setError] = useState("");
  const [isBusy, setIsBusy] = useState(false);
  const [selectedAgentId, setSelectedAgentId] = useState("");
  const [mode, setMode] = useState("hyperagent");
  const [repoUrl, setRepoUrl] = useState("");
  const [reviewResult, setReviewResult] = useState(null);
  const [reviewBusy, setReviewBusy] = useState(false);

  useEffect(() => {
    loadState();
  }, []);

  async function loadState() {
    setIsBusy(true);
    setError("");
    try {
      const nextState = await fetchState();
      startTransition(() => {
        setState(nextState);
        setSelectedAgentId((current) => current || nextState.best_agent.agent.agent_id);
      });
    } catch (loadError) {
      setError(loadError.message);
    } finally {
      setIsBusy(false);
    }
  }

  async function handleRun() {
    setIsBusy(true);
    setError("");
    try {
      const nextState = await runIterations(Number(iterations));
      startTransition(() => {
        setState(nextState);
        setSelectedAgentId(nextState.best_agent.agent.agent_id);
      });
    } catch (runError) {
      setError(runError.message);
    } finally {
      setIsBusy(false);
    }
  }

  async function handleReset() {
    setIsBusy(true);
    setError("");
    try {
      const nextState = await resetState(mode);
      startTransition(() => {
        setState(nextState);
        setSelectedAgentId(nextState.best_agent.agent.agent_id);
        setReviewResult(null);
      });
    } catch (resetError) {
      setError(resetError.message);
    } finally {
      setIsBusy(false);
    }
  }

  async function handleExportCsv() {
    try {
      const csv = await fetchMetricsCsv();
      const blob = new Blob([csv], { type: "text/csv" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `hyperagents-metrics-${state?.mode ?? "run"}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (exportError) {
      setError(exportError.message);
    }
  }

  async function handleReview() {
    setReviewBusy(true);
    setError("");
    try {
      const result = await reviewRepository(repoUrl);
      startTransition(() => {
        setReviewResult(result);
      });
    } catch (reviewError) {
      setError(reviewError.message);
    } finally {
      setReviewBusy(false);
    }
  }

  if (!state) {
    return (
      <main className="app-shell">
        <section className="hero">
          <h1>hyperagents</h1>
          <p>{error || "Loading backend state..."}</p>
        </section>
      </main>
    );
  }

  const archive = [...state.archive].sort(
    (left, right) => right.evaluation.fitness - left.evaluation.fitness,
  );
  const selectedEntry =
    archive.find((entry) => entry.agent.agent_id === selectedAgentId) ?? state.best_agent;

  return (
    <main className="app-shell">
      <section className="hero">
        <div>
          <p className="eyebrow">HyperAgents-Inspired Framework</p>
          <h1>hyperagents</h1>
          <p className="hero-copy">
            Self-improving agents that review GitHub repositories. Each agent evolves its own
            code-quality weights and decision threshold, storing every variant in an archive of
            stepping stones.
          </p>
          <ProviderBadge provider={state.provider} />
        </div>
        <div className="hero-panel">
          <label htmlFor="iterations">Iterations</label>
          <input
            id="iterations"
            type="number"
            min="1"
            max="100"
            value={iterations}
            onChange={(event) => setIterations(event.target.value)}
          />
          <fieldset className="mode-fieldset">
            <legend className="detail-label">Mode</legend>
            <label className="mode-option">
              <input
                type="radio"
                name="mode"
                value="hyperagent"
                checked={mode === "hyperagent"}
                onChange={() => setMode("hyperagent")}
              />
              HyperAgent <span className="mode-hint">(meta policy self-improves)</span>
            </label>
            <label className="mode-option">
              <input
                type="radio"
                name="mode"
                value="baseline"
                checked={mode === "baseline"}
                onChange={() => setMode("baseline")}
              />
              Baseline <span className="mode-hint">(meta policy frozen at seed)</span>
            </label>
          </fieldset>
          <div className="hero-actions">
            <button type="button" onClick={handleRun} disabled={isBusy}>
              {isBusy ? "Running..." : "Run Iterations"}
            </button>
            <button type="button" className="secondary" onClick={handleReset} disabled={isBusy}>
              Reset ({mode})
            </button>
            <button type="button" className="secondary" onClick={handleExportCsv} disabled={isBusy}>
              Export CSV
            </button>
          </div>
          {state.mode ? (
            <p className="detail-label">
              Active mode: <strong>{state.mode}</strong>
            </p>
          ) : null}
          {error ? <p className="error-text">{error}</p> : null}
        </div>
      </section>

      <section className="detail-section">
        <div className="panel-header">
          <h3>Live Repo Review</h3>
          <p>Paste a public GitHub URL. Fetches the repo and uses OpenAI to review it.</p>
        </div>
        <div className="detail-layout review-layout">
          <article className="detail-panel">
            <h4>Repository Input</h4>
            <label htmlFor="repo-url" className="detail-label">
              GitHub URL
            </label>
            <input
              id="repo-url"
              value={repoUrl}
              onChange={(event) => setRepoUrl(event.target.value)}
              placeholder="https://github.com/owner/repo"
            />
            <div className="hero-actions">
              <button
                type="button"
                onClick={handleReview}
                disabled={
                  reviewBusy ||
                  !state.provider.client_ready ||
                  repoUrl.trim().length < 10
                }
              >
                {reviewBusy ? "Reviewing..." : "Review Repository"}
              </button>
            </div>
          </article>
          <article className="detail-panel">
            <h4>Review Output</h4>
            {reviewResult ? (
              <div className="review-result">
                <div className="policy-grid">
                  <div>
                    <span className="detail-label">Recommendation</span>
                    <strong>{reviewResult.recommendation}</strong>
                  </div>
                  <div>
                    <span className="detail-label">Score</span>
                    <strong>{reviewResult.score}</strong>
                  </div>
                </div>
                <p className="summary-text">{reviewResult.summary}</p>
                <div className="review-columns">
                  <div>
                    <span className="detail-label">Strengths</span>
                    {(reviewResult.strengths ?? []).map((item) => (
                      <p key={item} className="summary-text">
                        {item}
                      </p>
                    ))}
                  </div>
                  <div>
                    <span className="detail-label">Issues</span>
                    {(reviewResult.issues ?? []).map((item) => (
                      <p key={item} className="summary-text">
                        {item}
                      </p>
                    ))}
                  </div>
                </div>
              </div>
            ) : (
              <p className="summary-text">
                Enter a GitHub URL and click Review Repository.
              </p>
            )}
          </article>
        </div>
      </section>

      <section className="stats-grid">
        <article className="stat-card">
          <span>Iterations</span>
          <strong>{state.iterations_completed}</strong>
        </article>
        <article className="stat-card">
          <span>Archive size</span>
          <strong>{state.archive.length}</strong>
        </article>
        <article className="stat-card">
          <span>Best train fitness</span>
          <strong>{formatPercent(state.best_agent.evaluation.fitness)}</strong>
        </article>
        <article className="stat-card">
          <span>Best test accuracy</span>
          <strong>{formatPercent(state.best_agent.evaluation.test_accuracy)}</strong>
        </article>
      </section>

      <section className="main-grid">
        <ProgressChart points={state.progress} />

        <div className="best-agent">
          <div className="panel-header">
            <h3>Best Agent</h3>
            <p>{state.best_agent.agent.agent_id}</p>
          </div>
          <div className="detail-grid">
            <div>
              <span className="detail-label">Parent</span>
              <strong>{state.best_agent.agent.parent_id ?? "seed"}</strong>
            </div>
            <div>
              <span className="detail-label">Generation</span>
              <strong>{state.best_agent.agent.generation}</strong>
            </div>
            <div>
              <span className="detail-label">Review style</span>
              <strong>{state.best_agent.agent.task_policy.review_style}</strong>
            </div>
            <div>
              <span className="detail-label">Focus metric</span>
              <strong>{state.best_agent.agent.meta_policy.focus_metric}</strong>
            </div>
          </div>
          <p className="summary-text">{state.best_agent.evaluation.summary}</p>
        </div>
      </section>

      <section className="archive-section">
        <div className="panel-header">
          <h3>Archive</h3>
          <p>Each card is a hyperagent containing both task and meta policy.</p>
        </div>
        <div className="archive-grid">
          {archive.map((entry) => (
            <AgentCard
              key={entry.agent.agent_id}
              entry={entry}
              selected={entry.agent.agent_id === selectedEntry.agent.agent_id}
              onSelect={setSelectedAgentId}
            />
          ))}
        </div>
      </section>

      <section className="detail-section">
        <div className="panel-header">
          <h3>Selected Agent</h3>
          <p>{selectedEntry.agent.agent_id}</p>
        </div>

        <div className="detail-layout">
          <article className="detail-panel">
            <h4>Task Policy</h4>
            <div className="policy-grid">
              {Object.entries(selectedEntry.agent.task_policy.weights).map(([feature, value]) => (
                <div key={feature}>
                  <span className="detail-label">{feature}</span>
                  <strong>{formatNumber(value)}</strong>
                </div>
              ))}
              <div>
                <span className="detail-label">threshold</span>
                <strong>{formatNumber(selectedEntry.agent.task_policy.threshold)}</strong>
              </div>
              <div>
                <span className="detail-label">style</span>
                <strong>{selectedEntry.agent.task_policy.review_style}</strong>
              </div>
            </div>
          </article>

          <article className="detail-panel">
            <h4>Meta Policy</h4>
            <div className="policy-grid">
              <div>
                <span className="detail-label">focus metric</span>
                <strong>{selectedEntry.agent.meta_policy.focus_metric}</strong>
              </div>
              <div>
                <span className="detail-label">weight step</span>
                <strong>{formatNumber(selectedEntry.agent.meta_policy.weight_step)}</strong>
              </div>
              <div>
                <span className="detail-label">threshold step</span>
                <strong>{formatNumber(selectedEntry.agent.meta_policy.threshold_step)}</strong>
              </div>
              <div>
                <span className="detail-label">exploration</span>
                <strong>{formatNumber(selectedEntry.agent.meta_policy.exploration_scale)}</strong>
              </div>
            </div>
            <div className="memory-list">
              {selectedEntry.agent.meta_policy.memory.map((note) => (
                <p key={note}>{note}</p>
              ))}
            </div>
          </article>

          <article className="detail-panel">
            <h4>Evaluation</h4>
            <div className="policy-grid">
              <div>
                <span className="detail-label">train accuracy</span>
                <strong>{formatPercent(selectedEntry.evaluation.train_accuracy)}</strong>
              </div>
              <div>
                <span className="detail-label">test accuracy</span>
                <strong>{formatPercent(selectedEntry.evaluation.test_accuracy)}</strong>
              </div>
              <div>
                <span className="detail-label">false positives</span>
                <strong>{selectedEntry.evaluation.false_positive_count}</strong>
              </div>
              <div>
                <span className="detail-label">false negatives</span>
                <strong>{selectedEntry.evaluation.false_negative_count}</strong>
              </div>
            </div>
            <p className="summary-text">{selectedEntry.evaluation.summary}</p>
          </article>
        </div>
      </section>

      <section className="events-section">
        <div className="panel-header">
          <h3>Recent Events</h3>
          <p>Parent-child mutations from the latest iterations.</p>
        </div>
        <div className="events-grid">
          {state.recent_events.map((event) => (
            <article className="event-card" key={`${event.iteration}-${event.child_id}`}>
              <span className="event-iteration">iter {event.iteration}</span>
              <strong>
                {event.parent_id} → {event.child_id}
              </strong>
              <span className={event.fitness_delta >= 0 ? "delta-positive" : "delta-negative"}>
                Δ {formatNumber(event.fitness_delta)}
              </span>
              <p>{event.summary}</p>
            </article>
          ))}
        </div>
      </section>
    </main>
  );
}

export default App;
