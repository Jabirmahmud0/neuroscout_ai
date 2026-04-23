import { useMemo, useState } from "react";
import { motion } from "framer-motion";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Download, Copy, Check, ExternalLink, FileText, FileType } from "lucide-react";
import { reportToMarkdown, reportToText, downloadFile } from "../lib/export";

function CitationBadge({ ids, references, onJump }) {
  return (
    <span className="inline-flex items-center gap-0.5 align-super">
      {ids.map((id, i) => {
        const ref = references.find((r) => r.id === id);
        return (
          <button
            key={i}
            onClick={() => onJump && onJump(id)}
            title={ref ? `${ref.title} — ${ref.url}` : `Source ${id}`}
            className="inline-flex items-center justify-center min-w-[18px] h-[18px] px-1 text-[10px] font-bold font-mono bg-zinc-900 text-white hover:bg-zinc-700 rounded-[3px] transition-colors duration-150"
            data-testid={`citation-${id}`}
          >
            {id}
          </button>
        );
      })}
    </span>
  );
}

function renderWithCitations(text, references, onJump) {
  // Replace [n] or [n,m] with placeholder spans then render
  // Strategy: split by regex, build elements
  if (!text) return null;
  const parts = [];
  const regex = /\[(\d+(?:\s*,\s*\d+)*)\]/g;
  let lastIndex = 0;
  let m;
  let key = 0;
  while ((m = regex.exec(text)) !== null) {
    if (m.index > lastIndex) {
      parts.push({ type: "text", value: text.slice(lastIndex, m.index), key: key++ });
    }
    const ids = m[1].split(",").map((s) => parseInt(s.trim(), 10)).filter(Boolean);
    parts.push({ type: "cite", ids, key: key++ });
    lastIndex = m.index + m[0].length;
  }
  if (lastIndex < text.length) {
    parts.push({ type: "text", value: text.slice(lastIndex), key: key++ });
  }

  return parts.map((p) =>
    p.type === "cite" ? (
      <CitationBadge key={p.key} ids={p.ids} references={references} onJump={onJump} />
    ) : (
      <span key={p.key}>{p.value}</span>
    ),
  );
}

// Custom paragraph/li renderers that intercept text and add citation badges
const buildMarkdownComponents = (references, onJump) => {
  const wrap = (children) => {
    if (typeof children === "string") {
      return renderWithCitations(children, references, onJump);
    }
    if (Array.isArray(children)) {
      return children.map((c, i) =>
        typeof c === "string" ? (
          <span key={i}>{renderWithCitations(c, references, onJump)}</span>
        ) : (
          c
        ),
      );
    }
    return children;
  };
  return {
    p: ({ children }) => <p>{wrap(children)}</p>,
    li: ({ children }) => <li>{wrap(children)}</li>,
    a: ({ href, children }) => (
      <a href={href} target="_blank" rel="noreferrer" className="underline">
        {children}
      </a>
    ),
  };
};

