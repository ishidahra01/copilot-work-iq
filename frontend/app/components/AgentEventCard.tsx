"use client";

import { useState } from "react";
import { AgentEvent } from "@/app/lib/types";

interface Props {
  event: AgentEvent;
}

export default function AgentEventCard({ event }: Props) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="my-2 rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden text-sm">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between px-3 py-2
          bg-gray-50 dark:bg-gray-800/60 hover:bg-gray-100 dark:hover:bg-gray-700/60
          transition-colors text-left"
      >
        <div className="flex items-center gap-2 min-w-0">
          <span>🧠</span>
          <span className="font-medium text-gray-700 dark:text-gray-300 truncate">
            {event.eventName}
          </span>
          <span className="text-xs text-gray-400 shrink-0">
            {new Date(event.timestamp).toLocaleTimeString([], {
              hour: "2-digit",
              minute: "2-digit",
              second: "2-digit",
            })}
          </span>
        </div>
        <span className="text-gray-400 text-xs">{expanded ? "▲ hide" : "▼ show"}</span>
      </button>

      {expanded && (
        <div className="px-3 py-2 bg-white dark:bg-gray-900/40">
          <pre className="text-xs bg-gray-100 dark:bg-gray-800 rounded p-2 overflow-auto whitespace-pre-wrap break-words max-h-56">
            {JSON.stringify(event.data ?? {}, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}
