import { useRef, useState } from "react";
import { ArrowRight, Sparkles } from "lucide-react";

const EXAMPLES = [
  "Why do people procrastinate despite knowing the consequences?",
  "The neuroscience of social media addiction and dopamine reward loops",
  "How does decision fatigue affect self-control and avoidance behavior?",
  "Investigate the habit loop behind compulsive smartphone checking",
  "Why do people stay in toxic relationships despite wanting to leave?",
  "The neuroscience and behavioral economics of impulse buying",
];

export default function QueryInput({ onSubmit, disabled }) {
  const [value, setValue] = useState("");
  const [mode, setMode] = useState("balanced");
  const ref = useRef(null);

  const submit = () => {
    const v = value.trim();
    if (!v || disabled) return;
    onSubmit({ query: v, mode });
  };

  const handleKey = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };

  return (
    <div className="w-full max-w-4xl mx-auto" data-testid="query-input-container">
      <div className="text-center mb-12">
        <div className="inline-flex items-center gap-2 px-3 py-1 border border-zinc-200 rounded-full font-mono text-[10px] uppercase tracking-widest text-zinc-600 mb-6">
          <Sparkles className="w-3 h-3" />
          Autonomous Research Agent
        </div>
        <h1 className="font-display font-black text-4xl sm:text-5xl lg:text-6xl text-zinc-900 leading-[1.05]">
          What should we investigate?
        </h1>
        <p className="mt-4 text-zinc-500 text-base max-w-xl mx-auto">
          Enter any research topic. NeuroScout will plan, search the live web, reason
          across sources, and write a fully cited report.
        </p>
      </div>

      <div className="relative">
        <textarea
          ref={ref}
          data-testid="query-input"
          value={value}
          onChange={(e) => setValue(e.target.value.slice(0, 500))}
          onKeyDown={handleKey}
          placeholder="Type a research topic..."
          rows={2}
          autoFocus
          className="w-full bg-transparent text-2xl md:text-3xl font-display font-normal text-zinc-900 placeholder:text-zinc-300 border-0 border-b-2 border-zinc-200 focus:border-zinc-900 focus:ring-0 focus:outline-none resize-none py-4 pr-16 transition-colors duration-150"
          disabled={disabled}
        />
        <button
          data-testid="submit-research"
          onClick={submit}
          disabled={!value.trim() || disabled}
          className="absolute right-0 bottom-5 w-11 h-11 bg-zinc-900 hover:bg-zinc-700 disabled:bg-zinc-200 disabled:cursor-not-allowed text-white rounded-md flex items-center justify-center transition-colors duration-150"
        >
          <ArrowRight className="w-5 h-5" />
        </button>
        <div className="font-mono text-[10px] text-zinc-400 mt-2 text-right">
          {value.length}/500
        </div>
      </div>

      <div className="mt-6">
        <div className="font-mono text-[10px] uppercase tracking-widest text-zinc-400 mb-3">
          Research mode
        </div>
        <div className="flex flex-wrap gap-2">
          {[
            ["quick", "Fast pass"],
            ["balanced", "Best default"],
            ["deep", "Maximum depth"],
          ].map(([id, label]) => (
            <button
              key={id}
              type="button"
              onClick={() => setMode(id)}
              disabled={disabled}
              className={`px-3 py-2 rounded-md text-sm border transition-colors duration-150 ${
                mode === id
                  ? "bg-zinc-900 text-white border-zinc-900"
                  : "border-zinc-200 text-zinc-700 hover:border-zinc-900 hover:bg-zinc-50"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      <div className="mt-12">
        <div className="font-mono text-[10px] uppercase tracking-widest text-zinc-400 mb-3">
          Try an example
        </div>
        <div className="flex flex-wrap gap-2">
          {EXAMPLES.map((ex, i) => (
            <button
              key={i}
              data-testid={`example-chip-${i}`}
              onClick={() => {
                setValue(ex);
                ref.current?.focus();
              }}
              className="text-left text-sm text-zinc-700 border border-zinc-200 hover:border-zinc-900 hover:bg-zinc-50 px-3 py-2 rounded-md transition-colors duration-150"
              disabled={disabled}
            >
              {ex}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
