import { useState, useRef, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { MessageSquare, Send, RotateCcw, Sparkles, ChevronsDown } from "lucide-react";
import { useQuery } from "../hooks/useQuery";
import { HistoryChatMessage, StreamingChatMessage } from "./ChatMessage";
import type { HistoryMessage } from "../types";

interface Props {
  repoId: string | null;
}

const EXAMPLE_QUESTIONS = [
  "How does authentication work in this repo?",
  "What are the main API endpoints?",
  "Explain the database models",
  "How are errors handled?",
];

let msgIdCounter = 0;
const nextId = () => String(++msgIdCounter);

const BOTTOM_THRESHOLD = 80; // px — within this distance = "at bottom"

export function QueryPanel({ repoId }: Props) {
  const [question, setQuestion] = useState("");
  const [history, setHistory] = useState<HistoryMessage[]>([]);
  const [streamingQuestion, setStreamingQuestion] = useState("");
  const [isAtBottom, setIsAtBottom] = useState(true);

  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);   // the scrollable container
  const bottomRef = useRef<HTMLDivElement>(null);   // sentinel at the very bottom
  const wasStreamingRef = useRef(false);

  const { query, reset, streaming, answer, sources, activeStep, completedSteps, error } =
    useQuery();

  // ── Scroll helpers ──────────────────────────────────────

  const scrollToBottom = useCallback((behavior: ScrollBehavior = "smooth") => {
    bottomRef.current?.scrollIntoView({ behavior, block: "end" });
  }, []);

  // Track whether the user is near the bottom
  const handleScroll = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    const distFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    setIsAtBottom(distFromBottom < BOTTOM_THRESHOLD);
  }, []);

  // ── Auto-scroll rules ───────────────────────────────────

  // 1. When user submits — always jump to bottom (they just sent something)
  useEffect(() => {
    if (!streamingQuestion) return;
    scrollToBottom("smooth");
    setIsAtBottom(true);
  }, [streamingQuestion, scrollToBottom]);

  // 2. While streaming tokens — only scroll if already at bottom
  useEffect(() => {
    if (answer && isAtBottom) {
      scrollToBottom("smooth");
    }
    // intentionally not including isAtBottom in deps — we want a snapshot
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [answer, scrollToBottom]);

  // 3. When a message is committed to history — scroll if at bottom
  useEffect(() => {
    if (isAtBottom) scrollToBottom("smooth");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [history.length, scrollToBottom]);

  // ── Auto-resize textarea ────────────────────────────────
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  }, [question]);

  // ── Commit streaming → history ──────────────────────────
  useEffect(() => {
    if (wasStreamingRef.current && !streaming && streamingQuestion) {
      setHistory((prev) => [
        ...prev,
        { id: nextId(), question: streamingQuestion, answer, sources, error },
      ]);
      setStreamingQuestion("");
      reset();
    }
    wasStreamingRef.current = streaming;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [streaming]);

  // ── Submit ──────────────────────────────────────────────
  const handleSubmit = useCallback(
    async (e: React.FormEvent | React.KeyboardEvent) => {
      e.preventDefault();
      const q = question.trim();
      if (!q || !repoId || streaming) return;
      setQuestion("");
      setStreamingQuestion(q);
      await query(q, repoId);
    },
    [question, repoId, streaming, query]
  );

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  const handleClear = () => {
    setHistory([]);
    setStreamingQuestion("");
    reset();
    setQuestion("");
  };

  const disabled = !repoId;
  const hasMessages = history.length > 0 || !!streamingQuestion;
  const showScrollBtn = hasMessages && !isAtBottom;

  return (
    <div className="chat-panel">
      {/* Header */}
      <div className="panel-header">
        <MessageSquare size={18} className="text-violet-400" />
        <span>Ask About the Codebase</span>
        {hasMessages && (
          <button onClick={handleClear} className="ml-auto icon-btn" title="Clear chat">
            <RotateCcw size={14} />
          </button>
        )}
      </div>

      {/* Scroll container */}
      <div className="chat-body-wrap">
        <div
          ref={scrollRef}
          className="chat-body"
          onScroll={handleScroll}
        >
          <AnimatePresence>
            {!hasMessages && (
              <motion.div
                className="chat-empty"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
              >
                {disabled ? (
                  <div className="empty-state">
                    <div className="empty-icon"><MessageSquare size={24} /></div>
                    <p className="empty-title">No repository indexed yet</p>
                    <p className="empty-sub">
                      Index a GitHub repository above to start asking questions.
                    </p>
                  </div>
                ) : (
                  <div className="empty-state">
                    <div className="empty-icon"><Sparkles size={24} /></div>
                    <p className="empty-title">Ask anything about the codebase</p>
                    <p className="empty-sub">Try one of these to get started:</p>
                    <div className="example-pills mt-3">
                      {EXAMPLE_QUESTIONS.map((q) => (
                        <button
                          key={q}
                          type="button"
                          className="example-pill"
                          onClick={() => setQuestion(q)}
                        >
                          {q}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </motion.div>
            )}
          </AnimatePresence>

          {history.map((msg) => (
            <HistoryChatMessage key={msg.id} message={msg} index={0} />
          ))}

          {streamingQuestion && (
            <StreamingChatMessage
              question={streamingQuestion}
              answer={answer}
              sources={sources}
              streaming={streaming}
              activeStep={activeStep}
              completedSteps={completedSteps}
              error={error}
            />
          )}

          <div ref={bottomRef} className="h-2" />
        </div>

        {/* Scroll-to-bottom button */}
        <AnimatePresence>
          {showScrollBtn && (
            <motion.button
              className="scroll-down-btn"
              onClick={() => {
                scrollToBottom("smooth");
                setIsAtBottom(true);
              }}
              initial={{ opacity: 0, y: 8, scale: 0.9 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 8, scale: 0.9 }}
              transition={{ duration: 0.15 }}
              title="Scroll to bottom"
            >
              <ChevronsDown size={16} />
              {streaming && (
                <span className="scroll-btn-live-dot" />
              )}
            </motion.button>
          )}
        </AnimatePresence>
      </div>

      {/* Input bar */}
      <div className="chat-input-bar">
        <form onSubmit={handleSubmit} className="chat-input-form">
          <textarea
            ref={textareaRef}
            className="chat-textarea"
            placeholder={
              disabled
                ? "Index a repository first..."
                : "Ask anything... (Enter to send, Shift+Enter for new line)"
            }
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={disabled || streaming}
            rows={1}
          />
          <motion.button
            className="btn-send"
            type="submit"
            disabled={disabled || streaming || !question.trim()}
            whileTap={{ scale: 0.93 }}
          >
            <Send size={16} />
          </motion.button>
        </form>
        <p className="chat-hint">
          {streaming ? "Generating response..." : "Enter to send · Shift+Enter for new line"}
        </p>
      </div>
    </div>
  );
}
