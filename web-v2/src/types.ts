// Shared backend shapes (subset used by the UI).
export interface Listing {
  id: string;
  source: string;
  native_id?: string;
  url?: string;
  title?: string;
  description?: string;
  price?: number | null;
  currency?: string;
  images?: string[];
  location?: string;
  distance_km?: number | null;
  seller?: { name?: string };
  pickup_available?: boolean;
  shipping_available?: boolean;
  attributes?: Record<string, unknown>;
}
export interface Scored {
  listing: Listing;
  final_score?: number;
  match_score?: number;
  lane?: string;
  risk?: { score: number; severity?: string };
  why?: string[];
  enrichments?: { field: string; value: number }[];
  deal_dna?: Record<string, number>;
}
export interface JobState {
  done: number;
  total: number | string;
  detail: string;
  label: string;
  control?: string;
}
export interface SearchResult {
  id: string;
  status: string;
  results: Scored[];
  filtered?: Scored[];
  filtered_out?: number;
  median?: number | null;
  driver_errors?: Record<string, string>;
  subqueries?: string[];
  parsed?: Record<string, unknown>;
  error?: string;
  partial?: { results: Scored[]; filtered?: Scored[]; n_results: number };
  control?: string;
  detail?: string;
  done?: number;
  total?: number | string;
}
export interface Category { label: string; id: string; slug?: string; param?: string }
