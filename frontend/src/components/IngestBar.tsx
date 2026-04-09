import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  GitFork,
  Loader2,
  CheckCircle2,
  RefreshCw,
  AlertCircle,
  SkipForward,
  Zap,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { useIngest } from "../hooks/useIngest";
import type { IngestResult } from "../types";

interface Props {
  onIngested: (result: IngestResult) => void;
  currentRepo: IngestResult | null;
}

const STATUS_ICON = {
  created: <CheckCircle2 size={14} />,
  updated: <RefreshCw size={14} />,
  skipped: <SkipForward size={14} />,
  error: <AlertCircle size={14} />,
};

const STATUS_COLOR = {
  created: "text-emerald-400",
  updated: "text-blue-400",
  skipped: "text-amber-400",
  error: "text-red-400",
};

export function IngestBar({ onIngested, currentRepo }: Props) {
  const [url, setUrl] = useState("");
  const [expanded, setExpanded] = useState(!currentRepo);
  const { ingest, loading, result, error } = useIngest();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!url.trim()) return;
    const res = await ingest(url.trim());
    if (res) {
      onIngested(res);
      setExpanded(false);
    }
  };

  return (
    <div className="ingest-bar">
      {/* Always-visible top row */}
      <div className="ingest-bar-top">
        <GitFork size={15} className="text-violet-400 shrink-0" />
        <span className="ingest-bar-label">Repository</span>

        {currentRepo ? (
          <div className="ingest-bar-repo-info">
            <span className="w-2 h-2 rounded-full bg-emerald-400 shrink-0" />
            <span className="font-mono text-sm text-slate-300 truncate">
              {currentRepo.repo_id}
            </span>
            {currentRepo.chunks_stored > 0 && (
              <span className="text-xs text-slate-500 font-mono shrink-0">
                {currentRepo.chunks_stored} chunks
              </span>
            )}
          </div>
        ) : (
          <span className="text-sm text-slate-500">No repository indexed</span>
        )}

        <button
          className="ingest-toggle-btn"
          onClick={() => setExpanded((v) => !v)}
          title={expanded ? "Collapse" : "Index a repo"}
        >
          {expanded ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
        </button>
      </div>

      {/* Expandable form */}
      <AnimatePresence initial={false}>
        {expanded && (
          <motion.div
            className="ingest-bar-form"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
          >
            <form onSubmit={handleSubmit} className="ingest-form-inner">
              <input
                className="url-input"
                type="text"
                placeholder="https://github.com/owner/repo"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                disabled={loading}
                spellCheck={false}
              />
              <motion.button
                className="btn-primary"
                type="submit"
                disabled={loading || !url.trim()}
                whileTap={{ scale: 0.96 }}
              >
                {loading ? <Loader2 size={15} className="animate-spin" /> : <Zap size={15} />}
                {loading ? "Indexing..." : "Index"}
              </motion.button>
            </form>

            <AnimatePresence>
              {(result || error) && (
                <motion.div
                  className="ingest-status-row"
                  initial={{ opacity: 0, y: -4 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0 }}
                >
                  {result && (
                    <span className={STATUS_COLOR[result.status]}>
                      {STATUS_ICON[result.status]}
                    </span>
                  )}
                  <span className="text-sm text-slate-400">
                    {error ?? result?.message}
                  </span>
                </motion.div>
              )}
            </AnimatePresence>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
