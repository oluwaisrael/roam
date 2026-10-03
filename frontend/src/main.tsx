import React from "react";
import ReactDOM from "react-dom/client";
import { ArrowRight, ArrowUp, ArrowUpRight, Bookmark, Check, ChevronDown, Coffee, Compass, GitCompareArrows, Heart, History, Leaf, LoaderCircle, LocateFixed, MapPin, Moon, Plus, RotateCcw, Search, SlidersHorizontal, Sparkles, Sun, Wifi, X, Zap } from "lucide-react";
import { Comparison, Modal, PlaceCard, money } from "./components";
import { searchApi } from "./api";
import { readStored, writeStored } from "./storage";
import type { Change, Location, Place, SearchResponse } from "./types";
import "./styles.css";

const areas = ["Lagos", "Yaba", "Victoria Island", "Ikoyi", "Lekki Phase 1", "Lekki", "Ikeja", "Surulere", "Ajah", "Lagos Island", "Marina"];
const moods = [
  { title: "A little focus", subtitle: "Coffee & a change of workspace", icon: Coffee, image: "coffee", query: "A quiet cafe to work for 3 hours under ₦10k with Wi-Fi and power" },
  { title: "Make an evening", subtitle: "Dinner, drinks & good company", icon: Heart, image: "dinner", query: "A romantic restaurant for a date under ₦30k, not too noisy" },
  { title: "Room to breathe", subtitle: "Green spaces & slower afternoons", icon: Leaf, image: "nature", query: "A peaceful park where I can read and unwind" },
];
const defaultQuery = "";

