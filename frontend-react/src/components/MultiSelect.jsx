import { useState, useRef, useEffect, useMemo } from 'react';

// Checkbox multi-select dropdown — lets the user combine several quarters in
// one filter. Mirrors Dropdown.jsx's styling/behaviour (custom panel so the
// option list can be dark-themed and searchable). `selected` is an array of
// option values; an empty array means "all" (no constraint).
export default function MultiSelect({
  icon,
  options,
  selected = [],
  onChange,
  allLabel = 'All',
  searchPlaceholder = 'Search…',
  widthClass = 'w-48',
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const ref = useRef(null);

  useEffect(() => {
    const onDocClick = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener('mousedown', onDocClick);
    return () => document.removeEventListener('mousedown', onDocClick);
  }, []);

  const selectedSet = useMemo(() => new Set(selected), [selected]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return options;
    return options.filter((o) => o.label.toLowerCase().includes(q));
  }, [options, query]);

  const toggle = (value) => {
    if (selectedSet.has(value)) onChange(selected.filter((v) => v !== value));
    else onChange([...selected, value]);
  };

  const buttonLabel =
    selected.length === 0
      ? allLabel
      : selected.length === 1
      ? options.find((o) => o.value === selected[0])?.label ?? '1 selected'
      : `${selected.length} selected`;

  return (
    <div className={`relative ${widthClass}`} ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-2 w-full bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg px-3 py-2 shadow-sm text-sm font-medium text-slate-700 dark:text-slate-200 hover:border-slate-300 dark:hover:border-slate-700 transition-colors"
      >
        {icon && <span className="material-symbols-outlined text-slate-400 text-lg">{icon}</span>}
        <span className="truncate flex-1 text-left">{buttonLabel}</span>
        {selected.length > 0 && (
          <span className="shrink-0 min-w-[18px] h-[18px] px-1 rounded-full bg-primary/15 text-primary text-[11px] font-bold flex items-center justify-center">
            {selected.length}
          </span>
        )}
        <span className="material-symbols-outlined text-slate-400 text-lg">
          {open ? 'arrow_drop_up' : 'arrow_drop_down'}
        </span>
      </button>

      {open && (
        <div className="absolute z-[2000] mt-1 w-full min-w-[230px] rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 shadow-xl flex flex-col">
          {/* Search */}
          <div className="p-2 border-b border-slate-100 dark:border-slate-800">
            <div className="relative">
              <span className="material-symbols-outlined absolute left-2 top-1/2 -translate-y-1/2 text-slate-400 text-[18px]">search</span>
              <input
                autoFocus
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder={searchPlaceholder}
                className="w-full pl-8 pr-2 py-1.5 text-sm bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-md focus:ring-2 focus:ring-primary focus:outline-none text-slate-700 dark:text-slate-200"
              />
            </div>
          </div>

          {/* Select all (filtered) / Clear */}
          <div className="flex items-center justify-between px-3 py-1.5 text-xs border-b border-slate-100 dark:border-slate-800">
            <button
              type="button"
              onClick={() => {
                const merged = new Set(selected);
                filtered.forEach((o) => merged.add(o.value));
                onChange([...merged]);
              }}
              className="font-semibold text-primary hover:underline"
            >
              Select{query ? ' matches' : ' all'}
            </button>
            <button
              type="button"
              onClick={() => onChange([])}
              disabled={selected.length === 0}
              className="font-semibold text-slate-500 hover:text-slate-700 dark:hover:text-slate-300 disabled:opacity-40 disabled:hover:text-slate-500"
            >
              Clear
            </button>
          </div>

          {/* Options */}
          <div className="max-h-64 overflow-auto py-1">
            {filtered.length === 0 ? (
              <p className="px-3 py-3 text-sm text-slate-400 text-center">No matches</p>
            ) : (
              filtered.map((o) => {
                const checked = selectedSet.has(o.value);
                return (
                  <button
                    key={o.value}
                    type="button"
                    onClick={() => toggle(o.value)}
                    className="w-full flex items-center gap-2.5 text-left px-3 py-2 text-sm text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors"
                  >
                    <span
                      className={`shrink-0 w-4 h-4 rounded border flex items-center justify-center transition-colors ${
                        checked
                          ? 'bg-primary border-primary text-white'
                          : 'border-slate-300 dark:border-slate-600'
                      }`}
                    >
                      {checked && <span className="material-symbols-outlined text-[14px] leading-none">check</span>}
                    </span>
                    <span className="truncate">{o.label}</span>
                  </button>
                );
              })
            )}
          </div>
        </div>
      )}
    </div>
  );
}
