import React from "react";
import ReactDOM from "react-dom/client";
import { ArrowUpRight, Clock, LocateFixed, MapPin, Search, SlidersHorizontal, Sparkles, Wifi, Zap } from "lucide-react";
import "./styles.css";

type Intent = {
  activity: string;
  budget_max: number | null;
  duration_hours: number | null;
  max_minutes: number | null;
  quiet: boolean;
  wifi: boolean;
  power: boolean;
  open_now: boolean;
  romantic: boolean;
  cheap: boolean;
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
};

type SearchResponse = {
  search_id: string;
  intent: Intent;
  results: Result[];
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
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  async function runSearch(nextQuery = query) {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch("http://127.0.0.1:8000/api/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query: nextQuery,
          location: { lat: 6.52, lng: 3.37 },
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
    intent.budget_max ? `₦${intent.budget_max.toLocaleString()} max` : null,
    intent.duration_hours ? `${intent.duration_hours} hrs` : null,
    intent.max_minutes ? `within ${intent.max_minutes} min` : null,
    intent.quiet ? "quiet" : null,
    intent.wifi ? "Wi-Fi" : null,
    intent.power ? "power" : null,
    intent.romantic ? "romantic" : null,
    intent.open_now ? "open now" : null,
  ].filter(Boolean);

  return (
    <div className="pills">
      {pills.map((pill) => (
        <span key={pill}>{pill}</span>
      ))}
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
        <div>
          <p className="meta">{result.category} • {result.area}</p>
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

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
