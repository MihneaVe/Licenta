import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { supabase } from '../supabaseClient';

export default function Overview() {
  const [stats, setStats] = useState({ total: 0, avgScore: 0, topTopic: '—', alertCount: 0 });
  const [recentFeedbacks, setRecentFeedbacks] = useState([]);
  const [topicCounts, setTopicCounts] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchData();
  }, []);

  async function fetchData() {
    setLoading(true);

    const { data, error } = await supabase
      .from('feedbacks')
      .select('*')
      .order('created_at', { ascending: false });

    if (error || !data) { setLoading(false); return; }

    const total = data.length;
    const avgScore = total > 0 ? Math.round(data.reduce((s, f) => s + (f.sentiment_score || 0), 0) / total) : 0;
    
    // Count negative/critical alerts
    const alertCount = data.filter(f => f.sentiment_label === 'Negative' || f.sentiment_label === 'Critical').length;

    // Topic distribution
    const topicMap = {};
    data.forEach(f => { topicMap[f.topic] = (topicMap[f.topic] || 0) + 1; });
    const sortedTopics = Object.entries(topicMap).sort((a, b) => b[1] - a[1]);
    const topTopic = sortedTopics[0]?.[0] || '—';

    // Topic counts for pie chart
    const topTopics = sortedTopics.slice(0, 3).map(([name, count]) => ({
      name,
      pct: Math.round((count / total) * 100),
    }));

    setStats({ total, avgScore, topTopic, alertCount });
    setTopicCounts(topTopics);
    setRecentFeedbacks(data.slice(0, 3));
    setLoading(false);
  }

  function timeAgo(dateStr) {
    const diff = Math.floor((Date.now() - new Date(dateStr)) / 1000);
    if (diff < 60) return `${diff}s ago`;
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
    return `${Math.floor(diff / 86400)}d ago`;
  }

  const sentimentColor = (label) => {
    if (label === 'Positive') return 'text-green-600 dark:text-green-400 bg-emerald-100 dark:bg-emerald-900/30';
    if (label === 'Negative' || label === 'Critical') return 'text-red-600 dark:text-red-400 bg-red-100 dark:bg-red-900/30';
    return 'text-yellow-600 dark:text-yellow-400 bg-yellow-100 dark:bg-yellow-900/30';
  };

  return (
    <div className="flex flex-col gap-6 lg:gap-8">
      
      {/* City Score Banner - Mobile */}
      <div className="md:hidden bg-gradient-to-r from-primary to-blue-400 rounded-2xl p-6 text-white shadow-lg relative overflow-hidden">
        <div className="relative z-10 flex justify-between items-center">
          <div>
            <h2 className="text-sm font-medium opacity-90 mb-1">Overall Sentiment</h2>
            <div className="flex items-baseline gap-2">
              <span className="text-4xl font-extrabold tracking-tight">{loading ? '…' : stats.avgScore}</span>
              <span className="text-sm font-medium opacity-80">/100</span>
            </div>
          </div>
          <div className="w-16 h-16 bg-white/20 rounded-full flex items-center justify-center backdrop-blur-sm">
            <span className="material-symbols-outlined text-4xl">trending_up</span>
          </div>
        </div>
        <div className="absolute top-0 right-0 -mt-8 -mr-8 w-32 h-32 bg-white opacity-10 rounded-full blur-2xl"></div>
        <div className="absolute bottom-0 left-0 -mb-8 -ml-8 w-24 h-24 bg-white opacity-10 rounded-full blur-xl"></div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 lg:gap-6">
        <div className="bg-white dark:bg-slate-900 p-4 md:p-6 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm">
          <div className="flex items-center justify-between mb-2 md:mb-4">
            <div className="p-2 bg-blue-50 dark:bg-blue-900/30 text-blue-600 rounded-lg hidden md:block">
              <span className="material-symbols-outlined">forum</span>
            </div>
            <span className="hidden md:inline-block text-emerald-500 text-xs font-bold bg-emerald-50 dark:bg-emerald-900/30 px-2 py-1 rounded-full">Live</span>
          </div>
          <p className="hidden md:block text-slate-500 text-sm font-medium">Total Feedbacks</p>
          <h3 className="text-2xl font-bold mt-1 text-slate-900 dark:text-white">
            {loading ? '…' : stats.total.toLocaleString()}
          </h3>
        </div>
        
        <div className="bg-white dark:bg-slate-900 p-4 md:p-6 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm">
          <div className="flex items-center justify-between mb-2 md:mb-4">
            <div className="p-2 bg-purple-50 dark:bg-purple-900/30 text-purple-600 rounded-lg hidden md:block">
              <span className="material-symbols-outlined">mood</span>
            </div>
            <span className="hidden md:inline-block text-emerald-500 text-xs font-bold bg-emerald-50 dark:bg-emerald-900/30 px-2 py-1 rounded-full">Score</span>
          </div>
          <p className="hidden md:block text-slate-500 text-sm font-medium">Avg Sentiment Score</p>
          <h3 className="text-2xl font-bold mt-1 text-slate-900 dark:text-white">
            {loading ? '…' : stats.avgScore}<span className="hidden md:inline">/100</span>
          </h3>
        </div>
        
        <div className="bg-white dark:bg-slate-900 p-4 md:p-6 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm">
          <div className="flex items-center justify-between mb-2 md:mb-4">
            <div className="p-2 bg-amber-50 dark:bg-amber-900/30 text-amber-600 rounded-lg hidden md:block">
              <span className="material-symbols-outlined">trending_up</span>
            </div>
          </div>
          <p className="hidden md:block text-slate-500 text-sm font-medium">Top Topic</p>
          <h3 className="text-2xl font-bold mt-1 truncate text-slate-900 dark:text-white">
            <span className="hidden md:inline">{loading ? '…' : stats.topTopic}</span>
            <span className="md:hidden">{loading ? '…' : stats.total}</span>
          </h3>
        </div>
        
        <div className="bg-white dark:bg-slate-900 p-4 md:p-6 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm">
          <div className="flex items-center justify-between mb-2 md:mb-4">
            <div className="p-2 bg-rose-50 dark:bg-rose-900/30 text-rose-600 rounded-lg hidden md:block">
              <span className="material-symbols-outlined">warning</span>
            </div>
            {!loading && stats.alertCount > 0 && (
              <span className="hidden md:inline-block text-rose-500 text-xs font-bold bg-rose-50 dark:bg-rose-900/30 px-2 py-1 rounded-full">Alert</span>
            )}
          </div>
          <p className="hidden md:block text-slate-500 text-sm font-medium">Active Alerts</p>
          <h3 className="text-2xl font-bold mt-1 text-slate-900 dark:text-white">
            {loading ? '…' : stats.alertCount}
          </h3>
        </div>
      </div>

      {/* Mobile Action */}
      <div className="md:hidden bg-white dark:bg-slate-900 rounded-xl p-5 shadow-sm border border-slate-100 dark:border-slate-800">
        <h3 className="text-sm font-bold text-slate-900 dark:text-white mb-3">Recent Activity</h3>
        <p className="text-xs text-slate-500 dark:text-slate-400 mb-4 leading-relaxed">
          {loading ? 'Loading…' : `There are currently ${stats.alertCount} negative/critical reports.`}
        </p>
        <div className="flex gap-3">
          <Link to="/dashboard/live-feed" className="flex-1 bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200 text-xs font-semibold py-2.5 px-4 rounded-lg text-center transition-colors">
            View Live Feed
          </Link>
          <Link to="/dashboard/heatmap" className="flex-1 bg-primary hover:bg-blue-600 text-white text-xs font-semibold py-2.5 px-4 rounded-lg text-center shadow-sm transition-colors">
            View Heatmap
          </Link>
        </div>
      </div>

      {/* Topics and Feedback Row - Desktop */}
      <div className="hidden md:grid grid-cols-1 lg:grid-cols-5 gap-8">
        <div className="lg:col-span-2 bg-white dark:bg-slate-900 p-6 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm flex flex-col">
          <h3 className="text-lg font-bold mb-6">Topic Distribution</h3>
          <div className="flex-1 flex flex-col items-center justify-center relative">
            <div className="w-full space-y-4">
              {loading ? (
                <p className="text-slate-400 text-sm text-center">Loading…</p>
              ) : topicCounts.map((t, i) => {
                const colors = ['bg-primary', 'bg-emerald-400', 'bg-amber-400'];
                const dotColors = ['bg-primary', 'bg-emerald-400', 'bg-amber-400'];
                return (
                  <div key={t.name}>
                    <div className="flex items-center justify-between text-sm mb-1">
                      <div className="flex items-center gap-2">
                        <div className={`w-3 h-3 rounded-full ${dotColors[i]}`}></div>
                        <span className="font-medium">{t.name}</span>
                      </div>
                      <span className="font-bold">{t.pct}%</span>
                    </div>
                    <div className="w-full bg-slate-100 dark:bg-slate-800 rounded-full h-2">
                      <div className={`h-2 rounded-full ${colors[i]}`} style={{ width: `${t.pct}%` }}></div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        <div className="lg:col-span-3 bg-white dark:bg-slate-900 p-6 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm">
          <div className="flex items-center justify-between mb-6">
            <h3 className="text-lg font-bold">Live Feedback Feed</h3>
            <Link to="/dashboard/live-feed" className="text-primary text-sm font-semibold hover:underline">View All</Link>
          </div>
          <div className="space-y-4">
            {loading ? (
              <p className="text-slate-400 text-sm">Loading…</p>
            ) : recentFeedbacks.map((fb) => (
              <div key={fb.id} className="p-4 rounded-lg bg-slate-50 dark:bg-slate-800/50 border border-slate-100 dark:border-slate-800">
                <div className="flex gap-4">
                  <div className="w-10 h-10 rounded-full bg-blue-100 text-blue-600 flex items-center justify-center flex-shrink-0 font-bold text-sm">
                    {fb.author_initials}
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center justify-between mb-1">
                      <h4 className="font-bold text-sm">{fb.author_name}</h4>
                      <span className="text-[10px] text-slate-400 font-medium">{timeAgo(fb.created_at)}</span>
                    </div>
                    <p className="text-sm text-slate-600 dark:text-slate-400 leading-relaxed mb-3 line-clamp-2">
                      {fb.content}
                    </p>
                    <div className="flex items-center gap-3">
                      <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${sentimentColor(fb.sentiment_label)}`}>
                        {fb.sentiment_label}
                      </span>
                      <span className="text-[10px] text-slate-500 font-medium flex items-center gap-1">
                        <span className="material-symbols-outlined text-sm">tag</span> {fb.topic}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

    </div>
  );
}
