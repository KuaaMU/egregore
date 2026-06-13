"use client";

import type { ProviderResponse } from "@/types";

interface ProviderPanelProps {
  provider: ProviderResponse | null;
  onClose: () => void;
}

export function ProviderPanel({ provider, onClose }: ProviderPanelProps) {
  if (!provider) {
    return (
      <aside className="w-80 border-l border-zinc-800 bg-zinc-900/30 flex flex-col items-center justify-center text-center p-6">
        <div className="text-4xl mb-3 text-zinc-800">⬡</div>
        <p className="text-sm text-zinc-600">
          Click a provider response to view details
        </p>
      </aside>
    );
  }

  return (
    <aside className="w-80 border-l border-zinc-800 bg-zinc-900/30 flex flex-col">
      {/* Header */}
      <div className="p-4 border-b border-zinc-800 flex items-center justify-between">
        <div>
          <h3 className="font-medium text-zinc-200">{provider.provider_id}</h3>
          <p className="text-xs text-zinc-500">{provider.model}</p>
        </div>
        <button
          onClick={onClose}
          className="text-zinc-600 hover:text-zinc-400 transition-colors"
        >
          ✕
        </button>
      </div>

      {/* Metrics */}
      <div className="grid grid-cols-2 gap-3 p-4 border-b border-zinc-800">
        <MetricCard label="Latency" value={`${provider.latency_ms.toFixed(0)}ms`} />
        <MetricCard label="Tokens" value={`${provider.token_count}`} />
        <MetricCard
          label="Status"
          value={provider.error ? "Error" : "Success"}
          highlight={provider.error ? "red" : "green"}
        />
        <MetricCard label="Length" value={`${provider.content.length} chars`} />
      </div>

      {/* Response Content */}
      <div className="flex-1 overflow-y-auto p-4">
        <h4 className="text-xs font-medium text-zinc-500 mb-2 uppercase tracking-wider">
          Response
        </h4>
        {provider.error ? (
          <div className="bg-red-950/20 border border-red-900/30 rounded-lg p-3">
            <p className="text-sm text-red-400">{provider.error}</p>
          </div>
        ) : (
          <div className="text-sm text-zinc-300 leading-relaxed whitespace-pre-wrap">
            {provider.content}
          </div>
        )}
      </div>
    </aside>
  );
}

function MetricCard({
  label,
  value,
  highlight,
}: {
  label: string;
  value: string;
  highlight?: "red" | "green";
}) {
  const colorClass = highlight === "red"
    ? "text-red-400"
    : highlight === "green"
      ? "text-emerald-400"
      : "text-zinc-200";

  return (
    <div className="bg-zinc-800/50 rounded-lg p-2.5">
      <p className="text-xs text-zinc-500 mb-1">{label}</p>
      <p className={`text-sm font-medium ${colorClass}`}>{value}</p>
    </div>
  );
}
