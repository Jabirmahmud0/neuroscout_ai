import { useEffect, useRef } from "react";
import { motion } from "framer-motion";

const TYPE_META = {
  start: { label: "START", color: "text-zinc-900", bg: "bg-zinc-100", border: "border-zinc-300" },
  plan: { label: "PLAN", color: "text-blue-700", bg: "bg-blue-50", border: "border-blue-200" },
  search: { label: "SEARCH", color: "text-amber-700", bg: "bg-amber-50", border: "border-amber-200" },
  observe: { label: "OBSERVE", color: "text-violet-700", bg: "bg-violet-50", border: "border-violet-200" },
  reason: { label: "REASON", color: "text-pink-700", bg: "bg-pink-50", border: "border-pink-200" },
  synthesize: { label: "SYNTHESIZE", color: "text-emerald-700", bg: "bg-emerald-50", border: "border-emerald-200" },
  error: { label: "ERROR", color: "text-red-700", bg: "bg-red-50", border: "border-red-200" },
  done: { label: "DONE", color: "text-zinc-900", bg: "bg-zinc-100", border: "border-zinc-300" },
  session: { label: "SESSION", color: "text-zinc-500", bg: "bg-zinc-50", border: "border-zinc-200" },
};

function fmtTime(ts) {
  if (!ts) return "";
  try {
    const d = new Date(ts);
    return d.toLocaleTimeString(undefined, { hour12: false });
  } catch {
    return "";
  }
}

export default function AgentStream({ events, isRunning }) {
  const ref = useRef(null);

  useEffect(() => {
    if (ref.current) ref.current.scrollTop = ref.current.scrollHeight;
  }, [events.length]);

  return (
    <div
      data-testid="agent-stream"
      className="border border-zinc-200 bg-white h-full flex flex-col overflow-hidden rounded-md"
    >
      <div className="px-5 py-3 border-b border-zinc-200 flex items-center justify-between bg-[#FAFAFA]">
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-emerald-500" />
          <span className="font-mono text-[11px] uppercase tracking-widest text-zinc-700">
            Live Agent Stream
          </span>
        </div>
        <span className="font-mono text-[10px] text-zinc-400">{events.length} events</span>
      </div>

      <div
        ref={ref}
        className="flex-1 overflow-y-auto thin-scrollbar p-5 font-mono text-xs leading-relaxed text-zinc-700"
      >
        {events.length === 0 && (
          <div className="text-zinc-400">Waiting for agent to start…</div>
        )}

        {events.map((e, i) => {
          const meta = TYPE_META[e.type] || TYPE_META.session;
          const isLast = i === events.length - 1;

          return (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.15 }}
              className="mb-2.5"
              data-testid={`stream-event-${e.type}`}
            >
              <div className="flex items-start gap-2">
                <span className="text-zinc-400 shrink-0">{fmtTime(e.ts)}</span>
                <span
                  className={`px-1.5 py-px text-[10px] font-bold rounded ${meta.bg} ${meta.color} border ${meta.border} shrink-0`}
                >
                  {meta.label}
                </span>
                <span className="break-words">
                  {e.message || JSON.stringify(e).slice(0, 200)}
                  {isLast && isRunning && <span className="cursor-blink" />}
                </span>
              </div>

              {e.sub_questions && (
                <ul className="mt-1.5 ml-16 space-y-0.5 text-zinc-500">
                  {e.sub_questions.map((q, j) => (
                    <li key={j}>↳ {q}</li>
                  ))}
                </ul>
              )}

              {e.results && e.results.length > 0 && (
                <ul className="mt-1.5 ml-16 space-y-0.5 text-zinc-500">
                  {e.results.slice(0, 3).map((r, j) => (
                    <li key={j} className="truncate">
                      ↳{" "}
                      <a
                        href={r.url}
                        target="_blank"
                        rel="noreferrer"
                        className="hover:text-zinc-900 underline"
                      >
                        {r.title || r.url}
                      </a>
                    </li>
                  ))}
                </ul>
              )}
            </motion.div>
          );
        })}
      </div>
    </div>
  );
}
