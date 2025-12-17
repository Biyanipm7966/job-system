import { useEffect, useMemo, useRef, useState } from "react";
import { createJob, listJobs, wsUrl } from "./api";

const JOB_TYPES = ["email_send", "pdf_render", "data_sync", "generic_task"];

function badge(status) {
  const map = {
    QUEUED: "🟦 QUEUED",
    RUNNING: "🟣 RUNNING",
    SUCCEEDED: "🟩 SUCCEEDED",
    FAILED: "🟧 FAILED",
    DEAD: "🟥 DEAD",
  };
  return map[status] || status;
}

export default function App() {
  const [jobs, setJobs] = useState([]);
  const [type, setType] = useState(JOB_TYPES[0]);
  const [payloadText, setPayloadText] = useState(`{"to":"user@company.com","subject":"Hello"}`);
  const [maxRetries, setMaxRetries] = useState(3);
  const [log, setLog] = useState([]);
  const wsRef = useRef(null);

  async function refresh() {
    const res = await listJobs(50);
    setJobs(res.jobs || []);
  }

  useEffect(() => {
    refresh();
  }, []);

  useEffect(() => {
    const ws = new WebSocket(wsUrl());
    wsRef.current = ws;

    ws.onmessage = (evt) => {
      try {
        const e = JSON.parse(evt.data);
        setLog((prev) => [e, ...prev].slice(0, 50));
        if (e.event === "JOB_CREATED" || e.event === "JOB_UPDATED" || e.event === "JOB_DEAD") {
          refresh();
        }
      } catch {
        // ignore
      }
    };

    ws.onopen = () => setLog((p) => [{ event: "WS_OPEN" }, ...p].slice(0, 50));
    ws.onclose = () => setLog((p) => [{ event: "WS_CLOSE" }, ...p].slice(0, 50));

    return () => ws.close();
  }, []);

  async function submitJob() {
    let payload = {};
    try {
      payload = JSON.parse(payloadText);
    } catch {
      alert("Payload must be valid JSON");
      return;
    }
    await createJob(type, payload, Number(maxRetries));
    setPayloadText(payloadText); // keep
  }

  const sorted = useMemo(() => {
    return [...jobs].sort((a, b) => (b.created_at || 0) - (a.created_at || 0));
  }, [jobs]);

  return (
    <div style={{ maxWidth: 1100, margin: "24px auto", padding: "0 16px" }}>
      <h1 style={{ marginBottom: 6 }}>Distributed Job Processing & Monitoring</h1>
      <div style={{ opacity: 0.75, marginBottom: 16 }}>
        Queue + workers + retries + dead-letter + real-time updates (Redis + FastAPI + React)
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1.3fr", gap: 16 }}>
        <div style={{ border: "1px solid #ddd", borderRadius: 12, padding: 16 }}>
          <h3 style={{ marginTop: 0 }}>Submit Job</h3>

          <div style={{ display: "grid", gap: 10 }}>
            <label>
              Type:&nbsp;
              <select value={type} onChange={(e) => setType(e.target.value)}>
                {JOB_TYPES.map((t) => (
                  <option key={t} value={t}>{t}</option>
                ))}
              </select>
            </label>

            <label>
              Max Retries:&nbsp;
              <input
                type="number"
                min={0}
                max={10}
                value={maxRetries}
                onChange={(e) => setMaxRetries(e.target.value)}
                style={{ width: 80 }}
              />
            </label>

            <label>Payload (JSON)</label>
            <textarea
              rows={8}
              value={payloadText}
              onChange={(e) => setPayloadText(e.target.value)}
              style={{ width: "100%", fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace" }}
            />

            <div style={{ display: "flex", gap: 8 }}>
              <button onClick={submitJob}>Create Job</button>
              <button onClick={refresh}>Refresh</button>
            </div>
          </div>

          <div style={{ marginTop: 16 }}>
            <h4 style={{ marginBottom: 8 }}>Live Events</h4>
            <div style={{ maxHeight: 250, overflow: "auto", borderTop: "1px solid #eee", paddingTop: 8 }}>
              {log.map((e, idx) => (
                <div key={idx} style={{ fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace", fontSize: 12, opacity: 0.85 }}>
                  {JSON.stringify(e)}
                </div>
              ))}
            </div>
          </div>
        </div>

        <div style={{ border: "1px solid #ddd", borderRadius: 12, padding: 16 }}>
          <h3 style={{ marginTop: 0 }}>Jobs</h3>

          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead>
                <tr>
                  <th align="left">ID</th>
                  <th align="left">Type</th>
                  <th align="left">Status</th>
                  <th align="left">Attempt</th>
                  <th align="left">Max</th>
                  <th align="left">Last Error</th>
                </tr>
              </thead>
              <tbody>
                {sorted.map((j) => (
                  <tr key={j.id} style={{ borderTop: "1px solid #eee" }}>
                    <td style={{ padding: "8px 0" }}>{j.id}</td>
                    <td style={{ padding: "8px 0" }}>{j.type}</td>
                    <td style={{ padding: "8px 0" }}>{badge(j.status)}</td>
                    <td style={{ padding: "8px 0" }}>{j.attempt}</td>
                    <td style={{ padding: "8px 0" }}>{j.max_retries}</td>
                    <td style={{ padding: "8px 0" }}>{j.last_error || "-"}</td>
                  </tr>
                ))}
                {sorted.length === 0 && (
                  <tr>
                    <td colSpan={6} style={{ padding: "10px 0", opacity: 0.7 }}>
                      No jobs yet. Create one.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          <p style={{ opacity: 0.7, marginTop: 12 }}>
            Tip: Create a few <b>pdf_render</b> jobs — some will fail and retry automatically.
          </p>
        </div>
      </div>
    </div>
  );
}
