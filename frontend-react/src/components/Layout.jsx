import { useState, useEffect, useMemo } from 'react';
import { Outlet, Link, useLocation } from "react-router-dom";
import { useAuth0 } from '@auth0/auth0-react';
import Sidebar from "./Sidebar";
import MultiSelect from "./MultiSelect";
import DateRangeFilter from "./DateRangeFilter";
import { supabase } from "../supabaseClient";

// 'YYYY-MM-DD' (start of day, local) → ISO. The "to" date is made inclusive of
// the whole day so a single-day range still matches that day's posts.
const startISO = (ymd) => (ymd ? new Date(`${ymd}T00:00:00`).toISOString() : null);
const endISO = (ymd) => (ymd ? new Date(`${ymd}T23:59:59.999`).toISOString() : null);

const todayYMD = (() => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
})();

export default function Layout() {
  const [title, setTitle] = useState('Dashboard Overview');
  const [sub, setSub] = useState('Real-time city-wide sentiment and public engagement.');
  const location = useLocation();
  const { isAuthenticated, loginWithRedirect, user, isLoading } = useAuth0();

  // Header filters, shared with the pages below via Outlet context.
  // `districts` is a list of quarter names ([] = all). `fromDate`/`toDate` are
  // 'YYYY-MM-DD' strings (either side may be null = unbounded).
  const [districts, setDistricts] = useState([]);
  const [fromDate, setFromDate] = useState(null);
  const [toDate, setToDate] = useState(null);
  const [quarterOptions, setQuarterOptions] = useState([]);

  useEffect(() => {
    supabase.from('quarters_map').select('name').then(({ data }) => {
      if (!data) return;
      const opts = data
        .map((d) => d.name)
        .filter(Boolean)
        .sort((a, b) => a.localeCompare(b))
        .map((n) => ({ value: n, label: n }));
      setQuarterOptions(opts);
    });
  }, []);

  // Memoized ISO bounds so pages only re-fetch when the picked dates actually
  // change (not on every render), keeping LiveFeed's infinite scroll stable.
  const fromISO = useMemo(() => startISO(fromDate), [fromDate]);
  const toISO = useMemo(() => endISO(toDate), [toDate]);

  const onDateChange = ({ fromDate: f, toDate: t }) => {
    if (f !== undefined) setFromDate(f);
    if (t !== undefined) setToDate(t);
  };

  useEffect(() => {
    switch(location.pathname) {
      case '/dashboard/live-feed':
        setTitle('Live Feedback Feed');
        setSub('Real-time timeline of city reports.');
        break;
      case '/dashboard/assistant':
        setTitle('City Assistant');
        setSub('Ask the AI about citizen feedback across the city.');
        break;
      case '/dashboard/heatmap':
        setTitle('Sentiment Heatmap');
        setSub('Geographic distribution of citizen sentiment.');
        break;
      case '/dashboard/topics':
        setTitle('Topic Explorer');
        setSub('Trending subjects across all districts.');
        break;
      case '/dashboard/settings':
        setTitle('Settings');
        setSub('Manage dashboard preferences and account.');
        break;
      default:
        setTitle('Dashboard Overview');
        setSub('Real-time city-wide sentiment and public engagement.');
        break;
    }
  }, [location.pathname]);

  return (
    <div className="bg-background-light dark:bg-background-dark font-display antialiased text-slate-900 dark:text-slate-100 min-h-screen pb-20 md:pb-0 flex">
      
      {/* Desktop Sidebar - Hidden on mobile */}
      <div className="hidden md:block">
        <Sidebar />
      </div>

      <div className="flex-1 md:ml-64 min-h-screen flex flex-col min-w-0">
        {/* Mobile Header - Hidden on desktop */}
        <div className="md:hidden sticky top-0 z-20 bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800">
          <div className="flex items-center justify-between px-4 py-3">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center text-primary">
                <span className="material-symbols-outlined">location_city</span>
              </div>
              <div>
                <h1 className="text-lg font-bold leading-tight">City Pulse</h1>
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  {title}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Link to="/dashboard/settings" className="w-10 h-10 rounded-full flex items-center justify-center text-slate-500 hover:bg-slate-50 dark:hover:bg-slate-800">
                <span className="material-symbols-outlined">settings</span>
              </Link>
              <button className="w-10 h-10 rounded-full flex items-center justify-center text-slate-500 hover:bg-slate-50 dark:hover:bg-slate-800">
                <span className="material-symbols-outlined">notifications</span>
              </button>
              
              {!isLoading && !isAuthenticated && (
                <div className="flex items-center gap-2 ml-1">
                  <button 
                    onClick={() => loginWithRedirect()}
                    className="px-3 py-1.5 text-slate-600 dark:text-slate-300 text-xs font-bold hover:text-primary transition-colors"
                  >
                    Log In
                  </button>
                  <button 
                    onClick={() => loginWithRedirect({ authorizationParams: { screen_hint: 'signup' } })}
                    className="px-3 py-1.5 bg-primary text-white text-xs font-bold rounded-lg shadow-sm hover:bg-blue-600 transition-colors"
                  >
                    Sign Up
                  </button>
                </div>
              )}
              {!isLoading && isAuthenticated && (
                <div className="w-10 h-10 rounded-full bg-slate-200 dark:bg-slate-700 ml-1 overflow-hidden">
                  <img src={user?.picture || 'https://via.placeholder.com/150'} alt="Profile" className="w-full h-full object-cover" />
                </div>
              )}
            </div>
          </div>
          
          {/* Quarter + date filters (Mobile) - drive every dashboard page */}
          <div className="flex items-center gap-2 px-4 pb-3">
            <MultiSelect
              icon="location_on"
              selected={districts}
              onChange={setDistricts}
              options={quarterOptions}
              allLabel="All Quarters"
              searchPlaceholder="Search quarters…"
              widthClass="flex-1 min-w-0"
            />
            <DateRangeFilter
              fromDate={fromDate}
              toDate={toDate}
              onChange={onDateChange}
              max={todayYMD}
              widthClass="flex-1 min-w-0"
            />
          </div>

          {/* Sub-header Context / Filters (Mobile only) */}
          {location.pathname === '/dashboard/live-feed' && (
            <div className="flex items-center gap-3 px-4 pb-3 overflow-x-auto hide-scrollbar">
              <button className="flex h-9 shrink-0 items-center justify-center gap-x-2 rounded-lg bg-white dark:bg-slate-800 px-3 text-sm font-medium text-slate-700 dark:text-slate-200 border border-slate-200 dark:border-slate-700 shadow-sm">
                <span className="material-symbols-outlined text-[18px]">filter_list</span>
                <span>Category</span>
                <span className="material-symbols-outlined text-[18px]">arrow_drop_down</span>
              </button>
              <div className="w-[1px] h-6 bg-slate-200 dark:bg-slate-700 shrink-0 mx-1"></div>
              <button className="flex h-9 shrink-0 items-center justify-center rounded-full bg-slate-900 dark:bg-white px-4 text-sm font-medium text-white dark:text-slate-900 shadow-sm">
                All
              </button>
              <button className="flex h-9 shrink-0 items-center justify-center rounded-full bg-slate-100 dark:bg-slate-800 px-4 text-sm font-medium text-slate-600 dark:text-slate-300 border border-transparent hover:border-slate-300 dark:hover:border-slate-600 transition-colors">
                Positive
              </button>
              <button className="flex h-9 shrink-0 items-center justify-center rounded-full bg-slate-100 dark:bg-slate-800 px-4 text-sm font-medium text-slate-600 dark:text-slate-300 border border-transparent hover:border-slate-300 dark:hover:border-slate-600 transition-colors">
                Neutral
              </button>
              <button className="flex h-9 shrink-0 items-center justify-center rounded-full bg-slate-100 dark:bg-slate-800 px-4 text-sm font-medium text-slate-600 dark:text-slate-300 border border-transparent hover:border-slate-300 dark:hover:border-slate-600 transition-colors">
                Negative
              </button>
            </div>
          )}
        </div>

        {/* Desktop Header - Hidden on mobile */}
        <header className="hidden md:block sticky top-0 z-40 bg-background-light/80 dark:bg-background-dark/80 backdrop-blur-md border-b border-slate-200 dark:border-slate-800 px-4 lg:px-8 py-4">
          <div className="flex items-center justify-between gap-4 max-w-7xl mx-auto">
            <div className="min-w-0 flex-1">
              <h2 className="text-xl lg:text-2xl font-bold text-slate-900 dark:text-white truncate">{title}</h2>
              <p className="text-xs lg:text-sm text-slate-500 truncate">{sub}</p>
            </div>
            <div className="flex items-center gap-2 lg:gap-4 shrink-0">
              <MultiSelect
                icon="location_on"
                selected={districts}
                onChange={setDistricts}
                options={quarterOptions}
                allLabel="All Quarters"
                searchPlaceholder="Search quarters…"
                widthClass="w-48"
              />
              <DateRangeFilter
                fromDate={fromDate}
                toDate={toDate}
                onChange={onDateChange}
                max={todayYMD}
                widthClass="w-48"
              />
              <Link to="/dashboard/settings" className="bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 p-2 rounded-lg flex items-center justify-center hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors">
                 <span className="material-symbols-outlined">settings</span>
              </Link>
              <button className="bg-primary text-white p-2 rounded-lg flex items-center justify-center hover:bg-primary/90">
                <span className="material-symbols-outlined">notifications</span>
              </button>
            </div>
          </div>
        </header>

        <main className="flex flex-col flex-1 p-4 md:p-6 lg:p-8 max-w-7xl mx-auto w-full min-w-0">
          {/* key on pathname so the wrapper remounts on navigation, replaying
              the entrance animation. min-h-0 keeps the Assistant's flex chain. */}
          <div key={location.pathname} className="flex flex-col flex-1 min-w-0 min-h-0 animate-page-enter">
            <Outlet context={{ districts, fromDate, toDate, fromISO, toISO }} />
          </div>
        </main>
      </div>

      {/* Mobile Bottom Navigation - Hidden on Desktop */}
      <nav className="md:hidden fixed bottom-0 w-full z-30 bg-white dark:bg-slate-900 border-t border-slate-200 dark:border-slate-800 pb-safe pt-2 shadow-[0_-4px_6px_-1px_rgba(0,0,0,0.05)]">
        <div className="flex justify-around items-end pb-2">
          <Link to="/dashboard" className={`flex flex-1 flex-col items-center justify-end gap-1 transition-colors group ${location.pathname === '/dashboard' || location.pathname === '/' ? 'text-primary' : 'text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200'}`}>
            <span className="material-symbols-outlined text-[24px]" style={location.pathname === '/dashboard' || location.pathname === '/' ? { fontVariationSettings: "'FILL' 1, 'wght' 400" } : {}}>dashboard</span>
            <p className="text-[10px] font-medium leading-normal tracking-wide truncate px-1">Overview</p>
          </Link>
          <Link to="/dashboard/heatmap" className={`flex flex-1 flex-col items-center justify-end gap-1 transition-colors group ${location.pathname === '/dashboard/heatmap' ? 'text-primary' : 'text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200'}`}>
            <span className="material-symbols-outlined text-[24px]" style={location.pathname === '/dashboard/heatmap' ? { fontVariationSettings: "'FILL' 1, 'wght' 400" } : {}}>map</span>
            <p className="text-[10px] font-medium leading-normal tracking-wide truncate px-1">Heatmap</p>
          </Link>
          <Link to="/dashboard/topics" className={`flex flex-1 flex-col items-center justify-end gap-1 transition-colors group ${location.pathname === '/dashboard/topics' ? 'text-primary' : 'text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200'}`}>
            <span className="material-symbols-outlined text-[24px]" style={location.pathname === '/dashboard/topics' ? { fontVariationSettings: "'FILL' 1, 'wght' 400" } : {}}>tag</span>
            <p className="text-[10px] font-medium leading-normal tracking-wide truncate px-1">Topics</p>
          </Link>
          <Link to="/dashboard/live-feed" className={`flex flex-1 flex-col items-center justify-end gap-1 transition-colors group ${location.pathname === '/dashboard/live-feed' ? 'text-primary' : 'text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200'}`}>
            <span className="material-symbols-outlined text-[24px]" style={location.pathname === '/dashboard/live-feed' ? { fontVariationSettings: "'FILL' 1, 'wght' 400" } : {}}>rss_feed</span>
            <p className="text-[10px] font-medium leading-normal tracking-wide truncate px-1">Live</p>
          </Link>
           <Link to="/dashboard/settings" className={`flex flex-1 flex-col items-center justify-end gap-1 transition-colors group ${location.pathname === '/dashboard/settings' ? 'text-primary' : 'text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200'}`}>
            <span className="material-symbols-outlined text-[24px]" style={location.pathname === '/dashboard/settings' ? { fontVariationSettings: "'FILL' 1, 'wght' 400" } : {}}>settings</span>
            <p className="text-[10px] font-medium leading-normal tracking-wide truncate px-1">Settings</p>
          </Link>
        </div>
        <div className="h-4 bg-white dark:bg-slate-900"></div>
      </nav>
    </div>
  );
}
