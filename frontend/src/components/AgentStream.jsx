import { useEffect, useRef } from "react";
import { motion } from "framer-motion";

const TYPE_META = {
  start: { label: "START", color: "text-zinc-900", bg: "bg-zinc-100", border: "border-zinc-300" },
  plan: { label: "PLAN", color: "text-blue-700", bg: "bg-blue-50", border: "border-blue-200" },
  search: { label: "SEARCH", color: "text-amber-700", bg: "bg-amber-50", border: "border-amber-200" },
  observe: { label: "OBSERVE", color: "text-violet-700", bg: "bg-violet-50", border: "border-violet-200" },
  reason: { label: "CRITIC", color: "text-pink-700", bg: "bg-pink-50", border: "border-pink-200" },
  synthesize: { label: "SYNTH", color: "text-emerald-700", bg: "bg-emerald-50", border: "border-emerald-200" },
  error: { label: "ERROR", color: "text-red-700", bg: "bg-red-50", border: "border-red-200" },
  done: { label: "DONE", color: "text-zinc-900", bg: "bg-zinc-100", border: "border-zinc-300" },
  session: { label: "SESSION", color: "text-zinc-500", bg: "bg-zinc-50", border: "border-zinc-200" },
};

function fmtTime(ts) {
  if (!ts) return "";
  try {
    return new Date(ts).toLocaleTimeString(undefined, { hour12: false });
  } catch (e) {
    return "";
  }
}

export default function AgentStream({ events, isRunning }) {
  const ref = useRef(null);

  useEffect(() => {
    if (ref.current) {
      ref.current.scrollTop = ref.current.scrollHeight;
    }
  }, [events.length]);

  return (
    <div data-testid="agent-stream" className="border border-zinc-200 bg-white h-full flex flex-col overflow-hidden rounded-md">
      <div className="px-5 py-3 border-b border-zinc-200 flex items-center justify-between bg-[#FAFAFA]">
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-emerald-500" />
          <span className="font-mono text-[11px] uppercase tracking-widest text-zinc-700">Live Agent Stream</span>
        </div>
        <span className="font-mono text-[10px] text-zinc-400">{events.length} events</span>
      </div>

      <div ref={ref} className="flex-1 overflow-y-auto thin-scrollbar p-5 font-mono text-xs leading-relaxed text-zinc-700">
        {events.length === 0 && <div className="text-zinc-400">Waiting for agent to start...</div>}

        {events.map((event, index) => {
          const meta = TYPE_META[event.type] || TYPE_META.session;
          const isLast = index === events.length - 1;

          return (
            <motion.div
              key={`${event.type}-${index}`}
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.15 }}
              className="mb-3"
            >
              <div className="flex items-start gap-2">
                <span className="text-zinc-400 shrink-0">{fmtTime(event.ts)}</span>
                <span className={`px-1.5 py-px text-[10px] font-bold rounded ${meta.bg} ${meta.color} border ${meta.border} shrink-0`}>
                  {meta.label}
                </span>
                <span className="break-words">
                  {event.message || JSON.stringify(event).slice(0, 220)}
                  {isLast && isRunning && <span className="cursor-blink" />}
                </span>
              </div>

              {event.plan && (
                <ul className="mt-1.5 ml-16 space-y-2 text-zinc-500">
                  {event.plan.map((item, itemIndex) => (
                    <li key={itemIndex}>
                      <div className="text-zinc-700">{item.intent?.toUpperCase()} - {item.sub_question}</div>
                      <div className="text-[11px] text-zinc-400">{(item.search_queries || []).join(" | ")}</div>
                    </li>
                  ))}
                </ul>
              )}

              {event.results && event.results.length > 0 && (
                <ul className="mt-1.5 ml-16 space-y-1 text-zinc-500">
                  {event.results.slice(0, 3).map((result, resultIndex) => (
                    <li key={resultIndex} className="break-words">
                      <a href={result.url} target="_blank" rel="noreferrer" className="hover:text-zinc-900 underline">
                        {result.title || result.url}
                      </a>
                      <span className="text-[11px] text-zinc-400">
                        {" "}
                        - {(result.source_type || "general").toUpperCase()} - q {result.source_quality_score ?? "n/a"}
                      </span>
                    </li>
                  ))}
                </ul>
              )}

              {event.missing_aspects?.length > 0 && (
                <ul className="mt-1.5 ml-16 space-y-0.5 text-zinc-500">
                  {event.missing_aspects.map((item, itemIndex) => (
                    <li key={itemIndex}>gap {'→'} {item}</li>
                  ))}
                </ul>
              )}

              {event.new_queries?.length > 0 && (
                <ul className="mt-1.5 ml-16 space-y-0.5 text-zinc-500">
                  {event.new_queries.map((item, itemIndex) => (
                    <li key={itemIndex}>follow-up {'→'} {item}</li>
                  ))}
                </ul>
              )}

              {event.conflicts?.length > 0 && (
                <ul className="mt-1.5 ml-16 space-y-0.5 text-zinc-500">
                  {event.conflicts.map((item, itemIndex) => (
                    <li key={itemIndex}>conflict {'→'} {item.topic || item.summary}</li>
                  ))}
                </ul>
              )}

              {event.validation && (
                <div className="mt-2 ml-16 grid grid-cols-2 gap-1">
                  {Object.entries(event.validation).map(([key, passed]) => (
                    <div
                      key={key}
                      className={`flex items-center gap-1.5 text-[11px] px-2 py-1 rounded ${
                        passed
                          ? "text-emerald-700 bg-emerald-50"
                          : "text-red-700 bg-red-50"
                      }`}
                    >
                      <span className={`w-1.5 h-1.5 rounded-full ${passed ? "bg-emerald-500" : "bg-red-500"}`} />
                      {key.replace("has_", "").replace(/_/g, " ")}
                    </div>
                  ))}
                </div>
              )}
            </motion.div>
          );
        })}
      </div>
    </div>
  );
}
