import { useState, useEffect, useRef, useCallback } from 'react';
import { useOutletContext } from 'react-router-dom';
import { supabase } from '../supabaseClient';

// Sentiment → colors for the label text and the meter fill. Written as
// complete, literal class names on purpose: Tailwind only generates classes it
// can see in the source, so the old approach of pulling class strings from the
// DB view (item.sentiment_gradient / item.sentiment_color) got purged and
// rendered with no color. Keyed off the label so the bar matches the word shown.
const SENTIMENT_STYLE = {
  positive: { text: 'text-emerald-500', bar: 'bg-emerald-500' },
  negative: { text: 'text-rose-500', bar: 'bg-rose-500' },
  neutral: { text: 'text-amber-500', bar: 'bg-amber-500' },
};

// How many rows we pull per page as the user scrolls.
const PAGE_SIZE = 30;

export default function LiveFeed() {
  const { districts = [], fromISO, toISO } = useOutletContext() || {};
  const [feedItems, setFeedItems] = useState([]);
  const [loading, setLoading] = useState(true);      // first page of a fresh filter set
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(true);
  const [error, setError] = useState(null);

  // Refs the IntersectionObserver callback reads so it never works off stale
  // state and doesn't need to be re-created on every render.
  const offsetRef = useRef(0);
  const hasMoreRef = useRef(true);
  const loadingMoreRef = useRef(false);

  // Fetch one page. `reset` starts a brand-new list (mount + filter change);
  // otherwise it appends the next page.
  const fetchPage = useCallback(async (reset) => {
    if (reset) {
      offsetRef.current = 0;
      hasMoreRef.current = true;
      setLoading(true);
    } else {
      if (loadingMoreRef.current || !hasMoreRef.current) return;
      loadingMoreRef.current = true;
      setLoadingMore(true);
    }

    const from = offsetRef.current;
    const to = from + PAGE_SIZE - 1;

    let q = supabase
      .from('feedbacks')
      .select('*')
      .order('created_at', { ascending: false })
      .range(from, to);
    if (districts.length) q = q.in('location', districts);
    if (fromISO) q = q.gte('created_at', fromISO);
    if (toISO) q = q.lte('created_at', toISO);

    const { data, error } = await q;

    if (error) {
      setError(error.message);
    } else {
      setError(null);
      const rows = data || [];
      offsetRef.current = from + rows.length;
      hasMoreRef.current = rows.length === PAGE_SIZE; // a short page = end of feed
      setHasMore(hasMoreRef.current);
      setFeedItems((prev) => {
        if (reset) return rows;
        const seen = new Set(prev.map((p) => p.id));
        return [...prev, ...rows.filter((r) => !seen.has(r.id))];
      });
    }

    if (reset) setLoading(false);
    loadingMoreRef.current = false;
    setLoadingMore(false);
  }, [districts, fromISO, toISO]);

  // Keep a live handle to the latest fetchPage for the observer callback.
  const fetchPageRef = useRef(fetchPage);
  fetchPageRef.current = fetchPage;

  // Reload from scratch whenever the header district/date filters change.
  useEffect(() => { fetchPage(true); }, [fetchPage]);

  // Real-time inserts (respecting the active quarter filter). Postgres views
  // don't emit LISTEN/NOTIFY, so this is mostly dormant for the `feedbacks`
  // view - kept (with an id-dedup guard) so it lights up if that ever changes.
  useEffect(() => {
    const channel = supabase
      .channel('feedbacks-live')
      .on('postgres_changes', { event: 'INSERT', schema: 'public', table: 'feedbacks' }, (payload) => {
        const row = payload.new;
        if (districts.length && !districts.includes(row.location)) return;
        setFeedItems((prev) => (prev.some((p) => p.id === row.id) ? prev : [row, ...prev]));
      })
      .subscribe();
    return () => { supabase.removeChannel(channel); };
  }, [districts]);

  // Infinite scroll. The dashboard scrolls the window (there's no inner scroll
  // container), so a scroll/resize listener that fires when we're within ~800px
  // of the bottom is simpler and more reliable than an IntersectionObserver.
  useEffect(() => {
    const maybeLoadMore = () => {
      if (loadingMoreRef.current || !hasMoreRef.current) return;
      const reachedThreshold =
        window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 800;
      if (reachedThreshold) fetchPageRef.current(false);
    };
    window.addEventListener('scroll', maybeLoadMore, { passive: true });
    window.addEventListener('resize', maybeLoadMore);
    return () => {
      window.removeEventListener('scroll', maybeLoadMore);
      window.removeEventListener('resize', maybeLoadMore);
    };
  }, []);

  function timeAgo(dateStr) {
    const diff = Math.floor((Date.now() - new Date(dateStr)) / 1000);
    if (diff < 60) return `${diff}s ago`;
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
    return `${Math.floor(diff / 86400)}d ago`;
  }

  const getColorClasses = (color) => {
    switch (color) {
      case 'blue': return 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300';
      case 'amber': return 'bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300';
      case 'green': return 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300';
      case 'purple': return 'bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300';
      case 'teal': return 'bg-teal-100 dark:bg-teal-900/30 text-teal-700 dark:text-teal-300';
      default: return 'bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300';
    }
  };

  const getBadgeClasses = (color) => {
    switch (color) {
      case 'blue': return 'bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-300 ring-blue-700/10';
      case 'amber': return 'bg-amber-50 dark:bg-amber-900/20 text-amber-700 dark:text-amber-300 ring-amber-700/10';
      case 'green': return 'bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-300 ring-green-700/10';
      case 'purple': return 'bg-purple-50 dark:bg-purple-900/20 text-purple-700 dark:text-purple-300 ring-purple-700/10';
      case 'teal': return 'bg-teal-50 dark:bg-teal-900/20 text-teal-700 dark:text-teal-300 ring-teal-700/10';
      default: return 'bg-slate-50 dark:bg-slate-800 text-slate-700 dark:text-slate-300 ring-slate-700/10';
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <div className="w-10 h-10 border-4 border-primary border-t-transparent rounded-full animate-spin"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center py-24 text-red-500 font-medium">
        Error: {error}
      </div>
    );
  }

  if (feedItems.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-24 text-center">
        <span className="material-symbols-outlined text-5xl text-slate-300 dark:text-slate-700 mb-3">inbox</span>
        <p className="text-slate-500 dark:text-slate-400 text-sm font-medium">No feedback matches these filters.</p>
      </div>
    );
  }

  return (
    <>
      <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4 md:gap-6">
        {feedItems.map((item) => {
          const sent = SENTIMENT_STYLE[(item.sentiment_label || '').toLowerCase()] || SENTIMENT_STYLE.neutral;
          // Bar = positivity: negative trends toward 0, neutral ~50%, positive
          // toward 100%. sentiment_score from the view is already 0..100 (50 =
          // neutral). Small floor so a strongly-negative post keeps a sliver of
          // visible color instead of vanishing entirely.
          const score = item.sentiment_score ?? 50;
          const width = Math.max(4, Math.min(100, Math.round(score)));
          return (
          <div key={item.id} className="bg-white dark:bg-slate-900 rounded-xl p-4 shadow-sm border border-slate-100 dark:border-slate-800 flex flex-col group">
            <div className="flex justify-between items-start mb-3">
              <div className="flex items-center gap-3">
                <div className={`w-10 h-10 rounded-full flex items-center justify-center text-sm font-bold shrink-0 ${getColorClasses(item.color)}`}>
                  {item.author_initials}
                </div>
                <div>
                  <p className="text-sm font-bold text-slate-900 dark:text-white">{item.author_name}</p>
                  <div className="flex items-center gap-2 text-xs text-slate-500">
                    <p>{timeAgo(item.created_at)}</p>
                    <span className="w-1 h-1 rounded-full bg-slate-300"></span>
                    <p className="flex items-center gap-0.5"><span className="material-symbols-outlined text-[12px]">place</span> {item.location}</p>
                  </div>
                </div>
              </div>
              <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-[10px] font-semibold ring-1 ring-inset shrink-0 uppercase tracking-wide ${getBadgeClasses(item.color)}`}>
                {item.topic}
              </span>
            </div>

            <p className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed mb-4 flex-1">
              {item.content}
            </p>

            <div className="mt-auto">
              <div className="flex justify-between text-[10px] uppercase font-bold tracking-wider text-slate-400 mb-1.5">
                <span>Sentiment Analysis</span>
                <span className={sent.text}>{item.sentiment_label}</span>
              </div>
              <div className="h-2 w-full bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden">
                <div className={`h-full rounded-full ${sent.bar}`} style={{ width: `${width}%` }}></div>
              </div>
            </div>
          </div>
          );
        })}
      </div>

      {/* Infinite-scroll sentinel + status. Only mounted while more pages remain. */}
      {hasMore && (
        <div className="flex items-center justify-center py-8">
          <div className="w-7 h-7 border-4 border-primary border-t-transparent rounded-full animate-spin"></div>
        </div>
      )}
      {!hasMore && feedItems.length > PAGE_SIZE && (
        <p className="text-center text-xs text-slate-400 py-8">You've reached the end of the feed.</p>
      )}
    </>
  );
}
