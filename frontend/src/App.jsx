import { useEffect, useState, useCallback } from "react";

const get = (url) => fetch(url).then((r) => r.json());

function Incident({ inc, onResolve }) {
  return (
    <div className={`card ${inc.status}`}>
      <div className="row">
        <h3>#{inc.id} · {inc.service}</h3>
        <span className={`badge ${inc.status}`}>{inc.status}</span>
      </div>
      <small>{new Date(inc.detected_at + "Z").toLocaleString()} · {inc.error_count} errors</small>
      <p>{inc.summary}</p>
      <h4>Top error patterns</h4>
      <ul>{inc.top_patterns.map((p) => <li key={p.pattern}><code>{p.pattern}</code> × {p.count}</li>)}</ul>
      <h4>Suspect deployments</h4>
      {inc.suspects.length === 0 && <p className="muted">None in window.</p>}
      {inc.suspects.map((s) => (
        <div key={s.deployment.id} className="suspect">
          <strong>{s.deployment.version}</strong> <code>{s.deployment.commit_sha.slice(0, 7)}</code>
          <span className="score">score {s.score}</span>
          <ul>{s.reasons.map((r) => <li key={r}>{r}</li>)}</ul>
        </div>
      ))}
      {inc.status === "open" && <button onClick={() => onResolve(inc.id)}>Mark resolved</button>}
    </div>
  );
}

export default function App() {
  const [incidents, setIncidents] = useState([]);
  const [deployments, setDeployments] = useState([]);
  const [logs, setLogs] = useState([]);

  const load = useCallback(async () => {
    const [i, d, l] = await Promise.all([
      get("/api/incidents"), get("/api/deployments"), get("/api/logs?level=ERROR&limit=20"),
    ]);
    setIncidents(i); setDeployments(d); setLogs(l);
  }, []);

  useEffect(() => { load(); const t = setInterval(load, 5000); return () => clearInterval(t); }, [load]);

  const resolve = async (id) => { await fetch(`/api/incidents/${id}/resolve`, { method: "POST" }); load(); };

  return (
    <main>
      <header><h1>🛡️ DeployGuard</h1><span className="muted">{incidents.filter((i) => i.status === "open").length} open incidents</span></header>
      <div className="grid">
        <section><h2>Incidents</h2>
          {incidents.length === 0 && <p className="muted">All clear.</p>}
          {incidents.map((i) => <Incident key={i.id} inc={i} onResolve={resolve} />)}
        </section>
        <aside>
          <h2>Deployments</h2>
          {deployments.map((d) => (
            <div key={d.id} className="mini"><strong>{d.service}</strong> {d.version}<br />
              <small>{new Date(d.deployed_at + "Z").toLocaleString()}</small></div>
          ))}
          <h2>Recent errors</h2>
          {logs.map((l, i) => <div key={i} className="mini err"><small>{l.service}</small><br />{l.message}</div>)}
        </aside>
      </div>
    </main>
  );
}
