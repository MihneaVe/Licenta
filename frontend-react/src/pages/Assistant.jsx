import { useState, useRef, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { useOutletContext } from 'react-router-dom';
import Markdown from '../components/Markdown';

// FastAPI backend (the RAG pipeline).
const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const SUGGESTIONS = [
  'What are residents most upset about right now?',
  'Summarize the main transport complaints.',
  'Which areas get the most negative feedback?',
  'What positive things are people saying?',
];

// The model cites posts inline as [1], [1, 5] to match the numbered context.
// We hide those markers and surface the quotes via the "See posts" modal instead.
const stripCitations = (t) => (t || '').replace(/\s*\[\d+(?:\s*,\s*\d+)*\]/g, '');

const SENTIMENT_BADGE = {
  Positive: 'text-emerald-700 bg-emerald-100 dark:text-emerald-300 dark:bg-emerald-900/30',
  Negative: 'text-rose-700 bg-rose-100 dark:text-rose-300 dark:bg-rose-900/30',
  Neutral: 'text-slate-600 bg-slate-100 dark:text-slate-300 dark:bg-slate-800',
};

// Modal listing the actual citizen-feedback posts an answer was grounded on.
function PostsModal({ posts, onClose }) {
  if (!posts) return null;
  // Portal to <body> so an ancestor's transform/overflow can't clip or
  // re-anchor the fixed overlay.
  return createPortal(
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-4" onClick={onClose}>
      <div className="absolute inset-0 bg-black/50 backdrop-blur-sm animate-fade-in" />
      <div
        className="relative w-full max-w-2xl max-h-[80vh] flex flex-col rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 shadow-2xl animate-scale-in"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 py-3.5 border-b border-slate-100 dark:border-slate-800">
          <h3 className="text-sm font-bold text-slate-900 dark:text-white flex items-center gap-2">
            <span className="material-symbols-outlined text-[18px] text-primary">forum</span>
            {posts.length} source post{posts.length === 1 ? '' : 's'}
          </h3>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-700 dark:hover:text-slate-200" aria-label="Close">
            <span className="material-symbols-outlined text-[20px]">close</span>
          </button>
        </div>
        <div className="overflow-y-auto px-5 py-4 space-y-3">
          {posts.map((p) => (
            <div key={p.id} className="rounded-xl border border-slate-100 dark:border-slate-800 bg-slate-50/60 dark:bg-slate-800/30 p-3.5">
              <div className="flex items-center gap-2 mb-1.5 text-[11px]">
                <span className="font-semibold text-slate-400">#{p.n}</span>
                {p.location && <span className="font-medium text-slate-600 dark:text-slate-300">{p.location}</span>}
                {p.topic && <span className="text-slate-400">· {p.topic}</span>}
                {p.sentiment_label && (
                  <span className={`ml-auto px-1.5 py-0.5 rounded-full font-medium ${SENTIMENT_BADGE[p.sentiment_label] || SENTIMENT_BADGE.Neutral}`}>
                    {p.sentiment_label}
                  </span>
                )}
              </div>
              <p className="text-sm text-slate-700 dark:text-slate-200 leading-relaxed">{p.content}</p>
              {p.url && (
                <a href={p.url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 mt-2 text-[11px] text-primary hover:underline">
                  <span className="material-symbols-outlined text-[13px]">open_in_new</span> source
                </a>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>,
    document.body,
  );
}

export default function Assistant() {
  const { districts = [], fromDate, toDate, fromISO, toISO } = useOutletContext() || {};
  const [messages, setMessages] = useState([]); // { role, content, meta?, statusText?, feedback? }
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [modalPosts, setModalPosts] = useState(null); // posts shown in the "See posts" modal
  const endRef = useRef(null);

  // Stable per-tab session id so feedback rows can be grouped for offline eval.
  const sessionId = useRef(
    (typeof crypto !== 'undefined' && crypto.randomUUID)
      ? crypto.randomUUID()
      : String(Date.now()),
  ).current;

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  // ----------------------------------------------------------------- sending
  async function send(text) {
    const question = (text ?? input).trim();
    if (!question || loading) return;
    setInput('');
    const history = messages.slice(-8).map((m) => ({ role: m.role, content: m.content }));

    // Append the user turn + an empty assistant placeholder we stream into.
    setMessages((prev) => [
      ...prev,
      { role: 'user', content: question },
      { role: 'assistant', content: '', meta: { streaming: true } },
    ]);
    setLoading(true);

    // Always edits the trailing assistant placeholder.
    const patchLast = (patch) =>
      setMessages((prev) => {
        const copy = prev.slice();
        const last = copy[copy.length - 1];
        copy[copy.length - 1] = typeof patch === 'function' ? patch(last) : { ...last, ...patch };
        return copy;
      });

    try {
      // Retrieval now happens server-side (hybrid pgvector + BM25 + rerank).
      // We only send the question, recent history, and the dashboard filters.
      const resp = await fetch(`${API_URL}/api/chat/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question,
          history,
          filters: {
            districts: districts.length ? districts : null,
            from: fromISO || null,
            to: toISO || null,
          },
        }),
      });

      // Connection-time failures come back as a JSON 503 (not a stream).
      if (!resp.ok || !resp.body) {
        const data = await resp.json().catch(() => ({}));
        patchLast({
          content: data.answer || 'The assistant is unavailable right now.',
          meta: { error: data.error || 'unavailable' },
        });
        return;
      }

      // Read the NDJSON event stream.
      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let answer = '';
      let info = {};
      let streamError = null;

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        let nl;
        while ((nl = buffer.indexOf('\n')) >= 0) {
          const line = buffer.slice(0, nl).trim();
          buffer = buffer.slice(nl + 1);
          if (!line) continue;
          let evt;
          try { evt = JSON.parse(line); } catch { continue; }

          if (evt.type === 'status') {
            // Progress text shown before the first token arrives.
            patchLast((m) => ({ ...m, statusText: evt.text }));
          } else if (evt.type === 'meta') {
            info = {
              used: evt.used_posts,
              model: evt.model,
              contextScore: evt.context_score,
              retrievalRounds: evt.retrieval_rounds,
              posts: evt.posts || [],
            };
            patchLast((m) => ({ ...m, statusText: null, meta: { ...m.meta, ...info } }));
          } else if (evt.type === 'token') {
            answer += evt.text;
            patchLast((m) => ({ ...m, content: answer, statusText: null }));
          } else if (evt.type === 'citations') {
            patchLast((m) => ({
              ...m,
              meta: {
                ...m.meta,
                post_ids: evt.post_ids,
                contextScore: evt.context_score,
                answerScore: evt.answer_score,
              },
            }));
          } else if (evt.type === 'error') {
            streamError = evt;
          }
        }
      }

      if (streamError) {
        patchLast((m) => ({
          ...m,
          content: answer || streamError.message || 'The assistant hit an error.',
          meta: { ...m.meta, error: streamError.code || 'error', streaming: false, ...info },
        }));
      } else {
        patchLast((m) => ({
          ...m,
          content: answer || m.content || 'No response.',
          meta: { ...m.meta, streaming: false, ...info },
        }));
      }
    } catch {
      patchLast({
        content: `Couldn't reach the assistant backend at ${API_URL}. Is the backend running?`,
        meta: { error: 'network' },
      });
    } finally {
      setLoading(false);
    }
  }

  // ---------------------------------------------------------------- feedback
  // Thumbs up/down → POST /api/rag/feedback/. Stored in Supabase (rag_feedback)
  // for offline eval and to re-weight retrieval (boost/bury cited posts).
  async function submitFeedback(messageIndex, rating) {
    const msg = messages[messageIndex];
    const prevUser = messages[messageIndex - 1];
    if (!msg || !prevUser || msg.feedback) return;

    // Optimistic UI update.
    setMessages((prev) => {
      const copy = [...prev];
      copy[messageIndex] = { ...copy[messageIndex], feedback: rating };
      return copy;
    });

    try {
      await fetch(`${API_URL}/api/rag/feedback/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          question: (prevUser.content || '').slice(0, 2000),
          answer: (msg.content || '').slice(0, 8000),
          retrieved_post_ids: msg.meta?.post_ids || [],
          rating,
          context_score: msg.meta?.contextScore ?? null,
          answer_score: msg.meta?.answerScore ?? null,
        }),
      });
    } catch {
      // Non-critical — silently ignore network errors on feedback.
    }
  }

  function onKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  }

  const quarterScope =
    districts.length === 0 ? 'All quarters'
    : districts.length === 1 ? districts[0]
    : `${districts.length} quarters`;
  const dateScope =
    fromDate && toDate ? `${fromDate} → ${toDate}`
    : fromDate ? `from ${fromDate}`
    : toDate ? `until ${toDate}`
    : 'all dates';
  const scope = `${quarterScope} · ${dateScope}`;

  return (
    <div className="flex flex-col flex-1 min-h-0">
      {/* Scope + reset */}
      <div className="flex items-center justify-between gap-3 mb-4">
        <div className="flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
          <span className="material-symbols-outlined text-[16px] text-primary">database</span>
          <span>RAG-grounded on live feedback — <span className="font-semibold text-slate-700 dark:text-slate-300">{scope}</span></span>
        </div>
        {messages.length > 0 && (
          <button
            onClick={() => !loading && setMessages([])}
            className="flex items-center gap-1 text-xs font-medium text-slate-500 hover:text-red-500 transition-colors disabled:opacity-40"
            disabled={loading}
          >
            <span className="material-symbols-outlined text-[16px]">restart_alt</span>
            Clear
          </button>
        )}
      </div>

      {/* Messages */}
      <div className="flex-1 min-h-0 overflow-y-auto space-y-4 pr-1">
        {messages.length === 0 && (
          <div className="h-full flex flex-col items-center justify-center text-center px-4">
            <div className="w-14 h-14 rounded-2xl bg-primary/10 border border-primary/20 flex items-center justify-center mb-4">
              <span className="material-symbols-outlined text-primary text-[30px]">smart_toy</span>
            </div>
            <h3 className="text-lg font-bold text-slate-900 dark:text-white">Ask the City Assistant</h3>
            <p className="text-sm text-slate-500 dark:text-slate-400 mt-1 max-w-md">
              Ask anything about what residents are reporting. Answers use hybrid retrieval
              (vector + keyword), cross-encoder reranking, and a local LLM that grades its own
              context and answer.
            </p>
            <div className="grid sm:grid-cols-2 gap-2 mt-6 w-full max-w-xl">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  onClick={() => send(s)}
                  className="text-left text-sm px-3.5 py-2.5 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-slate-700 dark:text-slate-300 hover:border-primary/40 hover:bg-primary/5 transition-colors"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m, i) => {
          const isStreaming = loading && i === messages.length - 1 && m.role === 'assistant';
          if (m.role === 'user') {
            return (
              <div key={i} className="flex justify-end animate-slide-up">
                <div className="max-w-[85%] md:max-w-[75%] rounded-2xl rounded-br-sm bg-primary text-white px-4 py-2.5 text-sm shadow-sm whitespace-pre-wrap">
                  {m.content}
                </div>
              </div>
            );
          }
          return (
            <div key={i} className="flex justify-start gap-2.5 animate-slide-up">
              <div className="w-8 h-8 shrink-0 rounded-full bg-primary/10 border border-primary/20 flex items-center justify-center">
                <span className="material-symbols-outlined text-primary text-[18px]">smart_toy</span>
              </div>
              <div className="max-w-[85%] md:max-w-[75%]">
                <div
                  className={`rounded-2xl rounded-bl-sm px-4 py-2.5 text-sm shadow-sm ${
                    m.meta?.error
                      ? 'bg-amber-50 dark:bg-amber-900/20 text-amber-800 dark:text-amber-200 border border-amber-200 dark:border-amber-900/40'
                      : 'bg-white dark:bg-slate-900 text-slate-700 dark:text-slate-200 border border-slate-100 dark:border-slate-800'
                  }`}
                >
                  {m.content ? (
                    <>
                      <Markdown>{stripCitations(m.content)}</Markdown>
                      {isStreaming && <span className="inline-block w-1.5 h-4 ml-0.5 -mb-0.5 bg-primary/70 animate-pulse align-text-bottom" />}
                    </>
                  ) : m.statusText ? (
                    <span className="flex items-center gap-2 text-slate-400 dark:text-slate-500 text-xs italic py-0.5">
                      <span className="w-3 h-3 rounded-full border-2 border-primary/40 border-t-primary animate-spin shrink-0" />
                      {m.statusText}
                    </span>
                  ) : (
                    <div className="flex gap-1 py-1">
                      <span className="w-2 h-2 rounded-full bg-slate-300 dark:bg-slate-600 animate-bounce [animation-delay:-0.3s]"></span>
                      <span className="w-2 h-2 rounded-full bg-slate-300 dark:bg-slate-600 animate-bounce [animation-delay:-0.15s]"></span>
                      <span className="w-2 h-2 rounded-full bg-slate-300 dark:bg-slate-600 animate-bounce"></span>
                    </div>
                  )}
                </div>

                {/* Footer: grounding info + thumbs feedback */}
                {!m.meta?.error && !isStreaming && m.meta?.used != null && (
                  <div className="flex items-center gap-3 mt-1 ml-1">
                    <p className="text-[11px] text-slate-400">
                      {m.meta.used} post{m.meta.used === 1 ? '' : 's'}
                      {m.meta.model ? ` · ${m.meta.model}` : ''}
                      {m.meta.contextScore != null ? ` · ctx ${m.meta.contextScore}/5` : ''}
                      {m.meta.answerScore != null ? ` · grounding ${m.meta.answerScore}/5` : ''}
                      {m.meta.retrievalRounds > 1 ? ` · ${m.meta.retrievalRounds} retrieval rounds` : ''}
                    </p>

                    {/* See posts — opens the grounding quotes in a modal */}
                    {m.meta.posts?.length > 0 && (
                      <button
                        onClick={() => setModalPosts(m.meta.posts)}
                        className="flex items-center gap-1 text-[11px] font-medium text-primary hover:underline"
                      >
                        <span className="material-symbols-outlined text-[14px]">forum</span>
                        See {m.meta.posts.length} posts
                      </button>
                    )}

                    {/* Thumbs up/down — only on fully rendered answers */}
                    {m.content && (
                      <div className="flex gap-1">
                        <button
                          onClick={() => submitFeedback(i, 'up')}
                          title="Good answer"
                          disabled={!!m.feedback}
                          className={`transition-all disabled:cursor-default ${
                            m.feedback === 'up'
                              ? 'text-emerald-500'
                              : m.feedback === 'down'
                              ? 'text-slate-300 dark:text-slate-700'
                              : 'text-slate-400 hover:text-emerald-500'
                          }`}
                        >
                          <span className="material-symbols-outlined text-[15px]">thumb_up</span>
                        </button>
                        <button
                          onClick={() => submitFeedback(i, 'down')}
                          title="Bad answer"
                          disabled={!!m.feedback}
                          className={`transition-all disabled:cursor-default ${
                            m.feedback === 'down'
                              ? 'text-rose-500'
                              : m.feedback === 'up'
                              ? 'text-slate-300 dark:text-slate-700'
                              : 'text-slate-400 hover:text-rose-500'
                          }`}
                        >
                          <span className="material-symbols-outlined text-[15px]">thumb_down</span>
                        </button>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          );
        })}
        <div ref={endRef} />
      </div>

      {/* Composer */}
      <div className="mt-4 flex items-end gap-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-2 shadow-sm">
        <textarea
          rows={1}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder="Ask about the city's feedback…"
          className="flex-1 resize-none bg-transparent px-2 py-1.5 text-sm text-slate-800 dark:text-slate-100 placeholder:text-slate-400 focus:outline-none max-h-32"
        />
        <button
          onClick={() => send()}
          disabled={loading || !input.trim()}
          className="shrink-0 w-10 h-10 rounded-xl bg-primary text-white flex items-center justify-center hover:bg-blue-600 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          aria-label="Send"
        >
          <span className="material-symbols-outlined text-[20px]">{loading ? 'hourglass_empty' : 'send'}</span>
        </button>
      </div>

      {/* Source-posts modal */}
      <PostsModal posts={modalPosts} onClose={() => setModalPosts(null)} />
    </div>
  );
}
