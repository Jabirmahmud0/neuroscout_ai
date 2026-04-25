import { useCallback, useRef, useState } from "react";
import Sidebar from "../components/Sidebar";
import QueryInput from "../components/QueryInput";
import AgentStream from "../components/AgentStream";
import ReportView from "../components/ReportView";
import { streamResearch, fetchSession } from "../lib/api";
import { Loader2, ArrowLeft } from "lucide-react";

export default function Dashboard() {
  const [events, setEvents] = useState([]);
  const [report, setReport] = useState(null);
  const [isRunning, setIsRunning] = useState(false);
  const [activeSessionId, setActiveSessionId] = useState(null);
  const [historyKey, setHistoryKey] = useState(0);
  const [error, setError] = useState(null);
  const controllerRef = useRef(null);

  const reset = () => {
    if (controllerRef.current) controllerRef.current.abort();
    setEvents([]);
    setReport(null);
    setIsRunning(false);
    setActiveSessionId(null);
    setError(null);
  };

  const handleSubmit = useCallback(({ query, mode }) => {
    setEvents([]);
    setReport(null);
    setError(null);
    setIsRunning(true);
    setActiveSessionId(null);

    controllerRef.current = streamResearch({
      query,
      mode,
      maxIterations: mode === "quick" ? 2 : mode === "deep" ? 6 : 4,
      onEvent: (evt) => {
        setEvents((prev) => [...prev, evt]);
        if (evt.type === "session" && evt.session_id) {
          setActiveSessionId(evt.session_id);
        }
        if (evt.type === "final" && evt.report) {
          setReport(evt.report);
        }
        if (evt.type === "done") {
          setIsRunning(false);
          setHistoryKey((k) => k + 1);
        }
        if (evt.type === "error") {
          setError(evt.message || "Unknown error");
        }
      },
      onError: (e) => {
        setError(e.message || String(e));
        setIsRunning(false);
      },
      onClose: () => {
        setIsRunning(false);
      },
    });
  }, []);

  const handleSelectSession = useCallback(async (id) => {
    if (!id) {
      reset();
      return;
    }
    if (controllerRef.current) controllerRef.current.abort();
    setIsRunning(false);
    setEvents([]);
    setError(null);
    setActiveSessionId(id);
    try {
      const data = await fetchSession(id);
      setReport(data.report || null);
      if (data.error_message) setError(data.error_message);
    } catch (e) {
      setError(e.message);
    }
  }, []);

  const showActive = isRunning || events.length > 0 || report;

  return (
    <div className="flex min-h-screen bg-white" data-testid="dashboard">
      <Sidebar
        activeSessionId={activeSessionId}
        onSelectSession={handleSelectSession}
        onNewResearch={reset}
        refreshKey={historyKey}
      />

      <main className="flex-1 min-w-0">
        {!showActive ? (
          <div className="min-h-screen flex items-center justify-center px-8 py-16">
            <QueryInput onSubmit={handleSubmit} disabled={isRunning} />
          </div>
        ) : (
          <div className="px-6 md:px-10 py-8 max-w-[1600px] mx-auto">
            <div className="flex items-center justify-between mb-6 flex-wrap gap-3">
              <button
                data-testid="back-button"
                onClick={reset}
                className="inline-flex items-center gap-1.5 text-sm text-zinc-600 hover:text-zinc-900 transition-colors duration-150"
              >
                <ArrowLeft className="w-4 h-4" />
                New research
              </button>
              {isRunning && (
                <div className="inline-flex items-center gap-2 font-mono text-[11px] uppercase tracking-widest text-zinc-700">
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  Agent running
                </div>
              )}
            </div>

            {error && (
              <div
                data-testid="error-banner"
                className="mb-6 border border-red-200 bg-red-50 text-red-800 text-sm px-4 py-3 rounded-md"
              >
                {error}
              </div>
            )}

            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
              <div className="lg:col-span-4 lg:sticky lg:top-6 lg:self-start lg:h-[calc(100vh-6rem)]">
                <AgentStream events={events} isRunning={isRunning} />
              </div>
              <div className="lg:col-span-8">
                <ReportView report={report} isStreaming={isRunning && !report} />
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
