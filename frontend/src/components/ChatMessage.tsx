import { motion, AnimatePresence } from "framer-motion";
import { User, BookOpen } from "lucide-react";
import { MarkdownContent } from "./MarkdownContent";
import { PipelineSteps } from "./PipelineSteps";
import { SourceCard } from "./SourceCard";
import type { HistoryMessage, PipelineStep, Source } from "../types";

// ── Completed message from history ──────────────────────

interface HistoryProps {
  message: HistoryMessage;
  index: number;
}

export function HistoryChatMessage({ message, index }: HistoryProps) {
  return (
    <motion.div
      className="chat-turn"
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index === 0 ? 0 : 0 }}
    >
      {/* User bubble */}
      <div className="user-bubble-row">
        <div className="user-bubble">{message.question}</div>
        <div className="avatar-icon">
          <User size={14} />
        </div>
      </div>

      {/* AI answer */}
      <div className="ai-answer-row">
        <div className="ai-avatar">
          <span className="ai-avatar-dot" />
        </div>
        <div className="ai-bubble">
          {message.error ? (
            <div className="md-error">{message.error}</div>
          ) : (
            <MarkdownContent content={message.answer} />
          )}

          <AnimatePresence>
            {message.sources.length > 0 && (
              <motion.div
                className="sources-section"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
              >
                <div className="sources-header">
                  <BookOpen size={13} className="text-slate-500" />
                  <span className="text-xs text-slate-500 font-medium uppercase tracking-wider">
                    Sources · {message.sources.length}
                  </span>
                </div>
                <div className="sources-list">
                  {message.sources.map((s, i) => (
                    <SourceCard key={`${s.file_path}-${s.name}-${i}`} source={s} index={i} />
                  ))}
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </motion.div>
  );
}

// ── Currently streaming message ──────────────────────────

interface StreamingProps {
  question: string;
  answer: string;
  sources: Source[];
  streaming: boolean;
  activeStep: PipelineStep | null;
  completedSteps: PipelineStep[];
  error: string | null;
}

export function StreamingChatMessage({
  question,
  answer,
  sources,
  streaming,
  activeStep,
  completedSteps,
  error,
}: StreamingProps) {
  return (
    <motion.div
      className="chat-turn"
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
    >
      {/* User bubble */}
      <div className="user-bubble-row">
        <div className="user-bubble">{question}</div>
        <div className="avatar-icon">
          <User size={14} />
        </div>
      </div>

      {/* AI answer area */}
      <div className="ai-answer-row">
        <div className="ai-avatar">
          {streaming ? (
            <motion.span
              className="ai-avatar-dot"
              animate={{ scale: [1, 1.3, 1], opacity: [1, 0.5, 1] }}
              transition={{ duration: 1, repeat: Infinity }}
            />
          ) : (
            <span className="ai-avatar-dot" />
          )}
        </div>
        <div className="ai-bubble">
          {/* Pipeline steps during streaming */}
          {activeStep && activeStep !== "done" && (
            <div className="mb-3">
              <PipelineSteps active={activeStep} completed={completedSteps} />
            </div>
          )}

          {error ? (
            <div className="md-error">{error}</div>
          ) : answer ? (
            <MarkdownContent content={answer} streaming={streaming} />
          ) : (
            streaming && (
              <div className="flex items-center gap-2 text-slate-500 text-sm">
                <motion.span
                  className="w-1.5 h-1.5 rounded-full bg-violet-400"
                  animate={{ opacity: [1, 0.2, 1] }}
                  transition={{ duration: 0.8, repeat: Infinity }}
                />
                Processing...
              </div>
            )
          )}

          <AnimatePresence>
            {sources.length > 0 && (
              <motion.div
                className="sources-section"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
              >
                <div className="sources-header">
                  <BookOpen size={13} className="text-slate-500" />
                  <span className="text-xs text-slate-500 font-medium uppercase tracking-wider">
                    Sources · {sources.length}
                  </span>
                </div>
                <div className="sources-list">
                  {sources.map((s, i) => (
                    <SourceCard key={`${s.file_path}-${s.name}-${i}`} source={s} index={i} />
                  ))}
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </motion.div>
  );
}
