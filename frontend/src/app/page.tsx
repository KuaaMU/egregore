"use client";

import { useState } from "react";
import { ConversationSidebar } from "@/components/ConversationSidebar";
import { RoundTableView } from "@/components/RoundTableView";
import { ProviderPanel } from "@/components/ProviderPanel";
import type { RoundTableResult, ProviderResponse } from "@/types";

export default function Home() {
  const [result, setResult] = useState<RoundTableResult | null>(null);
  const [selectedProvider, setSelectedProvider] = useState<ProviderResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [history, setHistory] = useState<Array<{ id: string; prompt: string; timestamp: Date }>>([]);

  const handleSubmit = async (prompt: string) => {
    setIsLoading(true);
    try {
      const res = await fetch("http://localhost:8000/api/chat/round-table", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt }),
      });
      const data: RoundTableResult = await res.json();
      setResult(data);
      setSelectedProvider(null);
      setHistory((prev) => [
        { id: data.id, prompt: data.prompt, timestamp: new Date() },
        ...prev,
      ]);
    } catch (err) {
      console.error("Failed to fetch:", err);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Left: Conversation History */}
      <ConversationSidebar
        history={history}
        onSelect={(id) => {
          // Future: load conversation by id
        }}
      />

      {/* Middle: Main Round Table View */}
      <RoundTableView
        result={result}
        isLoading={isLoading}
        onSubmit={handleSubmit}
        onSelectProvider={setSelectedProvider}
      />

      {/* Right: Provider Detail Panel */}
      <ProviderPanel
        provider={selectedProvider}
        onClose={() => setSelectedProvider(null)}
      />
    </div>
  );
}
