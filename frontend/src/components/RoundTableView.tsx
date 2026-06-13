"use client";

import { useState } from "react";
import type { RoundTableResult, ProviderResponse } from "@/types";

interface RoundTableViewProps {
  result: RoundTableResult | null;
  isLoading: boolean;
  onSubmit: (prompt: string) => void;
  onSelectProvider: (provider: ProviderResponse) => void;
}

export function RoundTableView({
  result,
  isLoading,
  onSubmit,
  onSelectProvider,
}: RoundTableViewProps) {
  const [prompt, setPrompt] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (prompt.trim() && !isLoading) {
      onSubmit(prompt.trim());
      setPrompt("");
    }
  };

  return (
    <main className="flex-1 flex flex-col">
      {/* Header */}
      <header className="border-b border-zinc-800 px-6 py-4">
        <h2 className="text-sm font-medium text-zinc-400">Round Table Discussion</h2>
      </header>

      {/* Content Area */}
      <div className="flex-1 overflow-y-auto px-6 py-6">
        {!result && !isLoading && (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <div className="text-6xl mb-6">⬡</div>
            <h2 className="text-2xl font-semibold mb-2">Ask the Collective</h2>
            <p className="text-zinc-500 max-w-md">
              Your question will be dispatched to multiple AI providers in parallel.
              Their responses will be analyzed for consensus and contradictions.
            </p>
          </div>
        )}

        {isLoading && (
          <div className="flex flex-col items-center justify-center h-full">
            <div className="animate-pulse text-violet-400 text-4xl mb-4">⬡</div>
            <p className="text-zinc-400">Consulting the collective...</p>
            <p className="text-xs text-zinc-600 mt-2">Dispatching to all providers</p>
          </div>
        )}

        {result && (
          <div className="max-w-3xl mx-auto space-y-6">
            {/* Prompt */}
            <div className="bg-zinc-900 rounded-xl p-5 border border-zinc-800">
              <p className="text-xs text-zinc-500 mb-2">You asked</p>
              <p className="text-zinc-100">{result.prompt}</p>
            </div>

            {/* Consensus (V1: simple) */}
            {result.consensus && (
              <div className="bg-violet-950/30 rounded-xl p-5 border border-violet-800/30">
                <div className="flex items-center gap-2 mb-3">
                  <span className="text-violet-400">⬡</span>
                  <h3 className="font-medium text-violet-300">Consensus</h3>
                  <span className="text-xs px-2 py-0.5 rounded-full bg-violet-900/50 text-violet-400">
                    {Math.round(result.consensus.confidence * 100)}% confidence
                  </span>
                </div>
                <p className="text-zinc-300 text-sm leading-relaxed">
                  {result.consensus.synthesis}
                </p>
              </div>
            )}

            {/* Provider Responses */}
            <div>
              <h3 className="text-sm font-medium text-zinc-400 mb-3">
                Provider Responses ({result.responses.length})
              </h3>
              <div className="grid gap-3">
                {result.responses.map((r) => (
                  <button
                    key={r.provider_id}
                    onClick={() => onSelectProvider(r)}
                    className="text-left bg-zinc-900/50 rounded-lg p-4 border border-zinc-800 hover:border-zinc-700 transition-colors"
                  >
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-zinc-200">
                          {r.provider_id}
                        </span>
                        <span className="text-xs text-zinc-600">{r.model}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        {r.error ? (
                          <span className="text-xs px-2 py-0.5 rounded-full bg-red-900/30 text-red-400">
                            error
                          </span>
                        ) : (
                          <>
                            <span className="text-xs px-2 py-0.5 rounded-full bg-zinc-800 text-zinc-400">
                              {r.latency_ms.toFixed(0)}ms
                            </span>
                            <span className="text-xs px-2 py-0.5 rounded-full bg-zinc-800 text-zinc-400">
                              {r.token_count} tokens
                            </span>
                          </>
                        )}
                      </div>
                    </div>
                    <p className="text-sm text-zinc-400 line-clamp-2">
                      {r.error || r.content}
                    </p>
                  </button>
                ))}
              </div>
            </div>

            {/* Total Latency */}
            <p className="text-xs text-zinc-600 text-center">
              Total round-trip: {result.total_latency_ms.toFixed(0)}ms
            </p>
          </div>
        )}
      </div>

      {/* Input Area */}
      <div className="border-t border-zinc-800 p-4">
        <form onSubmit={handleSubmit} className="max-w-3xl mx-auto">
          <div className="flex gap-3">
            <input
              type="text"
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="Ask the collective intelligence..."
              className="flex-1 bg-zinc-900 border border-zinc-700 rounded-lg px-4 py-3 text-sm text-zinc-100 placeholder-zinc-600 focus:outline-none focus:border-violet-600 transition-colors"
              disabled={isLoading}
            />
            <button
              type="submit"
              disabled={isLoading || !prompt.trim()}
              className="px-5 py-3 bg-violet-600 hover:bg-violet-700 disabled:bg-zinc-800 disabled:text-zinc-600 rounded-lg text-sm font-medium transition-colors"
            >
              {isLoading ? "Thinking..." : "Ask"}
            </button>
          </div>
        </form>
      </div>
    </main>
  );
}
