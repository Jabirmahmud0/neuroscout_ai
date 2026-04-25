import { useMemo, useState } from "react";
import { motion } from "framer-motion";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  AlertTriangle,
  Check,
  CheckCircle2,
  Clock,
  Copy,
  Database,
  Download,
  ExternalLink,
  FileText,
  FileType,
  Lightbulb,
  ShieldCheck,
  Sparkles,
  XCircle,
  Zap,
} from "lucide-react";
import { downloadFile, reportToMarkdown, reportToText } from "../lib/export";

function CitationBadge({ ids, references, onJump }) {
  return (
    <span className="inline-flex items-center gap-0.5 align-super">
      {ids.map((id, index) => {
        const reference = references.find((item) => item.id === id);
        return (
          <button
            key={`${id}-${index}`}
            onClick={() => onJump(id)}
            title={reference ? `${reference.title} - ${reference.url}` : `Source ${id}`}
            className="citation-badge"
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
  let cursor = 0;
  let match;
  let key = 0;

  while ((match = regex.exec(text)) !== null) {
    if (match.index > cursor) {
      parts.push(<span key={key++}>{text.slice(cursor, match.index)}</span>);
    }
    const ids = match[1]
      .split(",")
      .map((value) => parseInt(value.trim(), 10))
      .filter(Boolean);
    parts.push(<CitationBadge key={key++} ids={ids} references={references} onJump={onJump} />);
    cursor = match.index + match[0].length;
  }

  if (cursor < text.length) {
    parts.push(<span key={key++}>{text.slice(cursor)}</span>);
  }

  return parts;
}

const markdownComponents = (references, onJump) => {
  const wrap = (children) => {
    if (typeof children === "string") {
      return renderWithCitations(children, references, onJump);
    }
    if (Array.isArray(children)) {
      return children.map((child, index) =>
        typeof child === "string" ? (
          <span key={index}>{renderWithCitations(child, references, onJump)}</span>
        ) : (
          child
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

const SECTION_COLORS = [
  "from-violet-500 to-purple-600",
  "from-blue-500 to-indigo-600",
  "from-emerald-500 to-teal-600",
  "from-orange-500 to-amber-600",
  "from-rose-500 to-pink-600",
  "from-cyan-500 to-sky-600",
];

function MetricPill({ icon: Icon, children }) {
  return (
    <span className="report-meta-pill">
      <Icon className="w-3 h-3" /> {children}
    </span>
  );
}

const VALIDATION_LABELS = {
  has_causal_chain: { label: "Causal Chain", desc: "Multi-step A → B → C → D → Outcome" },
  has_cross_domain: { label: "Cross-Domain", desc: "Connects 2+ domains (e.g. neuro + econ)" },
  has_mechanism_depth: { label: "Mechanism Depth", desc: "Why / How / Effect in each section" },
  has_strong_sources: { label: "Strong Sources", desc: "≥2 research sources, ≤50% general" },
  has_insight_quality: { label: "Insight Quality", desc: "One mechanism-focused sentence, no jargon" },
  has_behavioral_economics: { label: "Behavioral Economics", desc: "2+ biases: loss aversion, sunk cost, etc." },
  has_human_reality_layer: { label: "Human Reality Layer", desc: "Social validation, FOMO, concrete patterns" },
  has_required_sections: { label: "Required Sections", desc: "Neuro / Psych / Behavioral / Cross-Domain" },
  has_evidence_gap_depth: { label: "Evidence Gap Depth", desc: "What / Why / Needed for each gap" },
  has_real_world_examples: { label: "Real-World Examples", desc: "Concrete relatable examples included" },
  has_identity_loop: { label: "Identity Loop", desc: "Identity → behavior → outcome → reinforcement" },
  has_escalation_pattern: { label: "Escalation Pattern", desc: "Small avoidance → delay → self-sabotage" },
};

function ValidationPanel({ validation }) {
  if (!validation || Object.keys(validation).length === 0) return null;

  const passed = Object.values(validation).filter(Boolean).length;
  const total = Object.keys(validation).length;
  const allPassed = passed === total;

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.15, duration: 0.25 }}
      className={`rounded-xl border p-5 mb-8 ${
        allPassed
          ? "border-emerald-200 bg-gradient-to-br from-emerald-50 to-teal-50"
          : "border-amber-200 bg-gradient-to-br from-amber-50 to-orange-50"
      }`}
      data-testid="validation-panel"
    >
      <div className="flex items-center gap-2.5 mb-4">
        <div
          className={`w-8 h-8 rounded-lg flex items-center justify-center ${
            allPassed ? "bg-emerald-500" : "bg-amber-500"
          }`}
        >
          {allPassed ? (
            <CheckCircle2 className="w-4.5 h-4.5 text-white" />
          ) : (
            <AlertTriangle className="w-4.5 h-4.5 text-white" />
          )}
        </div>
        <div>
          <div className="font-mono text-[10px] uppercase tracking-widest text-zinc-500">
            Quality Gates
          </div>
          <div className="text-sm font-semibold text-zinc-800">
            {passed}/{total} checks passed
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
        {Object.entries(validation).map(([key, value]) => {
          const meta = VALIDATION_LABELS[key] || { label: key, desc: "" };
          return (
            <div
              key={key}
              className={`flex items-start gap-2 px-3 py-2 rounded-lg border text-xs transition-colors ${
                value
                  ? "bg-white/60 border-emerald-200 text-emerald-800"
                  : "bg-white/60 border-red-200 text-red-800"
              }`}
            >
              {value ? (
                <CheckCircle2 className="w-3.5 h-3.5 mt-0.5 text-emerald-500 shrink-0" />
              ) : (
                <XCircle className="w-3.5 h-3.5 mt-0.5 text-red-500 shrink-0" />
              )}
              <div>
                <div className="font-semibold leading-tight">{meta.label}</div>
                <div className="text-[10px] opacity-70 mt-0.5 leading-snug">{meta.desc}</div>
              </div>
            </div>
          );
        })}
      </div>
    </motion.div>
  );
}

function InsightBlock({ title, icon: Icon, children, tone = "default" }) {
  const toneClass =
    tone === "warn"
      ? "border-amber-200 bg-amber-50"
      : tone === "danger"
      ? "border-rose-200 bg-rose-50"
      : "border-zinc-200 bg-zinc-50";

  return (
    <div className={`rounded-xl border p-5 ${toneClass}`}>
      <div className="flex items-center gap-2 mb-3">
        <Icon className="w-4 h-4 text-zinc-700" />
        <div className="font-mono text-[10px] uppercase tracking-widest text-zinc-500">{title}</div>
      </div>
      <div className="text-sm text-zinc-800 leading-relaxed">{children}</div>
    </div>
  );
}

export default function ReportView({ report, isStreaming }) {
  const [copied, setCopied] = useState(false);

  const markdown = useMemo(() => (report ? reportToMarkdown(report) : ""), [report]);

  const onCopy = async () => {
    if (!markdown) return;
    await navigator.clipboard.writeText(markdown);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  const onJump = (id) => {
    const element = document.getElementById(`ref-${id}`);
    if (element) {
      element.scrollIntoView({ behavior: "smooth", block: "center" });
    }
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
              ? "NeuroScout is gathering evidence and pressure-testing its answer."
              : "Run a research query to see a structured report with citations, conflicts, and confidence."}
          </div>
        </div>
      </div>
    );
  }

  const references = report.references || [];
  const confidence = report.confidence_summary || {};
  const topSourceIds = new Set(report.top_source_ids || []);

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: "easeOut" }}
      className="report-card overflow-hidden"
      data-testid="report-view"
    >
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
        <div className="flex items-center gap-3 text-xs text-zinc-400 flex-wrap justify-end">
          <MetricPill icon={Zap}>{report.search_iterations} iterations</MetricPill>
          <MetricPill icon={Clock}>{report.generation_time_sec}s</MetricPill>
          <MetricPill icon={Database}>{references.length} sources</MetricPill>
          <MetricPill icon={ShieldCheck}>{confidence.overall || "medium"} confidence</MetricPill>
          <MetricPill icon={Sparkles}>{report.mode || "balanced"} mode</MetricPill>
          <div className="flex items-center gap-1.5 ml-2">
            <button
              data-testid="export-md"
              onClick={() => downloadFile(`neuroscout-${report.report_id.slice(0, 8)}.md`, markdown, "text/markdown")}
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
            <button data-testid="copy-report" onClick={onCopy} className="report-action-btn">
              {copied ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
              {copied ? "Copied" : "Copy"}
            </button>
          </div>
        </div>
      </div>

      <div className="px-6 md:px-10 py-10 report-prose">
        <h1 className="report-title">{report.query}</h1>
        <div className="font-mono text-[10px] uppercase tracking-widest text-zinc-400 mb-10">
          Generated {new Date(report.created_at).toLocaleString()}
        </div>

        <div className="executive-summary-block">
          <div className="executive-summary-label">Executive Summary</div>
          <div className="text-base text-zinc-800 leading-relaxed">
            {renderWithCitations(report.executive_summary, references, onJump)}
          </div>
        </div>

        <ValidationPanel validation={report.telemetry?.validation} />

        <div className="grid md:grid-cols-2 gap-4 mb-10">
          {report.critical_insight && (
            <InsightBlock title="Critical Insight" icon={Lightbulb}>
              {renderWithCitations(report.critical_insight, references, onJump)}
            </InsightBlock>
          )}
          <InsightBlock title="Confidence" icon={ShieldCheck}>
            <div className="font-medium capitalize mb-1">{confidence.overall || "medium"}</div>
            <div>{confidence.rationale || "Confidence is based on source quality, breadth, and remaining gaps."}</div>
          </InsightBlock>
        </div>

        {(report.sections || []).map((section, index) => (
          <motion.section
            key={`${section.heading}-${index}`}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: index * 0.05, duration: 0.25 }}
            className="report-section"
          >
            <div className="report-section-header">
              <div className={`report-section-index bg-gradient-to-br ${SECTION_COLORS[index % SECTION_COLORS.length]}`}>
                {index + 1}
              </div>
              <h2 className="report-section-title">{section.heading}</h2>
            </div>
            <div className="report-section-body text-zinc-700">
              <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents(references, onJump)}>
                {section.content || ""}
              </ReactMarkdown>
            </div>
          </motion.section>
        ))}

        {(report.key_takeaways || []).length > 0 && (
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
            <ul className="key-takeaways-list">
              {report.key_takeaways.map((takeaway, index) => (
                <li key={index} className="key-takeaway-item">
                  <span className="key-takeaway-bullet" />
                  <span className="text-zinc-800 leading-relaxed text-[0.9375rem]">
                    {renderWithCitations(takeaway, references, onJump)}
                  </span>
                </li>
              ))}
            </ul>
          </motion.div>
        )}

        <div className="grid md:grid-cols-2 gap-4 mt-10">
          {(report.common_misconceptions || []).length > 0 && (
            <InsightBlock title="Common Misconceptions" icon={AlertTriangle} tone="warn">
              <ul className="space-y-2">
                {report.common_misconceptions.map((item, index) => (
                  <li key={index}>{renderWithCitations(item, references, onJump)}</li>
                ))}
              </ul>
            </InsightBlock>
          )}

          {(report.evidence_gaps || []).length > 0 && (
            <InsightBlock title="Evidence Gaps" icon={AlertTriangle} tone="warn">
              <ul className="space-y-3">
                {report.evidence_gaps.map((item, index) => (
                  <li key={index}>
                    {typeof item === "object" && item.gap ? (
                      <div>
                        <div className="font-semibold text-zinc-900">{item.gap}</div>
                        {item.reason && (
                          <div className="text-xs text-amber-700 mt-0.5">
                            <span className="font-medium">Why missing:</span> {item.reason}
                          </div>
                        )}
                        {item.needed && (
                          <div className="text-xs text-amber-700 mt-0.5">
                            <span className="font-medium">Needed:</span> {item.needed}
                          </div>
                        )}
                      </div>
                    ) : (
                      <span>{typeof item === "string" ? item : JSON.stringify(item)}</span>
                    )}
                  </li>
                ))}
              </ul>
            </InsightBlock>
          )}
        </div>

        {(report.conflicting_evidence || []).length > 0 && (
          <div className="mt-10">
            <div className="font-mono text-[10px] uppercase tracking-widest text-zinc-400 mb-4">
              Conflicting Evidence
            </div>
            <div className="space-y-3">
              {report.conflicting_evidence.map((item, index) => (
                <InsightBlock key={index} title={item.topic || "Conflict"} icon={AlertTriangle} tone="danger">
                  {renderWithCitations(item.summary, references, onJump)}
                </InsightBlock>
              ))}
            </div>
          </div>
        )}

        <div className="mt-12 pt-8 border-t border-zinc-100" data-testid="references-list">
          <div className="font-mono text-[10px] uppercase tracking-widest text-zinc-400 mb-5">
            References ({references.length})
          </div>
          <ol className="space-y-3">
            {references.map((reference) => (
              <li id={`ref-${reference.id}`} key={reference.id} className="flex gap-3 items-start scroll-mt-24 group">
                <span className="reference-badge">{reference.id}</span>
                <div className="min-w-0 flex-1">
                  <a
                    href={reference.url}
                    target="_blank"
                    rel="noreferrer"
                    className="text-sm text-zinc-800 hover:text-zinc-900 hover:underline break-words inline-flex items-start gap-1 font-medium transition-colors"
                  >
                    <span>{reference.title}</span>
                    <ExternalLink className="w-3 h-3 mt-1 opacity-40 group-hover:opacity-100 shrink-0 transition-opacity" />
                  </a>
                  <div className="font-mono text-[10px] text-zinc-400 mt-0.5 break-words">
                    {(reference.source_type || "general").toUpperCase()} - quality {reference.source_quality_score ?? "n/a"}
                    {topSourceIds.has(reference.id) ? " - top source" : ""}
                  </div>
                </div>
              </li>
            ))}
          </ol>
        </div>

        <div className="mt-10 pt-6 border-t border-zinc-100">
          <div className="font-mono text-[10px] text-zinc-400 leading-relaxed">
            AI-generated. Critical claims still need human verification, especially where evidence is limited or conflicting.
          </div>
        </div>
      </div>
    </motion.div>
  );
}
