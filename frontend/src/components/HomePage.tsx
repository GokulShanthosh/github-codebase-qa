import { motion } from "framer-motion";
import {
  Code2,
  GitBranch,
  Layers,
  Cpu,
  ArrowRight,
  Bot,
  Network,
  FlaskConical,
  Zap,
} from "lucide-react";

interface Props {
  onLaunch: (tool: string) => void;
}

const TOOLS = [
  {
    id: "codelens",
    icon: <Code2 size={28} />,
    title: "CodeLens",
    subtitle: "GitHub Codebase Q&A",
    description:
      "Ask natural language questions about any GitHub repository. Powered by AST-aware chunking, hybrid BM25 + pgvector retrieval, and LangGraph orchestration.",
    tags: ["AST Chunking", "Hybrid Search", "LangGraph", "Gemini 2.5"],
    status: "live" as const,
    accent: "#8b5cf6",
    accentBg: "rgba(139,92,246,0.08)",
    accentBorder: "rgba(139,92,246,0.25)",
  },
  {
    id: "code-review-agent",
    icon: <Bot size={28} />,
    title: "Code Review Agent",
    subtitle: "Multi-Agent PR Analysis",
    description:
      "Autonomous code review with specialized agents for security, bugs, code quality, and documentation — orchestrated via LangGraph supervisor.",
    tags: ["Multi-Agent", "LangGraph", "Security", "Static Analysis"],
    status: "soon" as const,
    accent: "#06b6d4",
    accentBg: "rgba(6,182,212,0.06)",
    accentBorder: "rgba(6,182,212,0.2)",
  },
  {
    id: "research-agent",
    icon: <Network size={28} />,
    title: "Research Assistant",
    subtitle: "AI-Powered Deep Research",
    description:
      "Multi-agent research pipeline with specialized agents for search, summarization, fact-checking, and citation generation.",
    tags: ["Search", "Summarize", "Fact-Check", "Citations"],
    status: "soon" as const,
    accent: "#10b981",
    accentBg: "rgba(16,185,129,0.06)",
    accentBorder: "rgba(16,185,129,0.2)",
  },
  {
    id: "llm-playground",
    icon: <FlaskConical size={28} />,
    title: "LLM Playground",
    subtitle: "Model Benchmarking & Evals",
    description:
      "Benchmark prompts across models, run eval suites, visualize token usage and latency — an engineer's testing ground.",
    tags: ["Evals", "Benchmarks", "Multi-model", "Observability"],
    status: "soon" as const,
    accent: "#f59e0b",
    accentBg: "rgba(245,158,11,0.06)",
    accentBorder: "rgba(245,158,11,0.2)",
  },
];

const FEATURE_PILLS = [
  { icon: <Layers size={13} />, label: "AST-aware code chunking" },
  { icon: <GitBranch size={13} />, label: "Incremental ingestion" },
  { icon: <Cpu size={13} />, label: "LangGraph orchestration" },
  { icon: <Zap size={13} />, label: "SSE streaming" },
];

export function HomePage({ onLaunch }: Props) {
  return (
    <div className="home-shell">
      {/* Hero */}
      <motion.div
        className="home-hero"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
      >
        <div className="home-badge">
          <span className="home-badge-dot" />
          AI Engineering Portfolio
        </div>
        <h1 className="home-title">
          Production-grade&nbsp;
          <span className="home-title-accent">AI tools</span>
          <br />
          built from scratch
        </h1>
        <p className="home-desc">
          A collection of LLM-powered applications demonstrating real engineering depth —
          RAG pipelines, multi-agent orchestration, and streaming interfaces.
        </p>
        <div className="home-feature-pills">
          {FEATURE_PILLS.map((f) => (
            <div key={f.label} className="home-feature-pill">
              {f.icon}
              {f.label}
            </div>
          ))}
        </div>
      </motion.div>

      {/* Cards */}
      <div className="tool-grid">
        {TOOLS.map((tool, i) => (
          <motion.div
            key={tool.id}
            className={`tool-card ${tool.status === "soon" ? "tool-card--soon" : ""}`}
            style={
              {
                "--card-accent": tool.accent,
                "--card-accent-bg": tool.accentBg,
                "--card-accent-border": tool.accentBorder,
              } as React.CSSProperties
            }
            initial={{ opacity: 0, y: 24 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 + i * 0.08 }}
            whileHover={tool.status === "live" ? { y: -3 } : {}}
          >
            {/* Status badge */}
            <div className="tool-card-status-row">
              {tool.status === "live" ? (
                <span className="status-live">
                  <span className="status-dot-live" />
                  Live
                </span>
              ) : (
                <span className="status-soon">Coming soon</span>
              )}
            </div>

            {/* Icon */}
            <div className="tool-card-icon">{tool.icon}</div>

            {/* Title */}
            <div className="tool-card-titles">
              <h2 className="tool-card-title">{tool.title}</h2>
              <p className="tool-card-subtitle">{tool.subtitle}</p>
            </div>

            {/* Description */}
            <p className="tool-card-desc">{tool.description}</p>

            {/* Tags */}
            <div className="tool-card-tags">
              {tool.tags.map((tag) => (
                <span key={tag} className="tool-tag">{tag}</span>
              ))}
            </div>

            {/* CTA */}
            {tool.status === "live" ? (
              <button
                className="tool-card-btn"
                onClick={() => onLaunch(tool.id)}
              >
                Launch
                <ArrowRight size={15} />
              </button>
            ) : (
              <button className="tool-card-btn tool-card-btn--disabled" disabled>
                Coming soon
              </button>
            )}

            {/* Soon overlay tint */}
            {tool.status === "soon" && <div className="tool-card-overlay" />}
          </motion.div>
        ))}
      </div>
    </div>
  );
}
