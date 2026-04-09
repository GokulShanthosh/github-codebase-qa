export interface Source {
  file_path: string;
  name: string | null;
  start_line: number;
  end_line: number;
}

export type IngestStatus = "created" | "updated" | "skipped" | "error";

export interface IngestResult {
  status: IngestStatus;
  message: string;
  chunks_stored: number;
  repo_id: string;
}

export type PipelineStep = "embed" | "search" | "rerank" | "generate" | "done";

export interface SSEEvent {
  type: "status" | "token" | "sources" | "error" | "done";
  message?: string;
  content?: string;
  data?: Source[];
}

export interface HistoryMessage {
  id: string;
  question: string;
  answer: string;
  sources: Source[];
  error: string | null;
}
