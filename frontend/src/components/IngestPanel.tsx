import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { GitFork, Loader2, CheckCircle2, RefreshCw, AlertCircle, SkipForward, Zap } from "lucide-react";
import { useIngest } from "../hooks/useIngest";
import type { IngestResult } from "../types";

interface Props {
  onIngested: (result: IngestResult) => void;
}

const STATUS_CONFIG = {
  created: {
    icon: <CheckCircle2 size={16} />,
    color: "text-emerald-400",
    bg: "bg-emerald-500/10 border-emerald-500/30",
    label: "Indexed",
  },
  updated: {
    icon: <RefreshCw size={16} />,
    color: "text-blue-400",
    bg: "bg-blue-500/10 border-blue-500/30",
    label: "Updated",
  },
  skipped: {
    icon: <SkipForward size={16} />,
    color: "text-amber-400",
    bg: "bg-amber-500/10 border-amber-500/30",
    label: "Up to date",
  },
  error: {
    icon: <AlertCircle size={16} />,
    color: "text-red-400",
    bg: "bg-red-500/10 border-red-500/30",
    label: "Error",
  },
};

export function IngestPanel({ onIngested }: Props) {
  const [url, setUrl] = useState("");
  const { ingest, loading, result, error } = useIngest();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!url.trim()) return;
    const res = await ingest(url.trim());
    if (res) onIngested(res);
  };

  const cfg = result ? STATUS_CONFIG[result.status] : null;

  return (
    <div className="panel">
      <div className="panel-header">
        <GitFork size={18} className="text-violet-400" />
        <span>Repository Ingestion</span>
        <span className="badge">AST · Hybrid Search · Incremental</span>
      </div>

      <form onSubmit={handleSubmit} className="panel-body">
        <div className="input-row">
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
            {loading ? (
              <Loader2 size={16} className="animate-spin" />
            ) : (
              <Zap size={16} />
            )}
            {loading ? "Indexing..." : "Index Repo"}
          </motion.button>
        </div>

        <AnimatePresence>
          {(result || error) && (
            <motion.div
              className={`status-pill ${cfg?.bg ?? "bg-red-500/10 border-red-500/30"}`}
              initial={{ opacity: 0, y: -6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
            >
              <span className={cfg?.color ?? "text-red-400"}>
                {cfg?.icon ?? <AlertCircle size={16} />}
              </span>
              <span className={`text-sm font-medium ${cfg?.color ?? "text-red-400"}`}>
                {cfg?.label ?? "Error"}
              </span>
              <span className="text-sm text-slate-400">
                {error ?? result?.message}
              </span>
              {result?.chunks_stored !== undefined && result.chunks_stored > 0 && (
                <span className="ml-auto text-xs text-slate-500 font-mono">
                  {result.chunks_stored} chunks
                </span>
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </form>
    </div>
  );
}