export default function ReportView({ report, isStreaming }) {
  const [copied, setCopied] = useState(false);

  const md = useMemo(() => (report ? reportToMarkdown(report) : ""), [report]);

  const onCopy = async () => {
    if (!md) return;
    await navigator.clipboard.writeText(md);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  const onJump = (id) => {
    const el = document.getElementById(`ref-${id}`);
    if (el) el.scrollIntoView({ behavior: "smooth", block: "center" });
  };

  if (!report) {
    return (
      <div
        data-testid="report-placeholder"
        className="border border-dashed border-zinc-200 bg-[#FAFAFA] h-full flex items-center justify-center rounded-md p-12 text-center"
      >
        <div>
          <div className="font-mono text-[10px] uppercase tracking-widest text-zinc-400 mb-2">
            {isStreaming ? "Synthesizing" : "Awaiting report"}
          </div>
          <div className="text-zinc-500 text-sm max-w-sm">
            {isStreaming
              ? "Agent is collecting evidence. The structured report will appear here."
              : "Run a research query to see the synthesized, cited report."}
          </div>
        </div>
      </div>
    );
  }

  const components = buildMarkdownComponents(report.references || [], onJump);

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
      data-testid="report-view"
      className="border border-zinc-200 bg-white rounded-md overflow-hidden"
    >
      <div className="px-6 py-4 border-b border-zinc-200 bg-[#FAFAFA] flex flex-wrap items-center gap-3 justify-between">
        <div className="flex items-center gap-2">
          <FileText className="w-4 h-4 text-zinc-500" />
          <span className="font-mono text-[11px] uppercase tracking-widest text-zinc-700">
            Research Report
          </span>
          <span className="font-mono text-[10px] text-zinc-400 ml-2">
            {report.search_iterations} iterations · {report.generation_time_sec}s ·{" "}
            {report.references?.length || 0} sources
          </span>
        </div>
        <div className="flex items-center gap-2">
          <button
            data-testid="export-md"
            onClick={() => downloadFile(`neuroscout-${report.report_id.slice(0, 8)}.md`, md, "text/markdown")}
            className="inline-flex items-center gap-1.5 px-2.5 py-1.5 text-xs border border-zinc-200 hover:border-zinc-900 hover:bg-zinc-50 rounded-md transition-colors duration-150"
          >
            <Download className="w-3.5 h-3.5" />
            .md
          </button>
          <button
            data-testid="export-txt"
            onClick={() => downloadFile(`neuroscout-${report.report_id.slice(0, 8)}.txt`, reportToText(report))}
            className="inline-flex items-center gap-1.5 px-2.5 py-1.5 text-xs border border-zinc-200 hover:border-zinc-900 hover:bg-zinc-50 rounded-md transition-colors duration-150"
          >
            <FileType className="w-3.5 h-3.5" />
            .txt
          </button>
          <button
            data-testid="copy-report"
            onClick={onCopy}
            className="inline-flex items-center gap-1.5 px-2.5 py-1.5 text-xs border border-zinc-200 hover:border-zinc-900 hover:bg-zinc-50 rounded-md transition-colors duration-150"
          >
            {copied ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
            {copied ? "Copied" : "Copy"}
          </button>
        </div>
      </div>

      <div className="px-6 md:px-10 py-8 report-prose">
        <h1 className="font-display font-black text-3xl md:text-4xl tracking-tight text-zinc-900 mb-2">
          {report.query}
        </h1>
        <div className="font-mono text-[10px] uppercase tracking-widest text-zinc-400 mb-8">
          Generated {new Date(report.created_at).toLocaleString()}
        </div>

        <div className="border-l-2 border-zinc-900 pl-5 mb-10 bg-[#FAFAFA] py-4 pr-4 rounded-r">
          <div className="font-mono text-[10px] uppercase tracking-widest text-zinc-500 mb-2">
            Executive Summary
          </div>
          <div className="text-base text-zinc-800 leading-relaxed">
            {renderWithCitations(report.executive_summary, report.references || [], onJump)}
          </div>
        </div>

        {(report.sections || []).map((s, i) => (
          <section key={i} className="mb-8" data-testid={`report-section-${i}`}>
            <h2 className="font-display font-bold text-2xl text-zinc-900 mb-3">{s.heading}</h2>
            <div className="text-zinc-800">
              <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
                {s.content || ""}
              </ReactMarkdown>
            </div>
          </section>
        ))}

        <div className="mt-12 pt-8 border-t border-zinc-200" data-testid="references-list">
          <div className="font-mono text-[10px] uppercase tracking-widest text-zinc-500 mb-4">
            References ({report.references?.length || 0})
          </div>
          <ol className="space-y-3">
            {(report.references || []).map((r) => (
              <li
                id={`ref-${r.id}`}
                key={r.id}
                className="flex gap-3 items-start scroll-mt-24"
                data-testid={`reference-${r.id}`}
              >
                <span className="font-mono text-xs font-bold text-zinc-900 bg-zinc-100 rounded px-1.5 py-0.5 mt-0.5 shrink-0">
                  {r.id}
                </span>
                <div className="min-w-0 flex-1">
                  <a
                    href={r.url}
                    target="_blank"
                    rel="noreferrer"
                    className="text-sm text-zinc-900 hover:underline break-words inline-flex items-start gap-1 group"
                  >
                    <span>{r.title}</span>
                    <ExternalLink className="w-3 h-3 mt-1 opacity-50 group-hover:opacity-100 shrink-0" />
                  </a>
                  <div className="font-mono text-[10px] text-zinc-400 truncate mt-0.5">
                    {r.url}
                  </div>
                </div>
              </li>
            ))}
          </ol>
        </div>

        <div className="mt-12 pt-6 border-t border-zinc-200">
          <div className="font-mono text-[10px] text-zinc-400 leading-relaxed">
            AI-generated. Verify critical claims independently. NeuroScout grounds every
            section in retrieved evidence but cannot guarantee absolute accuracy.
          </div>
        </div>
      </div>
    </motion.div>
  );
}
