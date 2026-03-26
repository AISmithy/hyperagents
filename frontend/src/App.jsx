import { startTransition, useEffect, useState } from "react";
import { addAccount, applyAllAccounts, deleteAccount, deleteRun, fetchAccountRepos, fetchAccounts, fetchMetricsCsv, fetchRuns, fetchState, loadRun, resetState, reviewRepository, runIterations } from "./api";

function formatPercent(value) {
  return `${Math.round(value * 100)}%`;
}

function formatNumber(value) {
  return Number(value).toFixed(3);
}

// ── Progress chart ────────────────────────────────────────────────────────────

function ProgressChart({ points }) {
  if (!points.length) return null;

  const width = 560;
  const height = 220;
  const pad = 18;
  const maxX = Math.max(...points.map((p) => p.iteration), 1);
  const toX = (v) => pad + (v / maxX) * Math.max(width - pad * 2, 1);
  const toY = (v) => height - pad - v * Math.max(height - pad * 2, 1);

  const line = points.map((p) => `${toX(p.iteration)},${toY(p.best_fitness)}`).join(" ");
  const testLine = points.map((p) => `${toX(p.iteration)},${toY(p.best_test_accuracy)}`).join(" ");

  return (
    <div className="chart-shell">
      <div className="chart-header">
        <h3>Progress</h3>
        <p>Best train fitness and test accuracy over iterations.</p>
      </div>
      <svg viewBox={`0 0 ${width} ${height}`} className="chart">
        <rect x="0" y="0" width={width} height={height} rx="18" className="chart-bg" />
        {[0.25, 0.5, 0.75].map((tick) => (
          <line key={tick} x1={pad} x2={width - pad} y1={toY(tick)} y2={toY(tick)} className="chart-grid" />
        ))}
        <polyline fill="none" strokeWidth="4" points={line} className="chart-line-primary" />
        <polyline fill="none" strokeWidth="3" points={testLine} className="chart-line-secondary" />
        {points.map((p) => (
          <g key={p.iteration}>
            <circle cx={toX(p.iteration)} cy={toY(p.best_fitness)} r="4" className="chart-dot-primary" />
            <circle cx={toX(p.iteration)} cy={toY(p.best_test_accuracy)} r="3" className="chart-dot-secondary" />
          </g>
        ))}
      </svg>
      <div className="chart-legend">
        <span><i className="legend-swatch legend-primary" />Best train fitness</span>
        <span><i className="legend-swatch legend-secondary" />Best test accuracy</span>
      </div>
    </div>
  );
}

// ── Compact archive row ───────────────────────────────────────────────────────

function AgentRow({ entry, selected, onSelect }) {
  const { agent, evaluation } = entry;
  return (
    <button
      type="button"
      className={`agent-row ${selected ? "selected" : ""}`}
      onClick={() => onSelect(agent.agent_id)}
    >
      <span className="agent-row-id">{agent.agent_id}</span>
      <span className="agent-row-cell muted">gen {agent.generation}</span>
      <span className="agent-row-cell">{agent.task_policy.review_style}</span>
      <span className="agent-row-cell score">{formatPercent(evaluation.train_accuracy)}</span>
      <span className="agent-row-cell score">{formatPercent(evaluation.test_accuracy)}</span>
      <span className="agent-row-cell muted">{agent.meta_policy.focus_metric}</span>
      <span className="agent-row-fp">{evaluation.false_positive_count} fp / {evaluation.false_negative_count} fn</span>
    </button>
  );
}

// ── Provider badge ────────────────────────────────────────────────────────────

function ProviderBadge({ provider }) {
  return (
    <div className={`provider-badge ${provider.client_ready ? "provider-live" : "provider-fallback"}`}>
      <strong>{provider.client_ready ? "OpenAI live" : "Heuristic fallback"}</strong>
      <span>{provider.model || "no model configured"}</span>
      <p>{provider.reason}</p>
      {provider.last_error && <p className="provider-error">{provider.last_error}</p>}
    </div>
  );
}

// ── Tab nav ───────────────────────────────────────────────────────────────────

