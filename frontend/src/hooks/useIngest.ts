import { useState } from "react";
import type { IngestResult } from "../types";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

export function useIngest() {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<IngestResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const ingest = async (repoUrl: string) => {
    setLoading(true);
    setResult(null);
    setError(null);

    try {
      const res = await fetch(`${API_BASE}/api/ingest`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ repo_url: repoUrl }),
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || "Ingestion failed");
      }

      const data: IngestResult = await res.json();
      setResult(data);
      return data;
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Unknown error";
      setError(msg);
      return null;
    } finally {
      setLoading(false);
    }
  };

  return { ingest, loading, result, error };
}
