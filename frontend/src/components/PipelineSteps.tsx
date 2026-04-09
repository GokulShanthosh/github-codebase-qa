import { motion } from "framer-motion";
import { Cpu, Search, SortDesc, Bot, CheckCircle2 } from "lucide-react";
import type { PipelineStep } from "../types";

const STEPS: { key: PipelineStep; label: string; icon: React.ReactNode; desc: string }[] = [
  { key: "embed", label: "Embed", icon: <Cpu size={14} />, desc: "Query → vector" },
  { key: "search", label: "Retrieve", icon: <Search size={14} />, desc: "Hybrid BM25 + pgvector" },
  { key: "rerank", label: "Rerank", icon: <SortDesc size={14} />, desc: "FlashRank cross-encoder" },
  { key: "generate", label: "Generate", icon: <Bot size={14} />, desc: "Gemini 2.5 Flash" },
];

interface Props {
  active: PipelineStep | null;
  completed: PipelineStep[];
}

export function PipelineSteps({ active, completed }: Props) {
  if (!active) return null;

  return (
    <motion.div
      className="pipeline-steps"
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
    >
      {STEPS.map((step, i) => {
        const isDone = completed.includes(step.key);
        const isActive = active === step.key;

        return (
          <div key={step.key} className="step-item">
            <div className={`step-node ${isDone ? "step-done" : isActive ? "step-active" : "step-idle"}`}>
              {isDone ? <CheckCircle2 size={14} /> : step.icon}
              {isActive && (
                <motion.div
                  className="step-pulse"
                  animate={{ scale: [1, 1.6, 1], opacity: [0.6, 0, 0.6] }}
                  transition={{ duration: 1.4, repeat: Infinity }}
                />
              )}
            </div>
            <div className="step-label">
              <span className={isDone ? "text-slate-400" : isActive ? "text-white" : "text-slate-600"}>
                {step.label}
              </span>
              <span className="text-xs text-slate-600">{step.desc}</span>
            </div>
            {i < STEPS.length - 1 && (
              <div className={`step-connector ${isDone ? "bg-violet-500/40" : "bg-slate-700"}`} />
            )}
          </div>
        );
      })}
    </motion.div>
  );
}
