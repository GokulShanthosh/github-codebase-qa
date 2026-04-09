import { motion, AnimatePresence } from "framer-motion";
import { Bot, BookOpen } from "lucide-react";
import { PipelineSteps } from "./PipelineSteps";
import { SourceCard } from "./SourceCard";
import type { Source, PipelineStep } from "../types";

interface Props {
  streaming: boolean;
  answer: string;
  sources: Source[];
  activeStep: PipelineStep | null;
  completedSteps: PipelineStep[];
  error: string | null;
}

export function AnswerPanel({ streaming, answer, sources, activeStep, completedSteps, error }: Props) {
  const hasContent = answer || streaming || error;

  return (
    <AnimatePresence>
      {hasContent && (
        <motion.div
          className="panel"
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0 }}
        >
          <div className="panel-header">
            <Bot size={18} className="text-violet-400" />
            <span>Answer</span>
            {streaming && (
              <span className="flex items-center gap-1.5 ml-auto text-xs text-violet-400">
                <span className="w-1.5 h-1.5 rounded-full bg-violet-400 animate-pulse" />
                Streaming
              </span>
            )}
          </div>

          <div className="panel-body space-y-4">
            <PipelineSteps active={activeStep} completed={completedSteps} />

            {error && (
              <div className="text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-4 py-3">
                {error}
              </div>
            )}

            {answer && (
              <div className="answer-text">
                {answer}
                {streaming && (
                  <motion.span
                    className="inline-block w-0.5 h-4 bg-violet-400 ml-0.5 align-middle"
                    animate={{ opacity: [1, 0] }}
                    transition={{ duration: 0.6, repeat: Infinity }}
                  />
                )}
              </div>
            )}

            <AnimatePresence>
              {sources.length > 0 && (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="sources-section"
                >
                  <div className="sources-header">
                    <BookOpen size={14} className="text-slate-500" />
                    <span className="text-xs text-slate-500 font-medium uppercase tracking-wider">
                      Sources · {sources.length}
                    </span>
                  </div>
                  <div className="sources-list">
                    {sources.map((s, i) => (
                      <SourceCard key={`${s.file_path}-${s.name}`} source={s} index={i} />
                    ))}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
