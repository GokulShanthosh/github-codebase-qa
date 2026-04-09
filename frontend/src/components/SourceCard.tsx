import { motion } from "framer-motion";
import { FileCode2, Hash } from "lucide-react";
import type { Source } from "../types";

interface Props {
  source: Source;
  index: number;
}

export function SourceCard({ source, index }: Props) {
  const fileName = source.file_path.split("/").pop() ?? source.file_path;
  const dirPath = source.file_path.split("/").slice(0, -1).join("/");

  return (
    <motion.div
      className="source-card"
      initial={{ opacity: 0, x: -8 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.06 }}
    >
      <div className="source-index">{index + 1}</div>
      <div className="source-info">
        <div className="source-name">
          <FileCode2 size={13} className="text-violet-400 shrink-0" />
          <span className="font-mono text-sm text-slate-200">{fileName}</span>
          {source.name && (
            <>
              <span className="text-slate-600">·</span>
              <span className="font-mono text-sm text-violet-300">{source.name}()</span>
            </>
          )}
        </div>
        <div className="source-meta">
          {dirPath && <span className="font-mono text-xs text-slate-500">{dirPath}/</span>}
          <span className="flex items-center gap-1 text-xs text-slate-500">
            <Hash size={11} />
            {source.start_line}–{source.end_line}
          </span>
        </div>
      </div>
    </motion.div>
  );
}