const TABS = [
  { id: "overview",  label: "Overview" },
  { id: "accounts",  label: "Accounts" },
  { id: "archive",   label: "Archive" },
  { id: "detail",    label: "Agent Detail" },
  { id: "events",    label: "Events" },
  { id: "runs",      label: "Runs" },
  { id: "review",    label: "Live Review" },
];

function TabNav({ active, onChange, archiveCount, accountCount }) {
  return (
    <nav className="tab-nav">
      {TABS.map((tab) => (
        <button
          key={tab.id}
          type="button"
          className={`tab-btn ${active === tab.id ? "active" : ""}`}
          onClick={() => onChange(tab.id)}
        >
          {tab.label}
          {tab.id === "archive" && archiveCount > 0 && (
            <span className="tab-badge">{archiveCount}</span>
          )}
          {tab.id === "accounts" && accountCount > 0 && (
            <span className="tab-badge">{accountCount}</span>
          )}
        </button>
      ))}
    </nav>
  );
}

// ── Feature bar ───────────────────────────────────────────────────────────────

function FeatureBar({ value }) {
  const pct = Math.round(value * 100);
  const color = pct >= 70 ? "#1a7d79" : pct >= 45 ? "#b8582f" : "#c0392b";
  return (
    <span className="feature-bar-wrap" title={`${pct}%`}>
      <span className="feature-bar-track">
        <span className="feature-bar-fill" style={{ width: `${pct}%`, background: color }} />
      </span>
      <span className="feature-bar-label">{pct}</span>
    </span>
  );
}

const PROFILES = ["premium", "startup", "legacy", "academic", "security_focused", "mixed"];

// ── App ───────────────────────────────────────────────────────────────────────

