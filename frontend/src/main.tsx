import React from "react";
import ReactDOM from "react-dom/client";
import { ArrowUpRight, Camera, Clock, LocateFixed, MapPin, Search, SlidersHorizontal, Sparkles, Wifi, Zap } from "lucide-react";
import "./styles.css";

type Intent = {
  activity: string;
  place_types: string[];
  area: string | null;
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
  raw_terms: string[];
};

type Result = {
  place_id: string;
  name: string;
  category: string;
  area: string;
  score: number;
  rating: number;
  price_level: number;
  typical_spend: number;
  distance_km: number | null;
  travel_minutes: number | null;
  open_now: boolean;
  match_reasons: string[];
  tradeoffs: string[];
  tags: string[];
  data_source: string;
  photo_url: string | null;
  photo_page_url: string | null;
};

type DecisionInsight = {
  headline: string;
  summary: string;
  confidence: "high" | "medium" | "low";
  primary_tradeoff: string;
  next_best_action: string;
  caveats: string[];
};

type SearchResponse = {
  search_id: string;
  intent: Intent;
  intelligence: DecisionInsight;
  results: Result[];
};

type UserLocation = {
  lat: number;
  lng: number;
};

const examples = [
  "Quiet place to work for 4 hours under ₦10k with Wi-Fi",
  "Date spot tonight around Lekki under ₦30k",
  "Somewhere peaceful to read near me",
  "Closest affordable coffee with power",
];

function App() {
  const [query, setQuery] = React.useState(examples[0]);
  const [data, setData] = React.useState<SearchResponse | null>(null);
  const [userLocation, setUserLocation] = React.useState<UserLocation | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const searchLocation = userLocation ?? { lat: 6.52, lng: 3.37 };

  async function runSearch(nextQuery = query, location = searchLocation) {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch("http://127.0.0.1:8000/api/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query: nextQuery,
          location,
        }),
      });
      if (!response.ok) throw new Error("Roam could not complete that search.");
      setData(await response.json());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }

  async function refine(change: Partial<Intent>) {
    if (!data) return;
    setLoading(true);
    setError(null);
    try {
      const response = await fetch("http://127.0.0.1:8000/api/search/refine", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ search_id: data.search_id, change }),
      });
      if (!response.ok) throw new Error("Roam could not refine that search.");
      setData(await response.json());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }

  React.useEffect(() => {
    runSearch(examples[0]);
  }, []);

  function useCurrentLocation() {
    if (!navigator.geolocation) {
      setError("Location is not available in this browser.");
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (position) => {
        const nextLocation = {
          lat: position.coords.latitude,
          lng: position.coords.longitude,
        };
        setUserLocation(nextLocation);
        runSearch(query, nextLocation);
      },
      () => setError("Roam could not access your location."),
      { enableHighAccuracy: false, timeout: 8000, maximumAge: 300000 },
    );
  }

  return (
    <main className="shell">
      <section className="search-panel" aria-label="Roam search">
        <div className="brand">
          <span className="brand-mark"><MapPin size={18} /></span>
          <span>Roam</span>
        </div>
        <div className="prompt">
          <p className="eyebrow">Real-world decisions, explained</p>
          <h1>What are you looking for?</h1>
        </div>
        <form
          className="search-box"
          onSubmit={(event) => {
            event.preventDefault();
            runSearch();
          }}
        >
          <Search size={21} aria-hidden="true" />
          <input value={query} onChange={(event) => setQuery(event.target.value)} aria-label="Search places" />
          <button type="button" className={userLocation ? "located" : ""} onClick={useCurrentLocation} aria-label="Use current location">
            <LocateFixed size={18} />
          </button>
          <button type="submit" disabled={loading}>
            <ArrowUpRight size={18} />
          </button>
        </form>
        <div className="examples" aria-label="Example searches">
          {examples.map((example) => (
            <button
              type="button"
              key={example}
              onClick={() => {
                setQuery(example);
                runSearch(example);
              }}
            >
              {example}
            </button>
          ))}
        </div>
      </section>

      {error && <p className="error">{error}</p>}

      {data && (
        <section className="decision-grid">
          <aside className="understanding" aria-label="Interpreted request">
            <div className="panel-heading">
              <Sparkles size={18} />
              <h2>Roam understood</h2>
            </div>
            <IntentPills intent={data.intent} />
            <InsightPanel insight={data.intelligence} />
            <div className="what-if">
              <div className="panel-heading">
                <SlidersHorizontal size={18} />
                <h2>What if</h2>
              </div>
              <button onClick={() => refine({ budget_max: 20000 })}>Budget becomes ₦20k</button>
              <button onClick={() => refine({ max_minutes: 10 })}>Distance matters more</button>
              <button onClick={() => refine({ wifi: false })}>Wi-Fi does not matter</button>
            </div>
          </aside>

          <section className="results" aria-label="Recommended places">
            <div className="results-header">
              <div>
                <p className="eyebrow">{loading ? "Recalculating" : "Best fits"}</p>
                <h2>{data.results.length} places worth considering</h2>
              </div>
              <div className="mini-map" aria-hidden="true">
                <span />
                <span />
                <span />
              </div>
            </div>
            <div className="cards">
              {data.results.map((result, index) => (
                <PlaceCard key={result.place_id} result={result} index={index} />
              ))}
            </div>
          </section>
        </section>
      )}
    </main>
  );
}

