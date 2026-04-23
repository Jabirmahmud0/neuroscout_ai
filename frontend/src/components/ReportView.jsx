import { useMemo, useState } from "react";
import { motion } from "framer-motion";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Download, Copy, Check, ExternalLink, FileText, FileType, Lightbulb, Clock, Database, Zap } from "lucide-react";
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
            className="citation-badge"
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

/* ── Section index badge colours (cycles) ── */
const SECTION_COLORS = [
  "from-violet-500 to-purple-600",
  "from-blue-500 to-indigo-600",
  "from-emerald-500 to-teal-600",
  "from-orange-500 to-amber-600",
  "from-rose-500 to-pink-600",
  "from-cyan-500 to-sky-600",
];

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
        className="border border-dashed border-zinc-200 bg-[#FAFAFA] h-full flex items-center justify-center rounded-xl p-12 text-center"
      >
        <div>
          <div className="w-12 h-12 rounded-full bg-zinc-100 flex items-center justify-center mx-auto mb-4">
            <FileText className="w-5 h-5 text-zinc-400" />
          </div>
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
  const takeaways = report.key_takeaways || [];

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: "easeOut" }}
      data-testid="report-view"
      className="report-card overflow-hidden"
    >
      {/* ── Toolbar ── */}
      <div className="report-toolbar">
        <div className="flex items-center gap-3">
          <div className="report-toolbar-icon">
            <FileText className="w-4 h-4" />
          </div>
          <div>
            <span className="font-mono text-[11px] uppercase tracking-widest text-zinc-700 font-semibold">
              Research Report
            </span>
          </div>
        </div>
        <div className="flex items-center gap-3 text-xs text-zinc-400">
          <span className="report-meta-pill">
            <Zap className="w-3 h-3" /> {report.search_iterations} iterations
          </span>
          <span className="report-meta-pill">
            <Clock className="w-3 h-3" /> {report.generation_time_sec}s
          </span>
          <span className="report-meta-pill">
            <Database className="w-3 h-3" /> {report.references?.length || 0} sources
          </span>
          <div className="flex items-center gap-1.5 ml-2">
            <button
              data-testid="export-md"
              onClick={() => downloadFile(`neuroscout-${report.report_id.slice(0, 8)}.md`, md, "text/markdown")}
              className="report-action-btn"
            >
              <Download className="w-3.5 h-3.5" /> .md
            </button>
            <button
              data-testid="export-txt"
              onClick={() => downloadFile(`neuroscout-${report.report_id.slice(0, 8)}.txt`, reportToText(report))}
              className="report-action-btn"
            >
              <FileType className="w-3.5 h-3.5" /> .txt
            </button>
            <button
              data-testid="copy-report"
              onClick={onCopy}
              className="report-action-btn"
            >
              {copied ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
              {copied ? "Copied" : "Copy"}
            </button>
          </div>
        </div>
      </div>

      {/* ── Body ── */}
      <div className="px-6 md:px-10 py-10 report-prose">

        {/* Title */}
        <h1 className="report-title">{report.query}</h1>
        <div className="font-mono text-[10px] uppercase tracking-widest text-zinc-400 mb-10">
          Generated {new Date(report.created_at).toLocaleString()}
        </div>

        {/* Executive Summary */}
        <div className="executive-summary-block">
          <div className="executive-summary-label">Executive Summary</div>
          <div className="text-base text-zinc-800 leading-relaxed">
            {renderWithCitations(report.executive_summary, report.references || [], onJump)}
          </div>
        </div>

        {/* Sections */}
        {(report.sections || []).map((s, i) => (
          <motion.section
            key={i}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.05, duration: 0.25 }}
            className="report-section"
            data-testid={`report-section-${i}`}
          >
            <div className="report-section-header">
              <div className={`report-section-index bg-gradient-to-br ${SECTION_COLORS[i % SECTION_COLORS.length]}`}>
                {i + 1}
              </div>
              <h2 className="report-section-title">{s.heading}</h2>
            </div>
            <div className="report-section-body text-zinc-700">
              <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
                {s.content || ""}
              </ReactMarkdown>
            </div>
          </motion.section>
        ))}

        {/* ── Key Takeaways Summary ── */}
        {takeaways.length > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2, duration: 0.35 }}
            className="key-takeaways-block"
            data-testid="key-takeaways"
          >
            <div className="key-takeaways-header">
              <div className="key-takeaways-icon">
                <Lightbulb className="w-4 h-4" />
              </div>
              <span className="key-takeaways-label">Key Takeaways</span>
            </div>
            <p className="key-takeaways-subtext">
              The most important conclusions from this research — for readers in a hurry.
            </p>
            <ul className="key-takeaways-list">
              {takeaways.map((t, i) => (
                <li key={i} className="key-takeaway-item">
                  <span className="key-takeaway-bullet" />
                  <span className="text-zinc-800 leading-relaxed text-[0.9375rem]">
                    {renderWithCitations(t, report.references || [], onJump)}
                  </span>
                </li>
              ))}
            </ul>
          </motion.div>
        )}

        {/* References */}
        <div className="mt-12 pt-8 border-t border-zinc-100" data-testid="references-list">
          <div className="font-mono text-[10px] uppercase tracking-widest text-zinc-400 mb-5">
            References ({report.references?.length || 0})
          </div>
          <ol className="space-y-3">
            {(report.references || []).map((r) => (
              <li
                id={`ref-${r.id}`}
                key={r.id}
                className="flex gap-3 items-start scroll-mt-24 group"
                data-testid={`reference-${r.id}`}
              >
                <span className="reference-badge">{r.id}</span>
                <div className="min-w-0 flex-1">
                  <a
                    href={r.url}
                    target="_blank"
                    rel="noreferrer"
                    className="text-sm text-zinc-800 hover:text-zinc-900 hover:underline break-words inline-flex items-start gap-1 font-medium transition-colors"
                  >
                    <span>{r.title}</span>
                    <ExternalLink className="w-3 h-3 mt-1 opacity-40 group-hover:opacity-100 shrink-0 transition-opacity" />
                  </a>
                  <div className="font-mono text-[10px] text-zinc-400 truncate mt-0.5">{r.url}</div>
                </div>
              </li>
            ))}
          </ol>
        </div>

        {/* Disclaimer */}
        <div className="mt-10 pt-6 border-t border-zinc-100">
          <div className="font-mono text-[10px] text-zinc-400 leading-relaxed">
            AI-generated. Verify critical claims independently. NeuroScout grounds every
            section in retrieved evidence but cannot guarantee absolute accuracy.
          </div>
        </div>
      </div>
    </motion.div>
  );
}