function App() {
  const [theme, setTheme] = React.useState<"light" | "dark">(() => readStored("roam-theme", matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"));
  const [view, setView] = React.useState<"explore" | "saved">("explore");
  const [query, setQuery] = React.useState(defaultQuery);
  const [followup, setFollowup] = React.useState("");
  const [area, setArea] = React.useState("Lagos");
  const [location, setLocation] = React.useState<Location | null>(null);
  const [locating, setLocating] = React.useState(false);
  const [data, setData] = React.useState<SearchResponse | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [loadingStep, setLoadingStep] = React.useState(0);
  const [error, setError] = React.useState<string | null>(null);
  const [notice, setNotice] = React.useState("");
  const [saved, setSaved] = React.useState<Place[]>(() => { const value = readStored<Place[]>("roam-saved-v2", []); return Array.isArray(value) ? value.filter(p => p && typeof p.place_id === "string" && typeof p.name === "string" && Array.isArray(p.evidence)) : []; });
  const [recent, setRecent] = React.useState<string[]>(() => { const value = readStored<string[]>("roam-recent", []); return Array.isArray(value) ? value.filter(q => typeof q === "string").slice(0, 5) : []; });
  const [compare, setCompare] = React.useState<Place[]>([]);
  const [showCompare, setShowCompare] = React.useState(false);
  const [showFilters, setShowFilters] = React.useState(false);
  const [showEvidence, setShowEvidence] = React.useState(false);
  const [sort, setSort] = React.useState("fit");
  const controller = React.useRef<AbortController | null>(null);
  const input = React.useRef<HTMLTextAreaElement>(null);

  React.useEffect(() => { document.documentElement.dataset.theme = theme; writeStored("roam-theme", theme); document.querySelector('meta[name="theme-color"]')?.setAttribute("content", theme === "dark" ? "#161817" : "#fafbf9"); }, [theme]);
  React.useEffect(() => { writeStored("roam-saved-v2", saved); }, [saved]);
  React.useEffect(() => { writeStored("roam-recent", recent); }, [recent]);
  React.useEffect(() => () => controller.current?.abort(), []);
  React.useEffect(() => { if (!notice) return; const timer = setTimeout(() => setNotice(""), 3500); return () => clearTimeout(timer); }, [notice]);
  React.useEffect(() => { if (!loading) return; setLoadingStep(0); const timer = setInterval(() => setLoadingStep(step => Math.min(step + 1, 2)), 6500); return () => clearInterval(timer); }, [loading]);

  async function requestSearch(nextQuery: string, options: { refine?: boolean; change?: Change; location?: Location } = {}) {
    if (!options.change && nextQuery.trim().length < 2) { input.current?.focus(); return; }
    controller.current?.abort();
    const active = new AbortController();
    controller.current = active;
    const timeout = setTimeout(() => active.abort("timeout"), 65000);
    setLoading(true); setError(null); setView("explore");
    const refining = options.refine && data;
    // A named area in the prompt always takes precedence over the location picker.
    const namedArea = areas.some(a => a !== "Lagos" && nextQuery.toLowerCase().includes(a.toLowerCase())) || /\bvi\b/i.test(nextQuery);
    const scopedQuery = !namedArea && area !== "Lagos" ? `${nextQuery} around ${area}` : nextQuery;
    try {
      const response = await searchApi(refining ? "search/refine" : "search", refining
        ? { search_id: data.search_id, ...(options.change ? { change: options.change } : { query: nextQuery.trim() }) }
        : { query: scopedQuery.trim().slice(0, 280), location: options.location ?? location }, active.signal);
      if (controller.current !== active) return;
      setData(response); setCompare([]); setSort("fit"); setFollowup("");
      if (!refining) { setQuery(nextQuery); setRecent(items => [nextQuery, ...items.filter(item => item !== nextQuery)].slice(0, 5)); }
    } catch (err) {
      if (controller.current !== active) return;
      if (active.signal.aborted && active.signal.reason !== "timeout") return;
      setError(active.signal.reason === "timeout" ? "This search is taking too long. Please try again." : err instanceof TypeError ? "Couldn't reach Roam. Check your connection and try again." : err instanceof Error ? err.message : "Something went wrong. Please try again.");
    } finally {
      clearTimeout(timeout);
      if (controller.current === active) setLoading(false);
    }
  }

  function getLocation() {
    if (!navigator.geolocation) { setError("Location isn't supported by this browser. Choose a neighbourhood instead."); return; }
    setLocating(true);
    navigator.geolocation.getCurrentPosition(position => { setLocation({ lat: position.coords.latitude, lng: position.coords.longitude }); setArea("Lagos"); setLocating(false); setNotice("Current location selected for your next search"); }, () => { setLocating(false); setError("Location access is unavailable. Choose a neighbourhood instead."); }, { timeout: 8000, maximumAge: 300000 });
  }

  function toggleSave(place: Place) {
    const exists = saved.some(item => item.place_id === place.place_id);
    setSaved(items => exists ? items.filter(item => item.place_id !== place.place_id) : [place, ...items].slice(0, 100));
    setNotice(exists ? "Removed from saved places" : "Added to your saved places");
  }

  function toggleCompare(place: Place) {
    if (compare.some(p => p.place_id === place.place_id)) setCompare(items => items.filter(p => p.place_id !== place.place_id));
    else if (compare.length < 3) setCompare(items => [...items, place]);
    else setNotice("You can compare up to 3 places at a time");
  }

  function reset() { controller.current?.abort(); controller.current = null; setLoading(false); setData(null); setQuery(""); setError(null); setCompare([]); setView("explore"); input.current?.focus(); }
  const results = [...(view === "saved" ? saved : data?.results || [])].sort((a, b) => sort === "budget" ? a.typical_spend - b.typical_spend : sort === "distance" ? (a.distance_km ?? Infinity) - (b.distance_km ?? Infinity) : b.score - a.score);
  const nav = <><button className={view === "explore" ? "nav-item active" : "nav-item"} onClick={() => setView("explore")}><Compass size={19} /><span>Explore</span></button><button className={view === "saved" ? "nav-item active" : "nav-item"} onClick={() => setView("saved")}><Bookmark size={18} /><span>Saved</span>{saved.length > 0 && <span className="nav-count">{saved.length}</span>}</button></>;

  return <>
    <a className="skip-link" href="#main">Skip to content</a>
    <header className="site-header"><div className="header-inner"><button className="brand" aria-label="Roam home" onClick={reset}><span className="brand-icon"><Compass size={22} strokeWidth={2.2} /></span>roam<span className="brand-period">.</span></button><nav className="desktop-nav" aria-label="Main navigation">{nav}</nav><div className="header-tools"><div className="location-picker"><MapPin size={15} /><select aria-label="Search neighbourhood" value={area} onChange={event => { setArea(event.target.value); setLocation(null); }}>{areas.map(a => <option key={a}>{a}</option>)}</select><ChevronDown size={13} /></div><button className="icon-button theme-button" onClick={() => setTheme(theme === "light" ? "dark" : "light")} title={`Switch to ${theme === "light" ? "dark" : "light"} mode`} aria-label={`Switch to ${theme === "light" ? "dark" : "light"} mode`}>{theme === "light" ? <Moon size={19} /> : <Sun size={19} />}</button></div></div></header>
    <main id="main" className="shell">
      {view === "explore" && <>
        <section className={`search-section ${data ? "has-results" : ""}`} aria-label="Place search">
          <div className="intro"><p className="eyebrow"><span className="small-dot" /> A little local discovery</p><h1>What’s the plan?</h1><p>Somewhere to focus. Someone to take out. A new favourite.</p></div>
          <form className="search-box" onSubmit={event => { event.preventDefault(); requestSearch(query); }}><div className="search-input-row"><Sparkles size={21} /><textarea ref={input} value={query} maxLength={250} rows={2} onChange={event => setQuery(event.target.value)} placeholder="A quiet cafe with good Wi-Fi, under ₦10k…" aria-label="What are you looking for?" onKeyDown={event => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); requestSearch(query); } }} /></div><div className="search-bottom"><button type="button" className={`location-button ${location ? "active" : ""}`} onClick={getLocation} disabled={locating}>{locating ? <LoaderCircle size={15} className="spin" /> : <LocateFixed size={15} />}<span>{locating ? "Finding you…" : location ? "Near you" : "Use my location"}</span></button><button className="search-submit" type="submit" disabled={loading || query.trim().length < 2}>{loading ? <LoaderCircle size={17} className="spin" /> : <><span>Find my place</span><ArrowRight size={17} /></>}</button></div></form>
          {!data && <div className="quick-prompts">{[{ icon: Coffee, label: "Coffee nearby", query: "Coffee near me" }, { icon: Heart, label: "Date night", query: moods[1].query }, { icon: Wifi, label: "Work & Wi-Fi", query: moods[0].query }, { icon: Leaf, label: "Somewhere quiet", query: "Somewhere peaceful to read" }].map(p => <button key={p.label} disabled={loading} onClick={() => requestSearch(p.query)}><p.icon size={15} />{p.label}</button>)}</div>}
        </section>
        {error && <div className="error-banner" role="alert"><span>{error}</span><button className="icon-button" aria-label="Dismiss error" onClick={() => setError(null)}><X size={17} /></button></div>}
        {loading && <div className="loading-state" role="status"><LoaderCircle size={20} className="spin" /><div><strong>{["Making sense of your plans", "Looking for places that fit", "Still checking live availability"][loadingStep]}</strong><span>{data ? "Keeping your preferences in mind" : "Good places are worth a moment"}</span></div><button className="icon-button" title="Cancel search" aria-label="Cancel search" onClick={() => { controller.current?.abort(); controller.current = null; setLoading(false); }}><X size={18} /></button></div>}
        {!data && !loading && <section className="discovery"><div className="section-heading"><div><p className="eyebrow">Follow your mood</p><h2>A change of scene.</h2></div><span className="subtle">Lagos, at your pace</span></div><div className="mood-grid">{moods.map(mood => <button className="mood-card" key={mood.title} onClick={() => requestSearch(mood.query)}><img src={`/images/${mood.image}.jpg`} alt="" /><span className="mood-content"><mood.icon size={20} /><strong>{mood.title}</strong><span>{mood.subtitle}</span></span><ArrowUpRight size={21} className="mood-arrow" /></button>)}</div>{recent.length > 0 && <div className="recent-searches"><p className="eyebrow"><History size={14} /> Recent searches</p>{recent.slice(0, 3).map(q => <button key={q} onClick={() => requestSearch(q)}><span>{q}</span><ArrowUpRight size={15} /></button>)}</div>}<div className="neighbourhoods"><span>Around the corner</span>{["Yaba", "Victoria Island", "Ikoyi", "Lekki Phase 1"].map(a => <button key={a} onClick={() => { setArea(a); requestSearch(`Cafes around ${a}`); }}>{a}<ArrowUpRight size={13} /></button>)}</div></section>}
        {data && <div className="decision-layout" aria-busy={loading}>
          <aside className="decision-aside"><div className="insight-heading"><span className="ai-mark"><Sparkles size={18} /></span><div><h2>The Roam take</h2><span>{data.engine_status}</span></div></div><p className="insight-summary">{data.intelligence.summary}</p><div className="intent-pills">{[data.intent.area, data.intent.budget_max !== null ? `${money(data.intent.budget_max)} max` : null, data.intent.duration_hours ? `${data.intent.duration_hours} hours` : null, ...data.intent.must_have.map(p => p === "wifi" ? "Wi-Fi" : p.replace(/_/g, " ")), data.intent.max_minutes ? `within ${data.intent.max_minutes} min` : null].filter(Boolean).map((p, i) => <span key={`${p}-${i}`}>{p}</span>)}</div><button className="evidence-button" onClick={() => setShowEvidence(true)}><span className="evidence-dot" />{data.intelligence.confidence === "low" ? "Limited evidence" : "About these recommendations"}<ArrowUpRight size={14} /></button>{data.clarification && <p className="clarification">{data.clarification}</p>}<div className="followup-section"><h3>A change of plan?</h3><div className="refine-prompts">{["Find somewhere closer", "Show me cheaper options", data.intent.wifi ? "Wi-Fi doesn't matter" : "Make it quieter"].map(q => <button key={q} disabled={loading} onClick={() => requestSearch(q, { refine: true })}><Plus size={14} />{q}</button>)}</div><form className="followup-box" onSubmit={event => { event.preventDefault(); requestSearch(followup, { refine: true }); }}><input value={followup} maxLength={280} onChange={e => setFollowup(e.target.value)} aria-label="Refine your search" placeholder="What if my budget is ₦20k?" /><button className="icon-button" aria-label="Apply follow-up" disabled={loading || followup.trim().length < 2}><ArrowUp size={18} /></button></form></div><button className="text-button new-search" onClick={reset}><RotateCcw size={14} /> Start fresh</button></aside>
          <section className="results-section" aria-label="Recommended places"><div className="section-heading result-heading"><div><p className="eyebrow">{data.data_status === "demo" ? "Demo results" : "Your shortlist"}</p><h2>{data.results.length ? `${data.results.length} places, picked for you.` : "A little further afield?"}</h2></div><button className="icon-button filter-button" title="Adjust preferences" aria-label="Adjust preferences" onClick={() => setShowFilters(true)} disabled={loading}><SlidersHorizontal size={19} /></button></div>{data.results.length > 0 && <div className="results-subheading"><span>{data.intent.area || (location ? "Near your location" : "Around Lagos")}</span><label>Sort by <select aria-label="Sort places" value={sort} onChange={e => setSort(e.target.value)}><option value="fit">Best fit</option><option value="budget">Lowest estimate</option><option value="distance">Nearest</option></select></label></div>}{data.results.length ? <div className="cards">{results.map((place, index) => <PlaceCard key={place.place_id} place={place} index={index} saved={saved.some(p => p.place_id === place.place_id)} selected={compare.some(p => p.place_id === place.place_id)} onSave={() => toggleSave(place)} onCompare={() => toggleCompare(place)} />)}</div> : <div className="empty-state"><MapPin size={30} /><h3>No live places found this time.</h3><p>Try another Lagos neighbourhood or search again in a moment.</p><button className="primary-button" onClick={() => requestSearch(query)} disabled={loading}>Try again<ArrowRight size={16} /></button></div>}<p className="results-footnote">Place data © OpenStreetMap contributors. Spend and fit scores are estimates.</p></section>
        </div>}
      </>}
      {view === "saved" && <section className="saved-section"><div className="section-heading"><div><p className="eyebrow">Good places, kept close</p><h1>Your saved places<span className="accent-period">.</span></h1></div><span className="saved-total">{saved.length}</span></div>{saved.length ? <><p className="saved-caption">Your personal shortlist, saved on this device.</p><div className="cards saved-grid">{results.map((place, index) => <PlaceCard key={place.place_id} place={place} index={index} saved selected={compare.some(p => p.place_id === place.place_id)} onSave={() => toggleSave(place)} onCompare={() => toggleCompare(place)} />)}</div></> : <div className="empty-state"><Bookmark size={32} /><h2>A few favourites in the making.</h2><button className="primary-button" onClick={() => setView("explore")}>Find a place<ArrowRight size={16} /></button></div>}</section>}
      <footer className="site-footer"><span>roam. <span>A good place to start.</span></span><span><span className="small-dot" /> Made for the real world</span></footer>
    </main>
    {compare.length > 0 && <div className="compare-tray"><span><GitCompareArrows size={18} /><strong>{compare.length}</strong> selected</span><button className="primary-button" disabled={compare.length < 2} onClick={() => setShowCompare(true)}>Compare<ArrowRight size={15} /></button><button className="icon-button" aria-label="Clear comparison" onClick={() => setCompare([])}><X size={17} /></button></div>}
    <nav className="mobile-nav" aria-label="Mobile navigation">{nav}<button className="nav-item" onClick={() => setTheme(theme === "light" ? "dark" : "light")} aria-label={`Switch to ${theme === "light" ? "dark" : "light"} mode`}>{theme === "light" ? <Moon size={19} /> : <Sun size={19} />}<span>{theme === "light" ? "Dark mode" : "Light mode"}</span></button></nav>
    {notice && <div className="toast" role="status"><Check size={16} />{notice}</div>}
    {showCompare && <Comparison places={compare} onClose={() => setShowCompare(false)} />}
    {showEvidence && data && <Modal title="Behind your recommendations" onClose={() => setShowEvidence(false)}><p className="modal-note">{data.engine_status}. The fit score reflects your preferences and the available place data.</p>{data.intelligence.caveats.map(c => <p className="evidence-paragraph" key={c}>{c}</p>)}<p className="evidence-paragraph"><strong>Before you go</strong>{data.intelligence.next_best_action}</p></Modal>}
    {showFilters && data && <Filters data={data} onClose={() => setShowFilters(false)} onApply={change => { setShowFilters(false); requestSearch("", { refine: true, change }); }} />}
  </>;
}