function IntentPills({ intent }: { intent: Intent }) {
  const pills = [
    intent.activity.replace("_", " "),
    intent.place_types.length ? intent.place_types.join(" / ") : null,
    intent.area ? `around ${intent.area}` : null,
    intent.budget_max ? `₦${intent.budget_max.toLocaleString()} max` : null,
    intent.duration_hours ? `${intent.duration_hours} hrs` : null,
    intent.max_minutes ? `within ${intent.max_minutes} min` : null,
    intent.quiet ? "quiet" : null,
    intent.wifi ? "Wi-Fi" : null,
    intent.power ? "power" : null,
    intent.romantic ? "romantic" : null,
    intent.open_now ? "open now" : null,
    intent.avoid.length ? `avoid ${intent.avoid.join(", ")}` : null,
    intent.priority.length ? `prioritize ${intent.priority.join(", ")}` : null,
  ].filter(Boolean);

  return (
    <>
      {intent.interpretation && <p className="interpretation">{intent.interpretation}</p>}
      <div className="pills">
        {pills.map((pill) => (
          <span key={pill}>{pill}</span>
        ))}
      </div>
    </>
  );
}

function InsightPanel({ insight }: { insight: DecisionInsight }) {
  return (
    <div className="insight">
      <p className="confidence">{insight.confidence} confidence</p>
      <h3>{insight.headline}</h3>
      <p>{insight.summary}</p>
      <div className="insight-detail">
        <strong>Tradeoff</strong>
        <span>{insight.primary_tradeoff}</span>
      </div>
      <div className="insight-detail">
        <strong>Next</strong>
        <span>{insight.next_best_action}</span>
      </div>
      {insight.caveats.length > 0 && (
        <ul className="caveats">
          {insight.caveats.map((caveat) => <li key={caveat}>{caveat}</li>)}
        </ul>
      )}
    </div>
  );
}

function PlaceCard({ result, index }: { result: Result; index: number }) {
  return (
    <article className={index === 0 ? "place-card featured" : "place-card"}>
      <div className="score">
        <strong>{result.score}%</strong>
        <span>match</span>
      </div>
      <div className="place-main">
        <PlacePhoto result={result} />
        <div>
          <p className="meta">{result.category} • {result.area} • {result.data_source}</p>
          <h3>{result.name}</h3>
        </div>
        <div className="place-facts">
          <span><Clock size={15} />{result.travel_minutes ? `${result.travel_minutes} min` : "Nearby"}</span>
          <span>{Array.from({ length: result.price_level }, () => "₦").join("")}</span>
          {result.tags.includes("wifi") && <span><Wifi size={15} />Wi-Fi</span>}
          {result.tags.includes("power") && <span><Zap size={15} />Power</span>}
        </div>
        <div className="reasoning">
          <div>
            <h4>Why Roam picked it</h4>
            <ul>
              {result.match_reasons.map((reason) => <li key={reason}>{reason}</li>)}
            </ul>
          </div>
          <div>
            <h4>Tradeoff</h4>
            <ul>
              {result.tradeoffs.map((tradeoff) => <li key={tradeoff}>{tradeoff}</li>)}
            </ul>
          </div>
        </div>
      </div>
    </article>
  );
}

function PlacePhoto({ result }: { result: Result }) {
  if (result.photo_url) {
    return (
      <a className="place-photo" href={result.photo_page_url ?? result.photo_url} target="_blank" rel="noreferrer" aria-label={`Open picture source for ${result.name}`}>
        <img src={result.photo_url} alt={result.name} loading="lazy" />
      </a>
    );
  }

  if (result.photo_page_url) {
    return (
      <a className="photo-link" href={result.photo_page_url} target="_blank" rel="noreferrer">
        <Camera size={16} />
        Picture source
      </a>
    );
  }

  return (
    <div className="photo-empty">
      <Camera size={16} />
      No verified picture yet
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
