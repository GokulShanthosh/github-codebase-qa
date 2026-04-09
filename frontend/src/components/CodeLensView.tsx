import { useState } from "react";
import { motion } from "framer-motion";
import { IngestBar } from "./IngestBar";
import { QueryPanel } from "./QueryPanel";
import type { IngestResult } from "../types";

interface Props {
  onBack?: () => void;
}

// onBack is used by App.tsx header — kept for interface clarity
export function CodeLensView({ onBack: _onBack }: Props) {
  const [ingestResult, setIngestResult] = useState<IngestResult | null>(null);

  return (
    <motion.div
      className="codelens-view"
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
    >
      <IngestBar onIngested={setIngestResult} currentRepo={ingestResult} />
      <div className="codelens-chat-area">
        <QueryPanel repoId={ingestResult?.repo_id ?? null} />
      </div>
    </motion.div>
  );
}
