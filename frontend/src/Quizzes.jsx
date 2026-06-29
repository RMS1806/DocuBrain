import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Brain, BookOpen, ChevronRight, ChevronLeft, CheckCircle2, XCircle,
  Loader2, Plus, RefreshCw, RotateCcw, Award, List,
} from 'lucide-react';
import { API_BASE } from './api';

const getToken = () => localStorage.getItem('token');

const authFetch = async (url, opts = {}) => {
  const res = await fetch(`${API_BASE}${url}`, {
    ...opts,
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${getToken()}`, ...(opts.headers ?? {}) },
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.detail ?? `Request failed (${res.status})`);
  return body;
};

const OPTION_LETTERS = ['A', 'B', 'C', 'D'];

/* ─── Flashcard ─────────────────────────────────────────────────────────── */
const FlashCard = ({ item, onNext, onPrev, current, total }) => {
  const [flipped, setFlipped] = useState(false);
  return (
    <div className="flex flex-col items-center gap-6">
      <p className="text-xs text-terracotta-600 font-bold font-mono">{current} / {total}</p>

      <div className="w-full max-w-lg cursor-pointer" style={{ perspective: 900 }} onClick={() => setFlipped(f => !f)}>
        <motion.div animate={{ rotateY: flipped ? 180 : 0 }} transition={{ duration: 0.45, ease: 'easeInOut' }}
          style={{ transformStyle: 'preserve-3d', position: 'relative', minHeight: 200 }}>
          <div className="glass rounded-2xl p-8 flex flex-col items-center justify-center text-center min-h-[200px]"
            style={{ backfaceVisibility: 'hidden', WebkitBackfaceVisibility: 'hidden' }}>
            <BookOpen className="w-6 h-6 text-terracotta-400 mb-3" />
            <p className="text-terracotta-950 font-bold text-lg leading-relaxed">{item.content_front}</p>
            <p className="text-xs text-terracotta-500 font-semibold mt-4">Tap to reveal answer</p>
          </div>
          <div className="glass rounded-2xl p-8 flex flex-col items-center justify-center text-center min-h-[200px] absolute inset-0"
            style={{ backfaceVisibility: 'hidden', WebkitBackfaceVisibility: 'hidden', transform: 'rotateY(180deg)', background: 'rgba(245,246,238,0.80)' }}>
            <CheckCircle2 className="w-6 h-6 text-olive-600 mb-3" />
            <p className="text-terracotta-950 text-base leading-relaxed font-semibold">{item.content_back}</p>
          </div>
        </motion.div>
      </div>

      <div className="flex items-center gap-4">
        <button onClick={onPrev} disabled={current === 1}
          className="p-2 rounded-xl glass glass-hover disabled:opacity-30 text-terracotta-600 transition-all">
          <ChevronLeft className="w-5 h-5" />
        </button>
        <button onClick={() => setFlipped(f => !f)}
          className="px-5 py-2 rounded-xl bg-white/70 border border-terracotta-200 text-terracotta-800 text-sm font-bold hover:bg-white/90 transition-all">
          {flipped ? 'Hide' : 'Reveal'}
        </button>
        <button onClick={() => { setFlipped(false); onNext(); }} disabled={current === total}
          className="p-2 rounded-xl glass glass-hover disabled:opacity-30 text-terracotta-600 transition-all">
          <ChevronRight className="w-5 h-5" />
        </button>
      </div>
    </div>
  );
};

/* ─── MCQ Result ─────────────────────────────────────────────────────────── */
const MCQResult = ({ result, items, onFinish }) => {
  const pct    = ((result.score / result.total) * 100).toFixed(0);
  const passed = result.score / result.total >= 0.6;

  const optionText = (itemIdx, answerIdx) => {
    if (answerIdx == null) return 'Skipped';
    const opts = items[itemIdx]?.options;
    if (!opts || answerIdx >= opts.length) return `Option ${answerIdx}`;
    return `${OPTION_LETTERS[answerIdx]}. ${opts[answerIdx]}`;
  };

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-5 max-w-lg mx-auto">
      <div className={`glass rounded-2xl p-6 text-center border ${passed ? 'border-olive-300' : 'border-red-200'}`}>
        <div className={`w-14 h-14 rounded-full flex items-center justify-center mx-auto mb-3 ${passed ? 'bg-olive-50' : 'bg-red-50'}`}>
          {passed ? <Award className="w-7 h-7 text-olive-600" /> : <RotateCcw className="w-7 h-7 text-red-500" />}
        </div>
        <p className={`text-3xl font-black ${passed ? 'text-olive-700' : 'text-red-600'}`}>{pct}%</p>
        <p className="text-terracotta-700 text-sm mt-1 font-semibold">{result.score} / {result.total} correct</p>
      </div>

      <div className="space-y-2 max-h-96 overflow-y-auto pr-1">
        {result.breakdown?.map((r, i) => (
          <div key={i} className={`glass rounded-xl px-4 py-3 border ${r.is_correct ? 'border-olive-200' : 'border-red-200'}`}>
            <div className="flex items-start gap-2.5">
              {r.is_correct
                ? <CheckCircle2 className="w-4 h-4 text-olive-600 mt-0.5 shrink-0" />
                : <XCircle className="w-4 h-4 text-red-500 mt-0.5 shrink-0" />
              }
              <div className="flex-1 min-w-0">
                <p className="text-sm text-terracotta-950 font-bold">{r.question}</p>
                {!r.is_correct && (
                  <div className="mt-1 space-y-0.5">
                    <p className="text-xs text-red-600 font-semibold">Your answer: <span className="font-bold">{optionText(i, r.your_answer)}</span></p>
                    <p className="text-xs text-olive-700 font-semibold">Correct: <span className="font-bold">{optionText(i, r.correct_answer)}</span></p>
                  </div>
                )}
                {r.explanation && (
                  <p className="text-xs text-terracotta-600 mt-1 italic font-medium">{r.explanation}</p>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>

      <button onClick={onFinish}
        className="w-full py-2.5 rounded-xl bg-terracotta-600 hover:bg-terracotta-700 text-white font-bold text-sm flex items-center justify-center gap-2 transition-all shadow-md shadow-terracotta-200">
        <List className="w-4 h-4" /> Back to Quizzes
      </button>
    </motion.div>
  );
};

/* ─── MCQ Quiz ──────────────────────────────────────────────────────────── */
const MCQQuiz = ({ items, quizId, onFinish }) => {
  const [current, setCurrent]     = useState(0);
  const [answers, setAnswers]     = useState({});
  const [submitted, setSubmitted] = useState(false);
  const [result, setResult]       = useState(null);
  const [loading, setLoading]     = useState(false);
  const [error, setError]         = useState('');

  const item = items[current];

  const handleAnswer = (optIdx) => {
    if (submitted || answers[item.id] != null) return;
    setAnswers(p => ({ ...p, [item.id]: optIdx }));
  };

  const handleSubmit = async () => {
    setLoading(true);
    setError('');
    try {
      const orderedAnswers = items.map(it => answers[it.id] ?? null);
      const res = await authFetch(`/quiz/${quizId}/attempt`, {
        method: 'POST',
        body: JSON.stringify({ answers: orderedAnswers }),
      });
      setResult(res);
      setSubmitted(true);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  if (submitted && result) {
    return <MCQResult result={result} items={items} onFinish={onFinish} />;
  }

  const options  = item?.options ?? [];
  const selected = answers[item?.id];

  return (
    <div className="space-y-5 max-w-xl mx-auto">
      <div className="flex items-center justify-between">
        <span className="text-xs text-terracotta-700 font-bold font-mono">{current + 1} / {items.length}</span>
        <div className="flex-1 mx-4 h-1.5 bg-white/60 rounded-full overflow-hidden">
          <motion.div animate={{ width: `${((current + 1) / items.length) * 100}%` }}
            className="h-full bg-gradient-to-r from-terracotta-500 to-olive-500 rounded-full" />
        </div>
        <span className="text-xs text-terracotta-700 font-bold font-mono">{Object.keys(answers).length} answered</span>
      </div>

      <div className="glass rounded-2xl p-6">
        <p className="text-terracotta-950 font-bold text-base leading-relaxed">{item?.content_front}</p>
      </div>

      <div className="grid grid-cols-1 gap-2.5">
        {options.map((text, idx) => {
          const isSelected = selected === idx;
          return (
            <button key={idx} onClick={() => handleAnswer(idx)}
              disabled={selected != null}
              className={`w-full text-left px-4 py-3 rounded-xl border text-sm font-semibold transition-all ${
                isSelected
                  ? 'bg-terracotta-50 border-terracotta-400 text-terracotta-900 shadow-sm'
                  : selected != null
                    ? 'bg-white/30 border-terracotta-100 text-terracotta-500 cursor-not-allowed'
                    : 'glass glass-hover border-terracotta-100 text-terracotta-900 hover:border-terracotta-300'
              }`}>
              <span className="inline-flex items-center gap-2.5">
                <span className={`w-5 h-5 rounded-full border-2 flex items-center justify-center text-[10px] font-black shrink-0 ${
                  isSelected ? 'border-terracotta-500 bg-terracotta-500 text-white' : 'border-terracotta-300 text-terracotta-500'
                }`}>{OPTION_LETTERS[idx]}</span>
                {text}
              </span>
            </button>
          );
        })}
      </div>

      {error && <p className="text-red-700 text-xs bg-red-50 border border-red-200 rounded-xl px-3 py-2 font-semibold">{error}</p>}

      <div className="flex gap-3">
        <button onClick={() => setCurrent(p => Math.max(0, p - 1))} disabled={current === 0}
          className="p-2.5 rounded-xl glass glass-hover disabled:opacity-30 text-terracotta-600 transition-all">
          <ChevronLeft className="w-4 h-4" />
        </button>
        {current < items.length - 1 ? (
          <button onClick={() => setCurrent(p => p + 1)} disabled={selected == null}
            className="flex-1 py-2.5 rounded-xl bg-terracotta-600 hover:bg-terracotta-700 disabled:bg-terracotta-200 text-white font-bold text-sm flex items-center justify-center gap-2 transition-all shadow-md shadow-terracotta-200">
            Next <ChevronRight className="w-4 h-4" />
          </button>
        ) : (
          <button onClick={handleSubmit} disabled={loading || Object.keys(answers).length < items.length}
            className="flex-1 py-2.5 rounded-xl bg-terracotta-600 hover:bg-terracotta-700 disabled:bg-terracotta-200 text-white font-bold text-sm flex items-center justify-center gap-2 transition-all shadow-md shadow-terracotta-200">
            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Award className="w-4 h-4" />}
            {loading ? 'Submitting…' : 'Submit Quiz'}
          </button>
        )}
      </div>
    </div>
  );
};

/* ─── Generate form ─────────────────────────────────────────────────────── */
const GenerateForm = ({ documents, onGenerated }) => {
  const [docId, setDocId]     = useState('');
  const [type, setType]       = useState('quiz');
  const [count, setCount]     = useState(5);
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState('');
  const readyDocs = documents.filter(d => d.status === 'ready' || d.status === 'completed');

  const handleGenerate = async (e) => {
    e.preventDefault();
    if (!docId) return;
    setLoading(true);
    setError('');
    try {
      const quiz = await authFetch('/quiz/generate', {
        method: 'POST',
        body: JSON.stringify({ document_id: Number(docId), quiz_type: type, count: Number(count) }),
      });
      onGenerated(quiz);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const sel = 'w-full bg-white/90 border border-terracotta-200 rounded-xl py-2.5 px-4 text-sm text-terracotta-950 font-semibold focus:outline-none focus:border-terracotta-500 focus:ring-2 focus:ring-terracotta-100 transition-all appearance-none';

  return (
    <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}
      className="glass rounded-2xl p-6 max-w-md">
      <div className="flex items-center gap-3 mb-5">
        <div className="w-10 h-10 rounded-xl bg-terracotta-50 border border-terracotta-200 flex items-center justify-center">
          <Brain className="w-5 h-5 text-terracotta-600" />
        </div>
        <div>
          <h3 className="font-bold text-terracotta-950 text-sm">Generate Quiz</h3>
          <p className="text-terracotta-600 text-xs font-medium">AI creates questions from your document</p>
        </div>
      </div>

      {readyDocs.length === 0 ? (
        <p className="text-terracotta-700 text-sm text-center py-4 font-semibold">No processed documents yet. Upload a PDF and wait for it to be ready.</p>
      ) : (
        <form onSubmit={handleGenerate} className="space-y-4">
          <div>
            <label className="block text-xs font-bold text-terracotta-800 uppercase tracking-wider mb-1.5">Document</label>
            <select required value={docId} onChange={e => setDocId(e.target.value)} className={sel}>
              <option value="">Select a document…</option>
              {readyDocs.map(d => <option key={d.id} value={d.id}>{d.filename}</option>)}
            </select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-bold text-terracotta-800 uppercase tracking-wider mb-1.5">Type</label>
              <select value={type} onChange={e => setType(e.target.value)} className={sel}>
                <option value="quiz">MCQ Quiz</option>
                <option value="flashcard">Flashcards</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-bold text-terracotta-800 uppercase tracking-wider mb-1.5">Count (3–30)</label>
              <input type="number" min="3" max="30" value={count} onChange={e => setCount(e.target.value)} className={sel} />
            </div>
          </div>
          {error && <p className="text-red-700 text-xs bg-red-50 border border-red-200 rounded-xl px-3 py-2 font-semibold">{error}</p>}
          <button type="submit" disabled={loading || !docId}
            className="w-full py-2.5 rounded-xl bg-terracotta-600 hover:bg-terracotta-700 disabled:bg-terracotta-200 text-white font-bold text-sm flex items-center justify-center gap-2 transition-all shadow-md shadow-terracotta-200">
            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
            {loading ? 'Generating… (10–20s)' : 'Generate'}
          </button>
        </form>
      )}
    </motion.div>
  );
};

/* ─── Main ──────────────────────────────────────────────────────────────── */
export default function Quizzes({ documents }) {
  const [quizList, setQuizList]       = useState([]);
  const [loadingList, setLoadList]    = useState(true);
  const [activeQuiz, setActiveQuiz]   = useState(null);
  const [loadingQuiz, setLoadingQuiz] = useState(false);
  const [cardIndex, setCardIndex]     = useState(0);
  const [view, setView]               = useState('list');

  const fetchList = async () => {
    setLoadList(true);
    try { setQuizList(await authFetch('/quiz/')); } catch { /* ignore */ }
    finally { setLoadList(false); }
  };
  useEffect(() => { fetchList(); }, []);

  const openQuiz = async (id) => {
    setLoadingQuiz(true);
    try {
      const quiz = await authFetch(`/quiz/${id}`);
      setActiveQuiz(quiz);
      setCardIndex(0);
      setView('play');
    } catch { /* ignore */ }
    finally { setLoadingQuiz(false); }
  };

  const handleGenerated = (quiz) => {
    setQuizList(p => [quiz, ...p]);
    setActiveQuiz(quiz);
    setCardIndex(0);
    setView('play');
  };

  const handleFinish = () => { setActiveQuiz(null); setView('list'); fetchList(); };

  const items   = activeQuiz?.items ?? [];
  const isFlash = activeQuiz?.quiz_type === 'flashcard';

  return (
    <div className="space-y-6 max-w-4xl">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-black text-terracotta-950">Quizzes</h2>
          <p className="text-terracotta-700 text-sm mt-0.5 font-medium">Test your understanding with AI-generated questions</p>
        </div>
        <div className="flex gap-2">
          {view === 'play' && (
            <button onClick={() => { setActiveQuiz(null); setView('list'); }}
              className="flex items-center gap-2 px-3 py-2 rounded-xl glass glass-hover text-terracotta-700 text-xs font-bold transition-all">
              <List className="w-3.5 h-3.5" /> All Quizzes
            </button>
          )}
          <button onClick={fetchList} className="p-2 rounded-xl glass glass-hover text-terracotta-600 hover:text-terracotta-900 transition-all">
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      <AnimatePresence mode="wait">
        {view === 'list' && (
          <motion.div key="list" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="space-y-6">
            <GenerateForm documents={documents} onGenerated={handleGenerated} />
            {loadingList ? (
              <div className="flex items-center justify-center h-32 gap-2">
                <Loader2 className="w-5 h-5 text-terracotta-500 animate-spin" />
                <span className="text-terracotta-700 text-sm font-semibold">Loading quizzes…</span>
              </div>
            ) : quizList.length === 0 ? (
              <div className="glass rounded-2xl p-12 flex flex-col items-center gap-3 text-center border-2 border-dashed border-terracotta-200/60">
                <Brain className="w-8 h-8 text-terracotta-300" />
                <p className="text-terracotta-900 text-sm font-bold">No quizzes yet</p>
                <p className="text-terracotta-600 text-xs font-medium">Generate your first quiz above</p>
              </div>
            ) : (
              <div className="space-y-2">
                <p className="text-xs font-bold text-terracotta-700 uppercase tracking-wider">
                  {quizList.length} quiz{quizList.length !== 1 ? 'zes' : ''}
                </p>
                {quizList.map((q, i) => (
                  <motion.div key={q.id} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: i * 0.04 }}
                    onClick={() => openQuiz(q.id)}
                    className="glass glass-hover rounded-xl px-4 py-3.5 flex items-center gap-4 cursor-pointer group transition-all">
                    <div className="w-9 h-9 rounded-lg bg-terracotta-50 border border-terracotta-200 flex items-center justify-center shrink-0">
                      {q.quiz_type === 'flashcard' ? <BookOpen className="w-4 h-4 text-olive-600" /> : <Brain className="w-4 h-4 text-terracotta-600" />}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-bold text-terracotta-950">
                        {q.quiz_type === 'flashcard' ? 'Flashcard Set' : 'MCQ Quiz'} #{q.id}
                      </p>
                      <p className="text-[11px] text-terracotta-600 mt-0.5 font-semibold">
                        {q.item_count ?? '?'} items · Doc #{q.document_id}
                      </p>
                    </div>
                    {loadingQuiz
                      ? <Loader2 className="w-4 h-4 text-terracotta-400 animate-spin shrink-0" />
                      : <ChevronRight className="w-4 h-4 text-terracotta-400 group-hover:text-terracotta-800 transition-colors shrink-0" />
                    }
                  </motion.div>
                ))}
              </div>
            )}
          </motion.div>
        )}

        {view === 'play' && activeQuiz && (
          <motion.div key="play" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
            {isFlash
              ? <FlashCard item={items[cardIndex]} current={cardIndex + 1} total={items.length}
                  onNext={() => setCardIndex(p => Math.min(items.length - 1, p + 1))}
                  onPrev={() => setCardIndex(p => Math.max(0, p - 1))} />
              : <MCQQuiz items={items} quizId={activeQuiz.id} onFinish={handleFinish} />
            }
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
