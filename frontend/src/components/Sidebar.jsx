import { useEffect, useState } from "react";
import { BrainCircuit, History, Loader2, Plus, Trash2 } from "lucide-react";
import { deleteSession, fetchSessions } from "../lib/api";

export default function Sidebar({ activeSessionId, onSelectSession, onNewResearch, refreshKey }) {
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      const data = await fetchSessions();
      setSessions(data);
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, [refreshKey]);

  const handleDelete = async (event, id) => {
    event.stopPropagation();
    try {
      await deleteSession(id);
      setSessions((current) => current.filter((item) => item.session_id !== id));
      if (activeSessionId === id) {
        onSelectSession(null);
      }
    } catch (error) {
      console.error(error);
    }
  };

  return (
    <aside
      data-testid="sidebar"
      className="w-72 shrink-0 border-r border-zinc-200 bg-[#FAFAFA] flex flex-col h-screen sticky top-0"
    >
      <div className="px-6 pt-8 pb-6 border-b border-zinc-200">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 bg-zinc-900 flex items-center justify-center rounded-md">
            <BrainCircuit className="w-5 h-5 text-white" strokeWidth={2.2} />
          </div>
          <div>
            <div className="font-display font-black text-lg leading-none text-zinc-900">NeuroScout</div>
            <div className="font-mono text-[10px] uppercase tracking-widest text-zinc-500 mt-1">Research Agent</div>
          </div>
        </div>
      </div>

      <div className="px-4 pt-4 pb-2">
        <button
          data-testid="new-research-button"
          onClick={onNewResearch}
          className="w-full flex items-center justify-center gap-2 bg-zinc-900 hover:bg-zinc-800 text-white text-sm font-medium py-2.5 rounded-md transition-colors duration-150"
        >
          <Plus className="w-4 h-4" />
          New Research
        </button>
      </div>

      <div className="px-6 mt-4 mb-2 flex items-center gap-2 text-zinc-500">
        <History className="w-3.5 h-3.5" />
        <span className="font-mono text-[10px] uppercase tracking-widest">Recent</span>
      </div>

      <div className="flex-1 overflow-y-auto thin-scrollbar px-2 pb-6" data-testid="session-history">
        {loading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="w-4 h-4 animate-spin text-zinc-400" />
          </div>
        ) : sessions.length === 0 ? (
          <div className="px-4 py-3 text-xs text-zinc-400 italic">No sessions yet.</div>
        ) : (
          <ul className="flex flex-col gap-1">
            {sessions.map((session) => (
              <li key={session.session_id}>
                <button
                  data-testid={`history-item-${session.session_id}`}
                  onClick={() => onSelectSession(session.session_id)}
                  className={`group w-full text-left px-3 py-2 rounded-md flex items-start gap-2 transition-colors duration-150 ${
                    activeSessionId === session.session_id
                      ? "bg-zinc-200 text-zinc-900"
                      : "hover:bg-zinc-100 text-zinc-700"
                  }`}
                >
                  <span
                    className={`mt-1.5 w-1.5 h-1.5 rounded-full shrink-0 ${
                      session.status === "completed"
                        ? "bg-emerald-500"
                        : session.status === "failed"
                        ? "bg-red-500"
                        : "bg-amber-500"
                    }`}
                  />
                  <div className="flex-1 min-w-0">
                    <div className="text-sm leading-snug line-clamp-2">{session.query}</div>
                    <div className="font-mono text-[10px] text-zinc-400 mt-1">
                      {(session.mode || "balanced").toUpperCase()} -{" "}
                      {new Date(session.created_at).toLocaleString(undefined, {
                        month: "short",
                        day: "numeric",
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </div>
                  </div>
                  <Trash2
                    onClick={(event) => handleDelete(event, session.session_id)}
                    className="w-3.5 h-3.5 text-zinc-400 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-opacity"
                    data-testid={`delete-session-${session.session_id}`}
                  />
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="px-6 py-4 border-t border-zinc-200">
        <div className="font-mono text-[10px] text-zinc-400 leading-relaxed">
          v1.0.0 - Gemini 3 Flash Preview
          <br />
          Real-Time Web Research
        </div>
      </div>
    </aside>
  );
}
