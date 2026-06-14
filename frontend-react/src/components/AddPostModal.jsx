import { useState } from 'react';
import { createPortal } from 'react-dom';
import { useAuth0 } from '@auth0/auth0-react';
import { authHeader } from '../lib/auth';

// FastAPI backend (same origin the Assistant uses).
const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const SOURCES = [
  { value: 'reddit', label: 'Reddit', icon: 'forum' },
  { value: 'x', label: 'X (Twitter)', icon: 'tag' },
];

// Manual paste ingestion - replaces the old Django /ingest/ form. Paste a
// Reddit or X post; the backend parses, cleans, and stores it, then runs
// NLP + embedding in the background so it shows up on the dashboard.
export default function AddPostModal({ onClose }) {
  const { getAccessTokenSilently } = useAuth0();
  const [source, setSource] = useState('reddit');
  const [text, setText] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const submit = async () => {
    if (!text.trim() || submitting) return;
    setSubmitting(true);
    setError(null);
    setResult(null);
    try {
      const res = await fetch(`${API_URL}/api/ingest/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...(await authHeader(getAccessTokenSilently)) },
        body: JSON.stringify({ source, text }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        setError(data.error || `Request failed (HTTP ${res.status})`);
      } else {
        setResult(data);
        setText('');
      }
    } catch {
      setError('Could not reach the UrbanPulse API. Is the backend running?');
    } finally {
      setSubmitting(false);
    }
  };

  return createPortal(
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-4" onClick={onClose}>
      <div className="absolute inset-0 bg-black/50 backdrop-blur-sm animate-fade-in" />
      <div
        className="relative w-full max-w-xl flex flex-col rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 shadow-2xl animate-scale-in"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 py-3.5 border-b border-slate-100 dark:border-slate-800">
          <h3 className="text-sm font-bold text-slate-900 dark:text-white flex items-center gap-2">
            <span className="material-symbols-outlined text-[18px] text-primary">post_add</span>
            Add Post
          </h3>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 transition-colors"
          >
            <span className="material-symbols-outlined text-[20px]">close</span>
          </button>
        </div>

        <div className="p-5 space-y-4">
          <div className="flex gap-2">
            {SOURCES.map((s) => (
              <button
                key={s.value}
                onClick={() => setSource(s.value)}
                className={`flex items-center gap-2 px-3 py-2 rounded-xl text-sm font-semibold border transition-colors ${
                  source === s.value
                    ? 'bg-primary/10 border-primary/30 text-primary dark:text-blue-400'
                    : 'border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800/50'
                }`}
              >
                <span className="material-symbols-outlined text-[18px]">{s.icon}</span>
                {s.label}
              </button>
            ))}
          </div>

          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={8}
            placeholder={`Paste the full ${source === 'reddit' ? 'Reddit post' : 'tweet'} here - title, author, and body included. The backend cleans it up automatically.`}
            className="w-full rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/50 px-3.5 py-3 text-sm text-slate-900 dark:text-white placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-primary/40 resize-none"
          />

          {error && (
            <div className="text-sm rounded-xl px-3.5 py-2.5 bg-rose-50 dark:bg-rose-900/20 text-rose-700 dark:text-rose-300 border border-rose-200 dark:border-rose-800">
              {error}
            </div>
          )}
          {result && (
            <div className="text-sm rounded-xl px-3.5 py-2.5 bg-emerald-50 dark:bg-emerald-900/20 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800">
              {result.created
                ? `Post #${result.id} added - sentiment, topic, and district are being computed in the background.`
                : `This post is already in the database (#${result.id}).`}
            </div>
          )}

          <div className="flex justify-end gap-2">
            <button
              onClick={onClose}
              className="px-4 py-2 rounded-xl text-sm font-semibold text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors"
            >
              Close
            </button>
            <button
              onClick={submit}
              disabled={!text.trim() || submitting}
              className="px-4 py-2 rounded-xl text-sm font-semibold bg-primary text-white shadow-sm hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {submitting ? 'Adding…' : 'Add post'}
            </button>
          </div>
        </div>
      </div>
    </div>,
    document.body
  );
}
