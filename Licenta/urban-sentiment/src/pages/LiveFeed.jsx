import { useState, useEffect } from 'react';
import { supabase } from '../supabaseClient';

export default function LiveFeed() {
  const [feedItems, setFeedItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchFeedbacks();

    // Set up real-time subscription
    const channel = supabase
      .channel('feedbacks-live')
      .on('postgres_changes', { event: 'INSERT', schema: 'public', table: 'feedbacks' }, (payload) => {
        setFeedItems((prev) => [payload.new, ...prev]);
      })
      .subscribe();

    return () => {
      supabase.removeChannel(channel);
    };
  }, []);

  async function fetchFeedbacks() {
    setLoading(true);
    const { data, error } = await supabase
      .from('feedbacks')
      .select('*')
      .order('created_at', { ascending: false })
      .limit(50);

    if (error) {
      setError(error.message);
    } else {
      setFeedItems(data);
    }
    setLoading(false);
  }

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

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4 md:gap-6">
      {feedItems.map((item) => (
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
          
          <div className="mb-4">
            <div className="flex justify-between text-[10px] uppercase font-bold tracking-wider text-slate-400 mb-1.5">
              <span>Sentiment Analysis</span>
              <span className={item.sentiment_color}>{item.sentiment_label}</span>
            </div>
            <div className="h-2 w-full bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden flex">
              <div className={`h-full bg-gradient-to-r ${item.sentiment_gradient} rounded-full`} style={{ width: `${item.sentiment_score}%` }}></div>
            </div>
          </div>
          
          <div className="flex items-center justify-between border-t border-slate-100 dark:border-slate-800 pt-3 mt-auto">
            <button className="flex items-center gap-1.5 text-slate-500 hover:text-red-500 transition-colors text-xs font-medium">
              <span className="material-symbols-outlined text-[18px]">flag</span>
              Flag
            </button>
            <button className="flex items-center gap-1.5 text-slate-500 hover:text-primary transition-colors text-xs font-medium">
              <span className="material-symbols-outlined text-[18px]">assignment_ind</span>
              Assign
            </button>
            <button className="flex items-center gap-1.5 text-slate-500 hover:text-primary transition-colors text-xs font-medium">
              <span className="material-symbols-outlined text-[18px]">info</span>
              Context
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
