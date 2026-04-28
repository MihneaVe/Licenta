import { useState, useEffect } from 'react';

// Django serves the Bucharest quarters map (Leaflet + 83 cartiere) at
// /feed/map/. VITE_DJANGO_URL lets compose / prod override the host.
const DJANGO_URL = import.meta.env.VITE_DJANGO_URL || 'http://localhost:8000';
const MAP_URL = `${DJANGO_URL}/feed/map/`;

export default function Heatmap() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  // If the iframe hasn't loaded in 15s, show a configuration hint.
  useEffect(() => {
    const t = setTimeout(() => setError(true), 15000);
    return () => clearTimeout(t);
  }, []);

  return (
    <div className="flex flex-col flex-1 gap-4 md:gap-6 relative" style={{ minHeight: '600px' }}>

      {/* Legend overlay */}
      <div className="absolute top-4 right-4 z-20 bg-slate-900/90 backdrop-blur-md rounded-xl p-4 shadow-lg border border-slate-700 pointer-events-none">
        <h3 className="text-xs font-bold text-white uppercase tracking-wider mb-3">
          Sentiment Legend
        </h3>
        <div className="flex flex-col gap-2 text-xs font-medium text-slate-300">
          <div className="flex items-center gap-2">
            <span className="w-3 h-3 rounded-full" style={{ backgroundColor: '#16a34a' }}></span>
            Positive (avg ≥ +0.3)
          </div>
          <div className="flex items-center gap-2">
            <span className="w-3 h-3 rounded-full" style={{ backgroundColor: '#f59e0b' }}></span>
            Mixed (−0.3 … +0.3)
          </div>
          <div className="flex items-center gap-2">
            <span className="w-3 h-3 rounded-full" style={{ backgroundColor: '#dc2626' }}></span>
            Negative (avg ≤ −0.3)
          </div>
          <div className="flex items-center gap-2">
            <span className="w-3 h-3 rounded-full" style={{ backgroundColor: '#6b7280' }}></span>
            No analysed posts yet
          </div>
        </div>
        <p className="text-[10px] text-slate-500 mt-3 max-w-[180px] leading-snug">
          Markers cover Bucharest's 83 cartiere plus the 6 sectors. Sized by post count.
        </p>
      </div>

      {/* Map iframe */}
      <div className="relative flex-1 rounded-xl overflow-hidden border border-slate-800 shadow-lg" style={{ minHeight: '550px' }}>
        {loading && !error && (
          <div className="absolute inset-0 z-10 flex flex-col items-center justify-center bg-slate-900 gap-4">
            <div className="w-10 h-10 border-4 border-primary border-t-transparent rounded-full animate-spin"></div>
            <p className="text-slate-400 text-sm font-medium">Loading Bucharest map…</p>
          </div>
        )}
        {error && loading && (
          <div className="absolute inset-0 z-10 flex flex-col items-center justify-center bg-slate-900 gap-3 px-8 text-center">
            <span className="material-symbols-outlined text-4xl text-slate-500">map_off</span>
            <p className="text-slate-400 text-sm font-medium">
              Map could not load from <code className="text-primary">{MAP_URL}</code>.
              Make sure the Django backend (<code className="text-primary">civicpulse:web</code>) is running on port 8000.
            </p>
          </div>
        )}
        <iframe
          src={MAP_URL}
          title="Bucharest Sentiment Heatmap"
          className="w-full h-full border-0"
          style={{ minHeight: '550px' }}
          onLoad={() => setLoading(false)}
          onError={() => { setLoading(false); setError(true); }}
        />
      </div>
    </div>
  );
}
