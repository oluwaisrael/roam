import React from "react";
import { ArrowUpRight, Bookmark, Check, ChevronDown, Coffee, ExternalLink, GitCompareArrows, Image, MapPin, Navigation, X } from "lucide-react";
import type { Place } from "./types";

export const money = (amount: number) => `₦${amount.toLocaleString("en-NG")}`;
export const safeUrl = (url: string | null | undefined) => url && /^https?:\/\//i.test(url) ? url : undefined;

export function PlaceCard({ place, index, saved, selected, onSave, onCompare }: {
  place: Place; index: number; saved: boolean; selected: boolean;
  onSave: () => void; onCompare: () => void;
}) {
  const [imageFailed, setImageFailed] = React.useState(false);
  const photo = safeUrl(place.photo_url);
  const map = safeUrl(place.maps_url) || `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(`${place.name} ${place.area} Lagos`)}`;
  const photos = safeUrl(place.photos_url) || `https://www.google.com/search?tbm=isch&q=${encodeURIComponent(`${place.name} ${place.area} Lagos`)}`;
  return <article className={`place-card ${selected ? "selected" : ""}`}>
    <div className="place-topline">
      <span className={index === 0 ? "rank first" : "rank"}>{index === 0 ? <><span className="small-dot" /> Top fit</> : `0${index + 1}`}</span>
      <span className="source">{place.data_source === "seed" ? "Demo place" : "OpenStreetMap"}</span>
      <button className={`icon-button save-button ${saved ? "active" : ""}`} onClick={onSave} title={saved ? "Unsave place" : "Save place"} aria-label={`${saved ? "Unsave" : "Save"} ${place.name}`} aria-pressed={saved}><Bookmark size={19} fill={saved ? "currentColor" : "none"} /></button>
    </div>
    {photo && !imageFailed && <a className="place-photo" href={safeUrl(place.photo_page_url) || photo} target="_blank" rel="noreferrer"><img src={photo} alt={place.name} loading="lazy" onError={() => setImageFailed(true)} /></a>}
    <div className="place-title-row">
      <div><p className="category-label">{place.category}</p><h3>{place.name}</h3><p className="place-area"><MapPin size={13} />{place.area === "Nearby" ? "Lagos" : place.area}</p></div>
      <div className="match-score" title="Estimated compatibility with your request, not a rating"><strong>{place.score}</strong><span>fit score</span></div>
    </div>
    <div className="place-metrics"><span><strong>{money(place.typical_spend)}</strong><small>est. / person</small></span><span><strong>{place.distance_km !== null ? `${place.distance_km} km` : "Lagos"}</strong><small>{place.distance_km !== null ? "straight-line distance" : "location listed"}</small></span></div>
    <div className="place-reasons">{place.match_reasons.slice(0, 2).map(reason => <p key={reason}><Check size={14} /><span>{reason}</span></p>)}</div>
    <details className="place-details"><summary>Why this place <ChevronDown size={16} /></summary><div className="evidence-list">{place.evidence.map(item => <div key={item.label}><span>{item.label}</span><div><strong>{item.value}</strong><small className={item.status}>{item.status}</small></div></div>)}</div><p className="tradeoff"><strong>The tradeoff</strong>{place.tradeoffs.filter(t => t !== "No major tradeoff for this request").join(". ") || "No clear tradeoff in the available data."}</p></details>
    <div className="place-actions"><a href={map} target="_blank" rel="noreferrer"><Navigation size={15} /> Directions <ArrowUpRight size={13} /></a><a href={photos} target="_blank" rel="noreferrer" title="Find pictures of this place"><Image size={15} /> Photos</a><button className={`icon-button ${selected ? "active" : ""}`} onClick={onCompare} title={selected ? "Remove from comparison" : "Compare place"} aria-label={`Compare ${place.name}`} aria-pressed={selected}><GitCompareArrows size={18} /></button></div>
  </article>;
}

export function Modal({ title, children, onClose }: { title: string; children: React.ReactNode; onClose: () => void }) {
  const ref = React.useRef<HTMLDialogElement>(null);
  React.useEffect(() => {
    const dialog = ref.current;
    const focusBefore = document.activeElement as HTMLElement | null;
    dialog?.showModal();
    document.body.style.overflow = "hidden";
    return () => { dialog?.close(); document.body.style.overflow = ""; focusBefore?.focus(); };
  }, []);
  return <dialog ref={ref} className="modal" onCancel={onClose} onClick={event => { if (event.target === ref.current) onClose(); }}><div className="modal-inner"><header><h2>{title}</h2><button className="icon-button" aria-label="Close dialog" onClick={onClose}><X size={20} /></button></header>{children}</div></dialog>;
}

export function Comparison({ places, onClose }: { places: Place[]; onClose: () => void }) {
  return <Modal title="A closer look" onClose={onClose}><div className="comparison-scroll"><table className="comparison"><thead><tr><th>What matters</th>{places.map(p => <th key={p.place_id}><Coffee size={20} /><span>{p.name}</span></th>)}</tr></thead><tbody>{[
    ["Fit score", ...places.map(p => `${p.score} / 100`)],
    ["Spend estimate", ...places.map(p => money(p.typical_spend))],
    ["Distance", ...places.map(p => p.distance_km === null ? "Not available" : `${p.distance_km} km (straight line)`)],
    ["Opening hours", ...places.map(p => p.open_now === null ? "Not verified" : p.open_now ? "Listed as open" : "Listed as closed")],
    ["Why it fits", ...places.map(p => p.match_reasons.join(". "))],
    ["Tradeoff", ...places.map(p => p.tradeoffs.join(". "))],
  ].map(row => <tr key={row[0]}>{row.map((cell, index) => index === 0 ? <th key={index}>{cell}</th> : <td key={index}>{cell}</td>)}</tr>)}</tbody></table></div><p className="modal-note"><ExternalLink size={14} /> Confirm prices and amenities with the venue before going.</p></Modal>;
}
