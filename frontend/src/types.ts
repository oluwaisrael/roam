export type Intent = {
  activity: string;
  area: string | null;
  place_types: string[];
  budget_max: number | null;
  duration_hours: number | null;
  max_minutes: number | null;
  quiet: boolean;
  wifi: boolean;
  power: boolean;
  open_now: boolean;
  romantic: boolean;
  cheap: boolean;
  must_have: string[];
  avoid: string[];
  priority: string[];
  interpretation: string;
};

export type Place = {
  place_id: string;
  name: string;
  category: string;
  area: string;
  score: number;
  rating: number | null;
  typical_spend: number;
  distance_km: number | null;
  travel_minutes: number | null;
  open_now: boolean | null;
  match_reasons: string[];
  tradeoffs: string[];
  tags: string[];
  data_source: string;
  photo_url: string | null;
  photo_page_url: string | null;
  maps_url: string;
  photos_url: string;
  evidence: { label: string; value: string; status: string }[];
};

export type SearchResponse = {
  search_id: string;
  intent: Intent;
  intelligence: {
    headline: string;
    summary: string;
    confidence: string;
    primary_tradeoff: string;
    next_best_action: string;
    caveats: string[];
  };
  results: Place[];
  engine: "ai" | "rules";
  engine_status: string;
  suggestions: string[];
  clarification: string | null;
  data_status: "live" | "demo" | "unavailable";
};

export type Location = { lat: number; lng: number };
export type Change = Partial<Pick<Intent, "budget_max" | "max_minutes" | "quiet" | "wifi" | "power" | "open_now" | "priority">>;
