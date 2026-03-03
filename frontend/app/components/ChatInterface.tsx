"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { v4 as uuidv4 } from "uuid";
import { ChatMessage, Model, ServerEvent, ToolExecution } from "@/app/lib/types";
import { createSession, deleteSession, fetchModels, connectWebSocket } from "@/app/lib/api";
import MessageList from "./MessageList";
import ModelSelector from "./ModelSelector";

export default function ChatInterface() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [models, setModels] = useState<Model[]>([]);
  const [selectedModel, setSelectedModel] = useState("gpt-4o");
  const [inputValue, setInputValue] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const wsRef = useRef<WebSocket | null>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // -------------------------------------------------------------------------
  // Session management
  // -------------------------------------------------------------------------

  const initSession = useCallback(async () => {
    try {
      const id = await createSession();
      setSessionId(id);

      const ws = connectWebSocket(id);
      wsRef.current = ws;

      ws.onopen = () => console.log("WebSocket connected");
      ws.onerror = (e) => console.error("WebSocket error", e);
      ws.onclose = () => console.log("WebSocket closed");

      return ws;
    } catch (err) {
      console.error("Failed to init session", err);
    }
  }, []);

  useEffect(() => {
    fetchModels().then((m) => {
      setModels(m);
      if (m.length > 0) setSelectedModel(m[0].id);
    });

    let cleanupWs: WebSocket | null = null;
    let cleanupSessionId: string | null = null;

    initSession().then((ws) => {
      cleanupWs = ws ?? null;
    });

    return () => {
      cleanupWs?.close();
      if (cleanupSessionId) deleteSession(cleanupSessionId);
    };
  }, [initSession]);

  // -------------------------------------------------------------------------
  // Message streaming via WebSocket
  // -------------------------------------------------------------------------

  const sendMessage = useCallback(async () => {
    const prompt = inputValue.trim();
    if (!prompt || isLoading || !wsRef.current) return;

    setInputValue("");
    setIsLoading(true);

    // Add user message
    const userMsg: ChatMessage = {
      id: uuidv4(),
      role: "user",
      content: prompt,
      timestamp: Date.now(),
    };
    setMessages((prev) => [...prev, userMsg]);

    // Prepare assistant message placeholder
    const assistantMsgId = uuidv4();
    const assistantMsg: ChatMessage = {
      id: assistantMsgId,
      role: "assistant",
      content: "",
      timestamp: Date.now(),
      toolExecutions: [],
      isStreaming: true,
    };
    setMessages((prev) => [...prev, assistantMsg]);

    // Track tool executions in progress
    const activeTools = new Map<string, ToolExecution>();

    wsRef.current.onmessage = (event: MessageEvent) => {
      const data: ServerEvent = JSON.parse(event.data);

      switch (data.type) {
        case "assistant.message_delta":
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantMsgId
                ? { ...m, content: m.content + data.content, isStreaming: true }
                : m
            )
          );
          break;

        case "assistant.message":
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantMsgId
                ? { ...m, content: data.content, isStreaming: false }
                : m
            )
          );
          break;

        case "tool.execution_start": {
          const toolId = uuidv4();
          const te: ToolExecution = {
            id: toolId,
            toolName: data.tool_name,
            args: data.args,
            status: "running",
            startedAt: Date.now(),
          };
          activeTools.set(data.tool_name, te);
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantMsgId
                ? { ...m, toolExecutions: [...(m.toolExecutions ?? []), te] }
                : m
            )
          );
          break;
        }

        case "tool.execution_complete": {
          const te = activeTools.get(data.tool_name);
          if (te) {
            const updated: ToolExecution = {
              ...te,
              result: data.result,
              status: "complete",
              completedAt: Date.now(),
            };
            activeTools.set(data.tool_name, updated);
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantMsgId
                  ? {
                      ...m,
                      toolExecutions: (m.toolExecutions ?? []).map((t) =>
                        t.id === te.id ? updated : t
                      ),
                    }
                  : m
              )
            );
          }
          break;
        }

        case "session.idle":
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantMsgId ? { ...m, isStreaming: false } : m
            )
          );
          setIsLoading(false);
          break;

        case "error":
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantMsgId
                ? {
                    ...m,
                    content: m.content || `❌ Error: ${data.message}`,
                    isStreaming: false,
                  }
                : m
            )
          );
          setIsLoading(false);
          break;
      }
    };

    wsRef.current.send(
      JSON.stringify({ prompt, model: selectedModel })
    );
  }, [inputValue, isLoading, selectedModel]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const handleNewConversation = async () => {
    if (sessionId) {
      wsRef.current?.close();
      deleteSession(sessionId);
    }
    setMessages([]);
    setIsLoading(false);
    await initSession();
  };

  // -------------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------------

  return (
    <div className="flex flex-col h-screen bg-gray-50 dark:bg-gray-950">
      {/* Header */}
      <header className="flex items-center justify-between px-4 py-3
        bg-white dark:bg-gray-900 border-b border-gray-200 dark:border-gray-800 shadow-sm shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center text-white text-lg">
            🤖
          </div>
          <div>
            <h1 className="text-sm font-semibold text-gray-900 dark:text-gray-100">
              Microsoft Support Agent
            </h1>
            <p className="text-xs text-gray-500 dark:text-gray-400">
              Powered by GitHub Copilot SDK · Foundry · Work IQ
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <ModelSelector
            models={models}
            selected={selectedModel}
            onChange={setSelectedModel}
            disabled={isLoading}
          />
          <button
            onClick={handleNewConversation}
            disabled={isLoading}
            className="text-xs px-3 py-1.5 rounded-lg border border-gray-300 dark:border-gray-600
              hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-600 dark:text-gray-400
              disabled:opacity-50 transition-colors"
          >
            + New chat
          </button>
        </div>
      </header>

      {/* Message list */}
      <MessageList messages={messages} />

      {/* Input area */}
      <div className="shrink-0 bg-white dark:bg-gray-900 border-t border-gray-200 dark:border-gray-800 px-4 py-3">
        <div className="max-w-4xl mx-auto flex gap-2 items-end">
          <textarea
            ref={inputRef}
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isLoading}
            placeholder="Ask a technical question… (Enter to send, Shift+Enter for newline)"
            rows={1}
            className="flex-1 resize-none rounded-xl border border-gray-300 dark:border-gray-600
              bg-gray-50 dark:bg-gray-800 text-gray-900 dark:text-gray-100
              px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500
              disabled:opacity-50 placeholder-gray-400 dark:placeholder-gray-500
              max-h-40 overflow-y-auto"
            style={{ minHeight: "48px" }}
            onInput={(e) => {
              const el = e.currentTarget;
              el.style.height = "auto";
              el.style.height = Math.min(el.scrollHeight, 160) + "px";
            }}
          />
          <button
            onClick={sendMessage}
            disabled={isLoading || !inputValue.trim()}
            className="px-4 py-3 rounded-xl bg-blue-600 hover:bg-blue-700 text-white
              disabled:opacity-50 disabled:cursor-not-allowed transition-colors shrink-0"
            aria-label="Send message"
          >
            {isLoading ? (
              <svg className="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
            ) : (
              <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
              </svg>
            )}
          </button>
        </div>
        <p className="text-xs text-gray-400 dark:text-gray-600 text-center mt-2">
          Session: {sessionId?.slice(0, 8) ?? "—"}
        </p>
      </div>
    </div>
  );
}
