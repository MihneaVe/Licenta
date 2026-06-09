import { useState, useEffect, useMemo } from 'react';
import { useOutletContext } from 'react-router-dom';
import { MapContainer, TileLayer, GeoJSON, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { supabase } from '../supabaseClient';

// The map reads Bucharest's quarters straight from Supabase (the read-only
// `quarters_map` view, granted to anon). Each quarter is a boundary polygon
// shaded by its average sentiment. Tiles + chrome follow the app theme.
const BUCHAREST_CENTER = [44.4378, 26.0969];

function colourFor(sent) {
  if (sent === null || sent === undefined) return '#6b7280'; // grey
  if (sent >= 0.3) return '#16a34a'; // green
  if (sent <= -0.3) return '#dc2626'; // red
  return '#f59e0b'; // amber
}

function radiusFor(count) {
  if (!count) return 6;
  return Math.min(26, 8 + Math.sqrt(count) * 5);
}

function rowsToFeatureCollection(rows) {
  const features = [];
  for (const r of rows) {
    let geometry = r.boundary_geojson;
    if (!geometry && r.centroid_lat != null && r.centroid_lng != null) {
      geometry = { type: 'Point', coordinates: [r.centroid_lng, r.centroid_lat] };
    }
    if (!geometry) continue;
    features.push({
      type: 'Feature',
      geometry,
      properties: {
        id: r.id,
        name: r.name,
        parent: r.parent,
        post_count: r.post_count,
        avg_sentiment: r.avg_sentiment,
      },
    });
  }
  return { type: 'FeatureCollection', features };
}

function styleForFeature(feature) {
  const p = feature.properties;
  const colour = colourFor(p.avg_sentiment);
  return {
    color: colour,
    weight: 1,
    fillColor: colour,
    fillOpacity: p.post_count ? 0.5 : 0.18,
  };
}

function pointToLayer(feature, latlng) {
  const p = feature.properties;
  const colour = colourFor(p.avg_sentiment);
  return L.circleMarker(latlng, {
    radius: radiusFor(p.post_count),
    color: colour,
    weight: 1,
    fillColor: colour,
    fillOpacity: 0.6,
  });
}

// Tooltip + popup only. Hover handlers are attached in the component so their
// mouseout can restore the *selection-aware* style (dimmed when filtered out).
function bindFeatureInfo(feature, layer) {
  const p = feature.properties;
  const sent = p.avg_sentiment == null ? '—' : Number(p.avg_sentiment).toFixed(2);
  layer.bindTooltip(p.name, { sticky: true });
  layer.bindPopup(
    `<div style="min-width:140px">
       <div style="font-weight:700;font-size:13px">${p.name}</div>
       ${p.parent ? `<div style="opacity:.7;font-size:11px;margin-bottom:4px">${p.parent}</div>` : ''}
       <div style="font-size:12px"><b>${p.post_count}</b> postări</div>
       <div style="font-size:12px">Sentiment mediu: <b>${sent}</b></div>
     </div>`
  );
}

// Track the dashboard's light/dark class on <html> so the map can follow it.
function useIsDark() {
  const [dark, setDark] = useState(
    () => typeof document !== 'undefined' && document.documentElement.classList.contains('dark')
  );
  useEffect(() => {
    const el = document.documentElement;
    const obs = new MutationObserver(() => setDark(el.classList.contains('dark')));
    obs.observe(el, { attributes: true, attributeFilter: ['class'] });
    return () => obs.disconnect();
  }, []);
  return dark;
}

// Pan/zoom to the quarter(s) chosen in the header filter: reset to the city
// when nothing is selected, fly to a single quarter, or fit the bounds of
// several. Keyed on the selection so re-picking re-frames the map.
function FlyToSelection({ districts, fc }) {
  const map = useMap();
  const key = districts.join('|');
  useEffect(() => {
    if (!fc) return;
    if (districts.length === 0) {
      map.setView(BUCHAREST_CENTER, 12);
      return;
    }
    const feats = fc.features.filter((f) => districts.includes(f.properties?.name));
    if (feats.length === 0) return;
    try {
      const bounds = L.geoJSON({ type: 'FeatureCollection', features: feats }).getBounds();
      if (feats.length === 1) map.setView(bounds.getCenter(), 14);
      else map.fitBounds(bounds, { padding: [60, 60], maxZoom: 14 });
    } catch {
      /* ignore bad geometry */
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, fc, map]);
  return null;
}

export default function Heatmap() {
  const { districts = [] } = useOutletContext() || {};
  const dark = useIsDark();
  const selectedSet = useMemo(() => new Set(districts), [districts]);

  // When a quarter filter is active, fade the quarters that aren't selected and
  // thicken the ones that are, so the map mirrors the header selection.
  const styleFn = (feature) => {
    const base = styleForFeature(feature);
    if (selectedSet.size === 0) return base;
    if (selectedSet.has(feature.properties.name)) {
      return { ...base, weight: 2.5, fillOpacity: Math.max(base.fillOpacity, 0.55) };
    }
    return { ...base, opacity: 0.25, fillOpacity: 0.05 };
  };

  const onEach = (feature, layer) => {
    bindFeatureInfo(feature, layer);
    layer.on({
      mouseover: (e) => e.target.setStyle({ weight: 2.5, fillOpacity: 0.65 }),
      mouseout: (e) => e.target.setStyle(styleFn(feature)),
    });
  };
  const [fc, setFc] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const { data, error } = await supabase
        .from('quarters_map')
        .select('id,name,parent,post_count,avg_sentiment,boundary_geojson,centroid_lat,centroid_lng');
      if (cancelled) return;
      if (error) {
        setError(error.message);
        setLoading(false);
        return;
      }
      setFc(rowsToFeatureCollection(data || []));
      setLoading(false);
    })();
    return () => { cancelled = true; };
  }, []);

  const tileUrl = dark
    ? 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png'
    : 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png';

  return (
    <div className="flex flex-col flex-1 gap-4 md:gap-6 relative" style={{ minHeight: '600px' }}>

      {/* Legend overlay */}
      <div className="absolute top-4 right-4 z-[1100] bg-white/90 dark:bg-slate-900/90 backdrop-blur-md rounded-xl p-4 shadow-lg border border-slate-200 dark:border-slate-700 pointer-events-none">
        <h3 className="text-xs font-bold text-slate-900 dark:text-white uppercase tracking-wider mb-3">
          Sentiment Legend
        </h3>
        <div className="flex flex-col gap-2 text-xs font-medium text-slate-600 dark:text-slate-300">
          <div className="flex items-center gap-2">
            <span className="w-3 h-3 rounded-sm" style={{ backgroundColor: '#16a34a' }}></span>
            Positive (avg ≥ +0.3)
          </div>
          <div className="flex items-center gap-2">
            <span className="w-3 h-3 rounded-sm" style={{ backgroundColor: '#f59e0b' }}></span>
            Mixed (−0.3 … +0.3)
          </div>
          <div className="flex items-center gap-2">
            <span className="w-3 h-3 rounded-sm" style={{ backgroundColor: '#dc2626' }}></span>
            Negative (avg ≤ −0.3)
          </div>
          <div className="flex items-center gap-2">
            <span className="w-3 h-3 rounded-sm" style={{ backgroundColor: '#6b7280' }}></span>
            No analysed posts yet
          </div>
        </div>
        <p className="text-[10px] text-slate-400 dark:text-slate-500 mt-3 max-w-[190px] leading-snug">
          Each polygon is one of Bucharest's 77 cartiere, shaded by average sentiment. Faint = no posts yet.
        </p>
      </div>

      {/* Non-blocking status chips */}
      {loading && (
        <div className="absolute bottom-6 left-1/2 -translate-x-1/2 z-[1100] flex items-center gap-2 bg-white/90 dark:bg-slate-900/90 backdrop-blur-md rounded-full px-4 py-2 shadow-lg border border-slate-200 dark:border-slate-700 pointer-events-none">
          <div className="w-4 h-4 border-2 border-primary border-t-transparent rounded-full animate-spin"></div>
          <span className="text-xs font-medium text-slate-600 dark:text-slate-300">Loading Bucharest quarters…</span>
        </div>
      )}
      {error && (
        <div className="absolute bottom-6 left-1/2 -translate-x-1/2 z-[1100] flex items-center gap-2 bg-amber-500/10 backdrop-blur-md rounded-full px-4 py-2 shadow-lg border border-amber-500/40">
          <span className="material-symbols-outlined text-amber-500 text-[18px]">warning</span>
          <span className="text-xs font-medium text-amber-700 dark:text-amber-200">Couldn't load quarters: {error}</span>
        </div>
      )}

      {/* Native Leaflet map */}
      <div className="relative flex-1 rounded-xl overflow-hidden border border-slate-200 dark:border-slate-800 shadow-lg" style={{ minHeight: '550px' }}>
        <MapContainer
          center={BUCHAREST_CENTER}
          zoom={12}
          scrollWheelZoom
          className="w-full h-full isolate"
          style={{ minHeight: '550px', background: dark ? '#101922' : '#eef2f6' }}
        >
          <TileLayer
            key={dark ? 'dark' : 'light'}
            url={tileUrl}
            subdomains="abcd"
            maxZoom={20}
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
          />
          {fc && (
            <GeoJSON
              key={districts.join('|')}
              data={fc}
              style={styleFn}
              pointToLayer={pointToLayer}
              onEachFeature={onEach}
            />
          )}
          <FlyToSelection districts={districts} fc={fc} />
        </MapContainer>
      </div>
    </div>
  );
}
