// Message and event types for the support agent chat UI

export type MessageRole = "user" | "assistant" | "system";

export interface ToolExecution {
  id: string;
  toolName: string;
  args?: Record<string, unknown>;
  result?: string;
  status: "running" | "complete" | "error";
  startedAt: number;
  completedAt?: number;
}

export interface ChatMessage {
  id: string;
  role: MessageRole;
  content: string;
  timestamp: number;
  toolExecutions?: ToolExecution[];
  isStreaming?: boolean;
}

export interface Model {
  id: string;
  name: string;
}

// WebSocket events from the backend
export type ServerEvent =
  | { type: "assistant.message_delta"; content: string }
  | { type: "assistant.message"; content: string }
  | { type: "tool.execution_start"; tool_name: string; args: Record<string, unknown> }
  | { type: "tool.execution_complete"; tool_name: string; result: string }
  | { type: "session.idle" }
  | { type: "error"; message: string };

export interface ChatSession {
  sessionId: string;
  messages: ChatMessage[];
  isLoading: boolean;
}
