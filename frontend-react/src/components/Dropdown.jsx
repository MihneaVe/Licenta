import { useState, useRef, useEffect } from 'react';

// Custom dropdown - native <select> option lists can't be dark-themed
// (the browser renders them with OS chrome), so we roll our own.
export default function Dropdown({ icon, value, options, onChange, widthClass = 'w-48' }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    const onDocClick = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener('mousedown', onDocClick);
    return () => document.removeEventListener('mousedown', onDocClick);
  }, []);

  const current = options.find((o) => o.value === value);

  return (
    <div className={`relative ${widthClass}`} ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-2 w-full bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg px-3 py-2 shadow-sm text-sm font-medium text-slate-700 dark:text-slate-200 hover:border-slate-300 dark:hover:border-slate-700 transition-colors"
      >
        {icon && <span className="material-symbols-outlined text-slate-400 text-lg">{icon}</span>}
        <span className="truncate flex-1 text-left">{current?.label ?? 'Select'}</span>
        <span className="material-symbols-outlined text-slate-400 text-lg">
          {open ? 'arrow_drop_up' : 'arrow_drop_down'}
        </span>
      </button>

      {open && (
        <div className="absolute z-[2000] mt-1 w-full min-w-[180px] max-h-72 overflow-auto rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 shadow-xl py-1">
          {options.map((o) => (
            <button
              key={o.value}
              type="button"
              onClick={() => { onChange(o.value); setOpen(false); }}
              className={`w-full text-left px-3 py-2 text-sm transition-colors ${
                o.value === value
                  ? 'bg-primary/10 text-primary font-semibold'
                  : 'text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800'
              }`}
            >
              {o.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
