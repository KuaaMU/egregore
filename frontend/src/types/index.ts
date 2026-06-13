export interface ProviderResponse {
  provider_id: string;
  model: string;
  content: string;
  latency_ms: number;
  token_count: number;
  error: string | null;
}

export interface Consensus {
  common_points: string[];
  differences: string[];
  synthesis: string;
  confidence: number;
}

export interface RoundTableResult {
  id: string;
  prompt: string;
  responses: ProviderResponse[];
  consensus: Consensus | null;
  total_latency_ms: number;
}
