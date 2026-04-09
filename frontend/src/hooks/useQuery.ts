import { useState, useCallback } from "react";
import { fetchEventSource } from "@microsoft/fetch-event-source";
import type { Source, PipelineStep } from "../types";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

// Maps status message text to a pipeline step name
function resolveStep(message: string): PipelineStep {
  if (message.includes("Embedding")) return "embed";
  if (message.includes("Searching")) return "search";
  if (message.includes("Ranking")) return "rerank";
  if (message.includes("Generating")) return "generate";
  return "embed";
}

export function useQuery() {
  const [streaming, setStreaming] = useState(false);
  const [answer, setAnswer] = useState("");
  const [sources, setSources] = useState<Source[]>([]);
  const [activeStep, setActiveStep] = useState<PipelineStep | null>(null);
  const [completedSteps, setCompletedSteps] = useState<PipelineStep[]>([]);
  const [error, setError] = useState<string | null>(null);

  const query = useCallback(async (question: string, repoId: string) => {
    setStreaming(true);
    setAnswer("");
    setSources([]);
    setActiveStep(null);
    setCompletedSteps([]);
    setError(null);

    let lastStep: PipelineStep | null = null;

    await fetchEventSource(`${API_BASE}/api/query`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, repo_id: repoId }),

      onmessage(ev) {
        try {
          const event = JSON.parse(ev.data);

          if (event.type === "status") {
            const step = resolveStep(event.message);
            setActiveStep(step);
            if (lastStep && lastStep !== step) {
              setCompletedSteps((prev) => [...prev, lastStep!]);
            }
            lastStep = step;
          }

          if (event.type === "token") {
            setAnswer((prev) => prev + event.content);
          }

          if (event.type === "sources") {
            setSources(event.data);
          }

          if (event.type === "done") {
            if (lastStep) {
              setCompletedSteps((prev) => [...prev, lastStep!]);
            }
            setActiveStep("done");
            setStreaming(false);
          }

          if (event.type === "error") {
            setError(event.message);
            setStreaming(false);
          }
        } catch {
          // ignore parse errors on empty keep-alive lines
        }
      },

      onerror(err) {
        setError(err instanceof Error ? err.message : "Stream error");
        setStreaming(false);
        throw err; // stops fetchEventSource from retrying
      },
    });
  }, []);

  const reset = useCallback(() => {
    setAnswer("");
    setSources([]);
    setActiveStep(null);
    setCompletedSteps([]);
    setError(null);
    setStreaming(false);
  }, []);

  return { query, reset, streaming, answer, sources, activeStep, completedSteps, error };
}
