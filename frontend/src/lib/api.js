// API helpers for NeuroScout AI

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API_BASE = `${BACKEND_URL}/api`;

export async function fetchSessions() {
  const r = await fetch(`${API_BASE}/sessions`);
  if (!r.ok) throw new Error("Failed to load sessions");
  return r.json();
}

export async function fetchSession(id) {
  const r = await fetch(`${API_BASE}/sessions/${id}`);
  if (!r.ok) throw new Error("Failed to load session");
  return r.json();
}

export async function deleteSession(id) {
  const r = await fetch(`${API_BASE}/sessions/${id}`, { method: "DELETE" });
  if (!r.ok) throw new Error("Failed to delete session");
  return r.json();
}

/**
 * Stream research events from the backend via SSE-over-fetch.
 * Calls onEvent for every parsed event object.
 * Returns the AbortController so the caller can cancel.
 */
export function streamResearch({ query, maxIterations = 5, onEvent, onError, onClose }) {
  const controller = new AbortController();

  (async () => {
    try {
      const resp = await fetch(`${API_BASE}/research/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, max_iterations: maxIterations }),
        signal: controller.signal,
      });

      if (!resp.ok || !resp.body) {
        const txt = await resp.text().catch(() => "");
        throw new Error(`HTTP ${resp.status}: ${txt}`);
      }

      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        // Split on SSE event boundary
        let idx;
        while ((idx = buffer.indexOf("\n\n")) !== -1) {
          const chunk = buffer.slice(0, idx);
          buffer = buffer.slice(idx + 2);

          // each chunk may have multiple "data:" lines
          const dataLines = chunk
            .split("\n")
            .filter((l) => l.startsWith("data:"))
            .map((l) => l.slice(5).trim());
          if (dataLines.length === 0) continue;

          const payload = dataLines.join("\n");
          try {
            const evt = JSON.parse(payload);
            onEvent && onEvent(evt);
          } catch (_) {
            // ignore malformed
          }
        }
      }
      onClose && onClose();
    } catch (e) {
      if (e.name === "AbortError") {
        onClose && onClose();
        return;
      }
      onError && onError(e);
    }
  })();

  return controller;
}
