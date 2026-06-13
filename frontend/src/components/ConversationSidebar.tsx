"use client";

interface HistoryItem {
  id: string;
  prompt: string;
  timestamp: Date;
}

interface ConversationSidebarProps {
  history: HistoryItem[];
  onSelect: (id: string) => void;
}

export function ConversationSidebar({ history, onSelect }: ConversationSidebarProps) {
  return (
    <aside className="w-64 border-r border-zinc-800 bg-zinc-900/50 flex flex-col">
      {/* Header */}
      <div className="p-4 border-b border-zinc-800">
        <h1 className="text-lg font-semibold tracking-tight">
          <span className="text-violet-400">⬡</span> Egregore
        </h1>
        <p className="text-xs text-zinc-500 mt-1">Where Intelligence Emerges Together</p>
      </div>

      {/* New Chat Button */}
      <div className="p-3">
        <button className="w-full px-3 py-2 text-sm rounded-lg border border-zinc-700 hover:bg-zinc-800 transition-colors text-zinc-300">
          + New Discussion
        </button>
      </div>

      {/* History List */}
      <div className="flex-1 overflow-y-auto px-2">
        {history.length === 0 ? (
          <p className="text-xs text-zinc-600 px-2 py-4">No conversations yet</p>
        ) : (
          history.map((item) => (
            <button
              key={item.id}
              onClick={() => onSelect(item.id)}
              className="w-full text-left px-3 py-2 rounded-lg text-sm text-zinc-400 hover:bg-zinc-800/50 hover:text-zinc-200 transition-colors mb-1 truncate"
            >
              {item.prompt}
            </button>
          ))
        )}
      </div>

      {/* Footer */}
      <div className="p-3 border-t border-zinc-800 text-xs text-zinc-600">
        v0.1.0 — Round Table
      </div>
    </aside>
  );
}