function App() {
  const [state, setState] = useState(null);
  const [iterations, setIterations] = useState(5);
  const [error, setError] = useState("");
  const [isBusy, setIsBusy] = useState(false);
  const [selectedAgentId, setSelectedAgentId] = useState("");
  const [mode, setMode] = useState("hyperagent");
  const [activeTab, setActiveTab] = useState("overview");
  const [runs, setRuns] = useState([]);
  const [repoUrl, setRepoUrl] = useState("");
  const [reviewResult, setReviewResult] = useState(null);
  const [reviewBusy, setReviewBusy] = useState(false);

  // accounts
  const [accounts, setAccounts] = useState([]);
  const [accountForm, setAccountForm] = useState({ name: "", platform: "synthetic", profile: "mixed", n_repos: 10 });
  const [accountsBusy, setAccountsBusy] = useState(false);
  const [expandedAccountId, setExpandedAccountId] = useState(null);
  const [accountReposMap, setAccountReposMap] = useState({});

  useEffect(() => {
    loadState();
    fetchRuns().then(setRuns).catch(() => {});
    fetchAccounts().then(setAccounts).catch(() => {});
  }, []);

  async function loadState() {
    setIsBusy(true);
    setError("");
    try {
      const next = await fetchState();
      startTransition(() => {
        setState(next);
        setSelectedAgentId((cur) => cur || next.best_agent.agent.agent_id);
      });
    } catch (e) { setError(e.message); }
    finally { setIsBusy(false); }
  }

  async function handleRun() {
    setIsBusy(true);
    setError("");
    try {
      const next = await runIterations(Number(iterations));
      const updatedRuns = await fetchRuns();
      startTransition(() => {
        setState(next);
        setSelectedAgentId(next.best_agent.agent.agent_id);
        setRuns(updatedRuns);
      });
    } catch (e) { setError(e.message); }
    finally { setIsBusy(false); }
  }

  async function handleReset() {
    setIsBusy(true);
    setError("");
    try {
      const next = await resetState(mode);
      const updatedRuns = await fetchRuns();
      startTransition(() => {
        setState(next);
        setSelectedAgentId(next.best_agent.agent.agent_id);
        setRuns(updatedRuns);
        setReviewResult(null);
        setActiveTab("overview");
      });
    } catch (e) { setError(e.message); }
    finally { setIsBusy(false); }
  }

  async function handleLoadRun(runId) {
    setIsBusy(true);
    setError("");
    try {
      const next = await loadRun(runId);
      startTransition(() => {
        setState(next);
        setSelectedAgentId(next.best_agent.agent.agent_id);
        setMode(next.mode);
        setActiveTab("overview");
      });
    } catch (e) { setError(e.message); }
    finally { setIsBusy(false); }
  }

  async function handleDeleteRun(runId) {
    try {
      await deleteRun(runId);
      setRuns((prev) => prev.filter((r) => r.run_id !== runId));
    } catch (e) { setError(e.message); }
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
    } catch (e) { setError(e.message); }
  }

  async function handleAddAccount() {
    if (!accountForm.name.trim()) return;
    setAccountsBusy(true);
    setError("");
    try {
      const result = await addAccount(accountForm.name.trim(), accountForm.platform, accountForm.profile, Number(accountForm.n_repos));
      setAccounts((prev) => [result, ...prev]);
      setAccountReposMap((prev) => ({ ...prev, [result.id]: result.repos }));
      setExpandedAccountId(result.id);
      setAccountForm((prev) => ({ ...prev, name: "" }));
    } catch (e) { setError(e.message); }
    finally { setAccountsBusy(false); }
  }

  async function handleDeleteAccount(id) {
    try {
      await deleteAccount(id);
      setAccounts((prev) => prev.filter((a) => a.id !== id));
      setAccountReposMap((prev) => { const n = { ...prev }; delete n[id]; return n; });
      if (expandedAccountId === id) setExpandedAccountId(null);
    } catch (e) { setError(e.message); }
  }

  async function handleToggleRepos(id) {
    if (expandedAccountId === id) { setExpandedAccountId(null); return; }
    if (!accountReposMap[id]) {
      try {
        const repos = await fetchAccountRepos(id);
        setAccountReposMap((prev) => ({ ...prev, [id]: repos }));
      } catch (e) { setError(e.message); return; }
    }
    setExpandedAccountId(id);
  }

  async function handleApplyAll() {
    setAccountsBusy(true);
    setError("");
    try {
      const next = await applyAllAccounts();
      startTransition(() => setState(next));
    } catch (e) { setError(e.message); }
    finally { setAccountsBusy(false); }
  }

  async function handleReview() {
    setReviewBusy(true);
    setError("");
    try {
      const result = await reviewRepository(repoUrl);
      startTransition(() => setReviewResult(result));
    } catch (e) { setError(e.message); }
    finally { setReviewBusy(false); }
  }

  function handleSelectAgent(agentId) {
    setSelectedAgentId(agentId);
    setActiveTab("detail");
  }

  if (!state) {
    return (
      <main className="app-shell">
        <section className="hero">
          <h1>hyperagents</h1>
          <p>{error || "Loading backend state…"}</p>
        </section>
      </main>
    );
  }

  const archive = [...state.archive].sort((a, b) => b.evaluation.fitness - a.evaluation.fitness);
  const selectedEntry = archive.find((e) => e.agent.agent_id === selectedAgentId) ?? state.best_agent;

  return (
    <main className="app-shell">

      {/* ── Always-visible header ── */}
      <section className="hero">
        <div>
          <p className="eyebrow">HyperAgents-Inspired Framework</p>
          <h1>hyperagents</h1>
          <p className="hero-copy">
            Self-improving agents that evolve task and meta policies, storing every
            variant in an archive of stepping stones.
          </p>
          <ProviderBadge provider={state.provider} />
        </div>
        <div className="hero-panel">
          <div className="hero-inline-row">
            <div className="hero-inline-field">
              <label htmlFor="iterations">Iterations</label>
              <input
                id="iterations"
                type="number"
                min="1"
                max="100"
                value={iterations}
                onChange={(e) => setIterations(e.target.value)}
              />
            </div>
            <fieldset className="mode-fieldset">
              <legend className="detail-label">Mode</legend>
              <label className="mode-option">
                <input type="radio" name="mode" value="hyperagent"
                  checked={mode === "hyperagent"} onChange={() => setMode("hyperagent")} />
                HyperAgent <span className="mode-hint">(meta self-improves)</span>
              </label>
              <label className="mode-option">
                <input type="radio" name="mode" value="baseline"
                  checked={mode === "baseline"} onChange={() => setMode("baseline")} />
                Baseline <span className="mode-hint">(meta frozen)</span>
              </label>
            <label className="mode-option">
                <input type="radio" name="mode" value="no_archive"
                  checked={mode === "no_archive"} onChange={() => setMode("no_archive")} />
                No Archive <span className="mode-hint">(greedy, no stepping stones)</span>
              </label>
            </fieldset>
          </div>
          <div className="hero-actions">
            <button type="button" onClick={handleRun} disabled={isBusy}>
              {isBusy ? "Running…" : "Run Iterations"}
            </button>
            <button type="button" className="secondary" onClick={handleReset} disabled={isBusy}>
              Reset ({mode})
            </button>
            <button type="button" className="secondary" onClick={handleExportCsv} disabled={isBusy}>
              Export CSV
            </button>
          </div>
          {state.mode && <p className="detail-label">Active mode: <strong>{state.mode}</strong></p>}
          {error && <p className="error-text">{error}</p>}
        </div>
      </section>

      {/* ── Compact stats bar ── */}
      <div className="stats-bar">
        <div className="stats-bar-item">
          <span>Iterations</span>
          <strong>{state.iterations_completed}</strong>
        </div>
        <div className="stats-bar-item">
          <span>Archive</span>
          <strong>{state.archive.length}</strong>
        </div>
        <div className="stats-bar-item">
          <span>Train repos</span>
          <strong>
            {state.dataset?.train_size ?? "—"}
            {state.dataset?.extra_train_size > 0 && (
              <span className="dataset-extra"> (+{state.dataset.extra_train_size})</span>
            )}
          </strong>
        </div>
        <div className="stats-bar-item">
          <span>Best train</span>
          <strong>{formatPercent(state.best_agent.evaluation.fitness)}</strong>
        </div>
        <div className="stats-bar-item">
          <span>Best test</span>
          <strong>{formatPercent(state.best_agent.evaluation.test_accuracy)}</strong>
        </div>
        <div className="stats-bar-item">
          <span>Best agent</span>
          <strong>{state.best_agent.agent.agent_id}</strong>
        </div>
      </div>

      {/* ── Tab navigation (sticky) ── */}
      <TabNav active={activeTab} onChange={setActiveTab} archiveCount={archive.length} accountCount={accounts.length} />

      {/* ── Tab: Overview ── */}
      {activeTab === "overview" && (
        <div className="tab-content">
          <div className="main-grid">
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
          </div>
        </div>
      )}

      {/* ── Tab: Accounts ── */}
      {activeTab === "accounts" && (
        <div className="tab-content">
          <div className="panel-header">
            <h3>Accounts</h3>
            <p>Add GitHub accounts or synthetic orgs. Each account generates repos with feature scores that extend the agent's training dataset.</p>
          </div>

          {/* Add account form */}
          <article className="detail-panel accounts-form">
            <h4>Add Account</h4>
            <div className="accounts-form-row">
              <div className="accounts-form-field">
                <label className="detail-label" htmlFor="acc-name">Account name</label>
                <input
                  id="acc-name"
                  value={accountForm.name}
                  onChange={(e) => setAccountForm((p) => ({ ...p, name: e.target.value }))}
                  placeholder="e.g. acme-corp or torvalds"
                  onKeyDown={(e) => e.key === "Enter" && handleAddAccount()}
                />
              </div>
              <fieldset className="mode-fieldset">
                <legend className="detail-label">Platform</legend>
                <label className="mode-option">
                  <input type="radio" name="acc-platform" value="synthetic"
                    checked={accountForm.platform === "synthetic"}
                    onChange={() => setAccountForm((p) => ({ ...p, platform: "synthetic" }))} />
                  Synthetic <span className="mode-hint">(instant, deterministic)</span>
                </label>
                <label className="mode-option">
                  <input type="radio" name="acc-platform" value="github"
                    checked={accountForm.platform === "github"}
                    onChange={() => setAccountForm((p) => ({ ...p, platform: "github" }))} />
                  GitHub <span className="mode-hint">(requires public API access)</span>
                </label>
              </fieldset>
              {accountForm.platform === "synthetic" && (
                <div className="accounts-form-field">
                  <label className="detail-label" htmlFor="acc-profile">Quality profile</label>
                  <select
                    id="acc-profile"
                    value={accountForm.profile}
                    onChange={(e) => setAccountForm((p) => ({ ...p, profile: e.target.value }))}
                  >
                    {PROFILES.map((p) => <option key={p} value={p}>{p}</option>)}
                  </select>
                </div>
              )}
              <div className="accounts-form-field">
                <label className="detail-label" htmlFor="acc-nrepos">Repos to scan</label>
                <input
                  id="acc-nrepos"
                  type="number"
                  min="1"
                  max="50"
                  value={accountForm.n_repos}
                  onChange={(e) => setAccountForm((p) => ({ ...p, n_repos: e.target.value }))}
                />
              </div>
            </div>
            <div className="hero-actions" style={{ marginTop: "0.85rem" }}>
              <button type="button" onClick={handleAddAccount} disabled={accountsBusy || !accountForm.name.trim()}>
                {accountsBusy ? "Scanning…" : "Add & Scan"}
              </button>
              {accounts.length > 0 && (
                <button type="button" className="secondary" onClick={handleApplyAll} disabled={accountsBusy}>
                  Apply All to Dataset
                </button>
              )}
            </div>
            {accounts.length > 0 && (
              <p className="summary-text" style={{ marginTop: "0.5rem" }}>
                "Apply All to Dataset" pushes all account repos into the engine (80% train / 20% test).
                Then Reset to re-initialise the loop with the expanded dataset.
              </p>
            )}
          </article>

          {/* Account list */}
          {accounts.length === 0 ? (
            <p className="summary-text">No accounts added yet.</p>
          ) : (
            <div className="accounts-list">
              {accounts.map((account) => (
                <article key={account.id} className="account-card">
                  <div className="account-card-header">
                    <div className="account-card-meta">
                      <strong>{account.name}</strong>
                      <span className={`runs-mode ${account.platform}`}>{account.platform}</span>
                      {account.profile && account.profile !== "inferred" && (
                        <span className="muted">{account.profile}</span>
                      )}
                      <span className="muted">{account.repo_count} repos</span>
                    </div>
                    <div className="account-card-actions">
                      <button type="button" className="runs-btn"
                        onClick={() => handleToggleRepos(account.id)}>
                        {expandedAccountId === account.id ? "Hide" : "View Repos"}
                      </button>
                      <button type="button" className="runs-btn danger"
                        onClick={() => handleDeleteAccount(account.id)}>
                        Delete
                      </button>
                    </div>
                  </div>

                  {expandedAccountId === account.id && accountReposMap[account.id] && (
                    <div className="repos-table">
                      <div className="repos-table-header">
                        <span>Name</span>
                        <span>Maint.</span>
                        <span>Security</span>
                        <span>Tests</span>
                        <span>Docs</span>
                        <span>Simplicity</span>
                        <span>Label</span>
                      </div>
                      {accountReposMap[account.id].map((repo) => (
                        <div key={repo.id ?? repo.name} className="repos-row">
                          <span className="muted" title={repo.name}>{repo.name}</span>
                          <FeatureBar value={repo.maintainability} />
                          <FeatureBar value={repo.security} />
                          <FeatureBar value={repo.test_coverage} />
                          <FeatureBar value={repo.documentation} />
                          <FeatureBar value={repo.simplicity} />
                          <span className={repo.label === 1 ? "label-accept" : "label-reject"}>
                            {repo.label === 1 ? "accept" : "reject"}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </article>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ── Tab: Archive ── */}
      {activeTab === "archive" && (
        <div className="tab-content">
          <div className="panel-header">
            <h3>Archive</h3>
            <p>Click a row to inspect the agent in detail.</p>
          </div>
          <div className="agent-table">
            <div className="agent-table-header">
              <span>ID</span>
              <span>Gen</span>
              <span>Style</span>
              <span>Train</span>
              <span>Test</span>
              <span>Focus</span>
              <span>Errors</span>
            </div>
            {archive.map((entry) => (
              <AgentRow
                key={entry.agent.agent_id}
                entry={entry}
                selected={entry.agent.agent_id === selectedEntry.agent.agent_id}
                onSelect={handleSelectAgent}
              />
            ))}
          </div>
        </div>
      )}

      {/* ── Tab: Agent Detail ── */}
      {activeTab === "detail" && (
        <div className="tab-content">
          <div className="panel-header">
            <h3>Selected Agent</h3>
            <p>{selectedEntry.agent.agent_id} — gen {selectedEntry.agent.generation}</p>
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
        </div>
      )}

      {/* ── Tab: Events ── */}
      {activeTab === "events" && (
        <div className="tab-content">
          <div className="panel-header">
            <h3>Recent Events</h3>
            <p>Parent-child mutations from the latest iterations.</p>
          </div>
          <div className="events-grid">
            {state.recent_events.map((event) => (
              <article className="event-card" key={`${event.iteration}-${event.child_id}`}>
                <span className="event-iteration">iter {event.iteration}</span>
                <strong>{event.parent_id} → {event.child_id}</strong>
                <span className={event.fitness_delta >= 0 ? "delta-positive" : "delta-negative"}>
                  Δ {formatNumber(event.fitness_delta)}
                </span>
                <p>{event.summary}</p>
              </article>
            ))}
          </div>
        </div>
      )}

      {/* ── Tab: Runs ── */}
      {activeTab === "runs" && (
        <div className="tab-content">
          <div className="panel-header">
            <h3>Saved Runs</h3>
            <p>Every reset creates a new run. Load one to restore its state and continue iterating.</p>
          </div>
          {runs.length === 0 ? (
            <p className="summary-text">No runs saved yet. Run some iterations first.</p>
          ) : (
            <div className="runs-table">
              <div className="runs-table-header">
                <span>ID</span>
                <span>UUID</span>
                <span>Mode</span>
                <span>Created</span>
                <span>Iterations</span>
                <span>Best Train</span>
                <span>Best Test</span>
                <span></span>
              </div>
              {runs.map((run) => (
                <div
                  key={run.run_id}
                  className={`runs-row ${state?.run_id === run.run_id ? "active-run" : ""}`}
                >
                  <span className="runs-id">#{run.run_id}</span>
                  <span className="runs-uuid muted">{run.run_uuid}</span>
                  <span className={`runs-mode ${run.mode}`}>{run.mode}</span>
                  <span className="muted">{run.created_at.replace("T", " ").replace("+00:00", "")}</span>
                  <span>{run.iterations_completed}</span>
                  <span className="score">{formatPercent(run.best_fitness)}</span>
                  <span className="score">{formatPercent(run.best_test_accuracy)}</span>
                  <span className="runs-actions">
                    <button
                      type="button"
                      className="runs-btn"
                      onClick={() => handleLoadRun(run.run_id)}
                      disabled={isBusy}
                    >
                      Load
                    </button>
                    <button
                      type="button"
                      className="runs-btn danger"
                      onClick={() => handleDeleteRun(run.run_id)}
                      disabled={isBusy || state?.run_id === run.run_id}
                    >
                      Delete
                    </button>
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ── Tab: Live Review ── */}
      {activeTab === "review" && (
        <div className="tab-content">
          <div className="panel-header">
            <h3>Live Repo Review</h3>
            <p>Paste a public GitHub URL. Fetches the repo and uses OpenAI to review it.</p>
          </div>
          <div className="detail-layout review-layout">
            <article className="detail-panel">
              <h4>Repository Input</h4>
              <label htmlFor="repo-url" className="detail-label">GitHub URL</label>
              <input
                id="repo-url"
                value={repoUrl}
                onChange={(e) => setRepoUrl(e.target.value)}
                placeholder="https://github.com/owner/repo"
              />
              <div className="hero-actions" style={{ marginTop: "0.85rem" }}>
                <button
                  type="button"
                  onClick={handleReview}
                  disabled={reviewBusy || !state.provider.client_ready || repoUrl.trim().length < 10}
                >
                  {reviewBusy ? "Reviewing…" : "Review Repository"}
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
                        <p key={item} className="summary-text">{item}</p>
                      ))}
                    </div>
                    <div>
                      <span className="detail-label">Issues</span>
                      {(reviewResult.issues ?? []).map((item) => (
                        <p key={item} className="summary-text">{item}</p>
                      ))}
                    </div>
                  </div>
                </div>
              ) : (
                <p className="summary-text">Enter a GitHub URL and click Review Repository.</p>
              )}
            </article>
          </div>
        </div>
      )}

    </main>
  );
}

export default App;
