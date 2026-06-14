import { useState, useRef, useEffect } from 'react';

// Calendar-style date filter. The user can set a "from" date, a "to" date, or
// both - anything left blank is unbounded on that side. Values are plain
// 'YYYY-MM-DD' strings (or null). Quick presets fill both ends in one click.
const fmt = (ymd) => {
  if (!ymd) return null;
  const [y, m, d] = ymd.split('-').map(Number);
  return new Date(y, m - 1, d).toLocaleDateString(undefined, { day: 'numeric', month: 'short' });
};

const toYMD = (date) => {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, '0');
  const d = String(date.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
};

export default function DateRangeFilter({ fromDate, toDate, onChange, min, max, widthClass = 'w-48' }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    const onDocClick = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener('mousedown', onDocClick);
    return () => document.removeEventListener('mousedown', onDocClick);
  }, []);

  // Keep the range coherent: a "from" after "to" (or vice-versa) collapses to a
  // single day rather than producing an empty, confusing result set.
  const setFrom = (v) => {
    const next = v || null;
    onChange({ fromDate: next, toDate: next && toDate && next > toDate ? next : toDate });
  };
  const setTo = (v) => {
    const next = v || null;
    onChange({ toDate: next, fromDate: next && fromDate && next < fromDate ? next : fromDate });
  };

  const preset = (kind) => {
    const today = new Date();
    if (kind === 'all') return onChange({ fromDate: null, toDate: null });
    let from;
    if (kind === '7d') from = new Date(today.getTime() - 7 * 864e5);
    else if (kind === '30d') from = new Date(today.getTime() - 30 * 864e5);
    else if (kind === 'ytd') from = new Date(today.getFullYear(), 0, 1);
    onChange({ fromDate: toYMD(from), toDate: toYMD(today) });
  };

  let label = 'Any date';
  if (fromDate && toDate) label = `${fmt(fromDate)} - ${fmt(toDate)}`;
  else if (fromDate) label = `From ${fmt(fromDate)}`;
  else if (toDate) label = `Until ${fmt(toDate)}`;

  const inputCls =
    'w-full px-2 py-1.5 text-sm bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-md focus:ring-2 focus:ring-primary focus:outline-none text-slate-700 dark:text-slate-200 [color-scheme:light] dark:[color-scheme:dark]';

  return (
    <div className={`relative ${widthClass}`} ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-2 w-full bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg px-3 py-2 shadow-sm text-sm font-medium text-slate-700 dark:text-slate-200 hover:border-slate-300 dark:hover:border-slate-700 transition-colors"
      >
        <span className="material-symbols-outlined text-slate-400 text-lg">calendar_today</span>
        <span className="truncate flex-1 text-left">{label}</span>
        <span className="material-symbols-outlined text-slate-400 text-lg">
          {open ? 'arrow_drop_up' : 'arrow_drop_down'}
        </span>
      </button>

      {open && (
        <div className="absolute right-0 z-[2000] mt-1 w-72 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 shadow-xl p-3 flex flex-col gap-3">
          {/* Quick presets */}
          <div className="flex flex-wrap gap-1.5">
            {[
              ['7d', 'Last 7d'],
              ['30d', 'Last 30d'],
              ['ytd', 'Year to date'],
              ['all', 'All time'],
            ].map(([k, lbl]) => (
              <button
                key={k}
                type="button"
                onClick={() => preset(k)}
                className="px-2.5 py-1 text-xs font-medium rounded-md bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 hover:bg-primary/10 hover:text-primary transition-colors"
              >
                {lbl}
              </button>
            ))}
          </div>

          {/* From / To inputs */}
          <div className="flex flex-col gap-2">
            <label className="flex flex-col gap-1">
              <span className="text-xs font-semibold text-slate-500 dark:text-slate-400">From</span>
              <input
                type="date"
                value={fromDate || ''}
                min={min}
                max={toDate || max}
                onChange={(e) => setFrom(e.target.value)}
                className={inputCls}
              />
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-xs font-semibold text-slate-500 dark:text-slate-400">To</span>
              <input
                type="date"
                value={toDate || ''}
                min={fromDate || min}
                max={max}
                onChange={(e) => setTo(e.target.value)}
                className={inputCls}
              />
            </label>
          </div>

          <div className="flex items-center justify-between pt-1 border-t border-slate-100 dark:border-slate-800">
            <button
              type="button"
              onClick={() => onChange({ fromDate: null, toDate: null })}
              disabled={!fromDate && !toDate}
              className="text-xs font-semibold text-slate-500 hover:text-slate-700 dark:hover:text-slate-300 disabled:opacity-40"
            >
              Clear
            </button>
            <button
              type="button"
              onClick={() => setOpen(false)}
              className="text-xs font-semibold text-primary hover:underline"
            >
              Done
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
