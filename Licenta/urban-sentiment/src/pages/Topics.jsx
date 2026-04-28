import { useState, useEffect } from 'react';
import { supabase } from '../supabaseClient';

export default function Topics() {
  const [topics, setTopics] = useState([]);
  const [allFeedbacks, setAllFeedbacks] = useState([]);
  const [selectedTopic, setSelectedTopic] = useState(null);
  const [filter, setFilter] = useState('All Topics');
  const [search, setSearch] = useState('');
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

    setAllFeedbacks(data);

    // Aggregate topics
    const topicMap = {};
    data.forEach(f => {
      if (!topicMap[f.topic]) topicMap[f.topic] = { name: f.topic, count: 0, scores: [], feedbacks: [] };
      topicMap[f.topic].count++;
      topicMap[f.topic].scores.push(f.sentiment_score || 0);
      topicMap[f.topic].feedbacks.push(f);
    });

    const aggregated = Object.values(topicMap).map(t => ({
      ...t,
      avgScore: Math.round(t.scores.reduce((a, b) => a + b, 0) / t.scores.length),
      pct: Math.round((t.count / data.length) * 100),
    })).sort((a, b) => b.count - a.count);

    setTopics(aggregated);
    if (aggregated.length > 0) setSelectedTopic(aggregated[0]);
    setLoading(false);
  }

  const categories = ['All Topics', ...topics.map(t => t.name)];
  const filteredTopics = topics.filter(t => {
    if (filter !== 'All Topics' && t.name !== filter) return false;
    if (search && !t.name.toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  });

  const sentimentTrend = (score) => {
    if (score >= 80) return { icon: 'trending_up', cls: 'text-rose-600 bg-rose-50 dark:bg-rose-900/30', pct: '+' };
    if (score >= 60) return { icon: 'trending_flat', cls: 'text-slate-600 bg-slate-100 dark:bg-slate-800', pct: '~' };
    return { icon: 'trending_down', cls: 'text-emerald-600 bg-emerald-50 dark:bg-emerald-900/30', pct: '+' };
  };

  const barColor = (i) => {
    const colors = ['bg-primary', 'bg-rose-500', 'bg-amber-500', 'bg-emerald-500', 'bg-purple-500', 'bg-teal-500'];
    return colors[i % colors.length];
  };

  const mostPositive = topics.length ? topics.reduce((a, b) => a.avgScore < b.avgScore ? a : b) : null;
  const mostNegative = topics.length ? topics.reduce((a, b) => a.avgScore > b.avgScore ? a : b) : null;

  function timeAgo(dateStr) {
    const diff = Math.floor((Date.now() - new Date(dateStr)) / 1000);
    if (diff < 60) return `${diff}s ago`;
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
    return `${Math.floor(diff / 86400)}d ago`;
  }

  return (
    <div className="flex flex-col gap-6">
      
      {/* Search and Filters */}
      <div className="flex flex-col md:flex-row gap-4">
        <div className="relative flex-1">
          <span className="material-symbols-outlined absolute left-4 top-1/2 -translate-y-1/2 text-slate-400">search</span>
          <input 
            type="text" 
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search topics, keywords..." 
            className="w-full pl-11 pr-4 py-3 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl focus:ring-2 focus:ring-primary focus:outline-none dark:text-white"
          />
        </div>

        <div className="flex gap-2 overflow-x-auto hide-scrollbar md:w-auto">
          {categories.slice(0, 5).map((cat) => (
            <button
              key={cat}
              onClick={() => setFilter(cat)}
              className={`whitespace-nowrap px-4 py-2 font-semibold rounded-lg text-sm transition-colors ${
                filter === cat
                  ? 'bg-slate-900 dark:bg-white text-white dark:text-slate-900 shadow-sm'
                  : 'bg-white dark:bg-slate-900 text-slate-600 dark:text-slate-300 border border-slate-200 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800'
              }`}
            >
              {cat}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Trending Topics List */}
        <div className="lg:col-span-1 space-y-4">
          <h2 className="text-lg font-bold text-slate-900 dark:text-white flex items-center gap-2">
            <span className="material-symbols-outlined text-rose-500">local_fire_department</span>
            Trending Now
          </h2>
          
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <div className="w-8 h-8 border-4 border-primary border-t-transparent rounded-full animate-spin"></div>
            </div>
          ) : filteredTopics.map((topic, i) => {
            const trend = sentimentTrend(topic.avgScore);
            const isSelected = selectedTopic?.name === topic.name;
            return (
              <div
                key={topic.name}
                onClick={() => setSelectedTopic(topic)}
                className={`bg-white dark:bg-slate-900 rounded-xl p-4 shadow-sm border flex flex-col gap-3 group cursor-pointer transition-colors relative overflow-hidden ${
                  isSelected ? 'border-primary' : 'border-slate-100 dark:border-slate-800 hover:border-primary/50'
                }`}
              >
                <div className={`absolute left-0 top-0 bottom-0 w-1 ${barColor(i)} ${isSelected ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'} transition-opacity`}></div>
                <div className="flex justify-between items-start">
                  <div>
                    <h3 className={`font-bold text-slate-900 dark:text-white transition-colors ${isSelected ? 'text-primary' : 'group-hover:text-primary'}`}>{topic.name}</h3>
                    <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">{topic.count} mention{topic.count !== 1 ? 's' : ''}</p>
                  </div>
                  <div className={`flex items-center gap-1 px-2 py-1 rounded font-bold text-xs ${trend.cls}`}>
                    <span className="material-symbols-outlined text-[14px]">{trend.icon}</span>
                    {topic.avgScore}
                  </div>
                </div>
                <div className="w-full bg-slate-100 dark:bg-slate-800 rounded-full h-1.5 mt-2">
                  <div className={`h-1.5 rounded-full ${barColor(i)}`} style={{ width: `${topic.pct}%` }}></div>
                </div>
              </div>
            );
          })}
        </div>

        {/* Topic Deep Dive */}
        <div className="lg:col-span-2 space-y-6">
          <div className="bg-white dark:bg-slate-900 rounded-xl p-6 shadow-sm border border-slate-100 dark:border-slate-800">
            <div className="flex justify-between items-start mb-6">
              <h3 className="text-lg font-bold text-slate-900 dark:text-white">
                {selectedTopic ? `${selectedTopic.name} — Deep Dive` : 'Topic Deep Dive'}
              </h3>
            </div>
            
            {!selectedTopic ? (
              <div className="flex flex-col items-center justify-center p-8 border border-dashed border-slate-200 dark:border-slate-700 rounded-xl bg-slate-50 dark:bg-slate-800/50">
                <div className="w-16 h-16 bg-blue-100 text-blue-500 rounded-full flex items-center justify-center mb-4">
                  <span className="material-symbols-outlined text-3xl">insights</span>
                </div>
                <p className="text-slate-500 text-center font-medium">Select a topic from the left to view detailed analysis.</p>
              </div>
            ) : (
              <div className="space-y-4">
                <div className="grid grid-cols-3 gap-4">
                  <div className="bg-slate-50 dark:bg-slate-800/50 rounded-lg p-3 text-center">
                    <p className="text-xs text-slate-500 font-bold uppercase tracking-wider mb-1">Mentions</p>
                    <p className="text-2xl font-bold text-slate-900 dark:text-white">{selectedTopic.count}</p>
                  </div>
                  <div className="bg-slate-50 dark:bg-slate-800/50 rounded-lg p-3 text-center">
                    <p className="text-xs text-slate-500 font-bold uppercase tracking-wider mb-1">Avg Score</p>
                    <p className="text-2xl font-bold text-slate-900 dark:text-white">{selectedTopic.avgScore}</p>
                  </div>
                  <div className="bg-slate-50 dark:bg-slate-800/50 rounded-lg p-3 text-center">
                    <p className="text-xs text-slate-500 font-bold uppercase tracking-wider mb-1">Share</p>
                    <p className="text-2xl font-bold text-slate-900 dark:text-white">{selectedTopic.pct}%</p>
                  </div>
                </div>
                <div className="space-y-3 max-h-64 overflow-y-auto">
                  {selectedTopic.feedbacks.map(fb => (
                    <div key={fb.id} className="p-3 bg-slate-50 dark:bg-slate-800/50 rounded-lg border border-slate-100 dark:border-slate-800">
                      <div className="flex justify-between mb-1">
                        <p className="text-sm font-semibold text-slate-900 dark:text-white">{fb.author_name}</p>
                        <span className="text-[10px] text-slate-400">{timeAgo(fb.created_at)}</span>
                      </div>
                      <p className="text-xs text-slate-600 dark:text-slate-400 line-clamp-2">{fb.content}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="bg-white dark:bg-slate-900 p-4 rounded-xl shadow-sm border border-slate-100 dark:border-slate-800">
              <p className="text-xs text-slate-500 font-bold uppercase tracking-wider mb-1">Most Positive</p>
              <p className="font-bold text-emerald-600">{loading ? '…' : (mostPositive?.name || '—')}</p>
              {mostPositive && <p className="text-xs text-slate-400 mt-1">Avg score: {mostPositive.avgScore}</p>}
            </div>
            <div className="bg-white dark:bg-slate-900 p-4 rounded-xl shadow-sm border border-slate-100 dark:border-slate-800">
              <p className="text-xs text-slate-500 font-bold uppercase tracking-wider mb-1">Most Negative</p>
              <p className="font-bold text-rose-600">{loading ? '…' : (mostNegative?.name || '—')}</p>
              {mostNegative && <p className="text-xs text-slate-400 mt-1">Avg score: {mostNegative.avgScore}</p>}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