function Filters({ data, onClose, onApply }: { data: SearchResponse; onClose: () => void; onApply: (change: Change) => void }) {
  const [budget, setBudget] = React.useState(data.intent.budget_max?.toString() || "");
  const [minutes, setMinutes] = React.useState(data.intent.max_minutes?.toString() || "");
  const [quiet, setQuiet] = React.useState(data.intent.quiet);
  const [wifi, setWifi] = React.useState(data.intent.wifi);
  const [power, setPower] = React.useState(data.intent.power);
  return <Modal title="What matters to you" onClose={onClose}><form className="filter-form" onSubmit={event => { event.preventDefault(); onApply({ budget_max: budget === "" ? null : Number(budget), max_minutes: minutes === "" ? null : Number(minutes), quiet, wifi, power }); }}><label>Budget per person<span className="field-input"><span>₦</span><input type="number" min="0" max="10000000" step="500" value={budget} onChange={e => setBudget(e.target.value)} placeholder="No limit" /></span></label><label>Travel time preference<span className="field-input"><input type="number" min="1" max="240" value={minutes} onChange={e => setMinutes(e.target.value)} placeholder="No limit" /><span>min</span></span></label><div className="filter-switches">{[{ label: "A quieter space", icon: Leaf, checked: quiet, set: setQuiet }, { label: "Wi-Fi", icon: Wifi, checked: wifi, set: setWifi }, { label: "Power access", icon: Zap, checked: power, set: setPower }].map(item => <label key={item.label}><span><item.icon size={18} />{item.label}</span><input type="checkbox" role="switch" checked={item.checked} onChange={event => item.set(event.target.checked)} /></label>)}</div><button className="primary-button" type="submit">Update my places<ArrowRight size={16} /></button></form></Modal>;
}

ReactDOM.createRoot(document.getElementById("root")!).render(<React.StrictMode><App /></React.StrictMode>);
