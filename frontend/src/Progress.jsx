import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { TrendingUp, Target, Award, BookOpen, Clock, CheckCircle2, XCircle, Loader2, RefreshCw } from 'lucide-react';
import { API_BASE } from './api';

const getToken = () => localStorage.getItem('token');

const ScoreRing = ({ pct, size = 80 }) => {
  const r = 30;
  const circ = 2 * Math.PI * r;
  const dash = ((pct ?? 0) / 100) * circ;
  const color = (pct ?? 0) >= 70 ? '#5f6728' : (pct ?? 0) >= 50 ? '#a6750c' : '#963a2c';
  return (
    <svg width={size} height={size} viewBox="0 0 80 80">
      <circle cx="40" cy="40" r={r} fill="none" stroke="rgba(255,248,240,0.7)" strokeWidth="7" />
      <motion.circle cx="40" cy="40" r={r} fill="none" stroke={color} strokeWidth="7"
        strokeLinecap="round" strokeDasharray={circ} strokeDashoffset={circ - dash}
        transform="rotate(-90 40 40)"
        initial={{ strokeDashoffset: circ }}
        animate={{ strokeDashoffset: circ - dash }}
        transition={{ duration: 1, ease: 'easeOut' }}
      />
      <text x="40" y="44" textAnchor="middle" fontSize="14" fontWeight="800" fill={color}>
        {pct != null ? `${Math.round(pct)}%` : '—'}
      </text>
    </svg>
  );
};

const STAT_CARDS = [
  { key: 'total_quizzes_attempted', label: 'Quizzes Taken', icon: TrendingUp, bg: 'bg-terracotta-50', ic: 'text-terracotta-600', border: 'border-terracotta-200', fmt: v => v ?? 0 },
  { key: 'documents_studied',       label: 'Docs Studied',  icon: BookOpen,   bg: 'bg-olive-50',      ic: 'text-olive-700',      border: 'border-olive-200',      fmt: v => v ?? 0 },
  { key: 'average_score_pct',       label: 'Avg Score',     icon: Target,     bg: 'bg-mustard-50',    ic: 'text-mustard-700',    border: 'border-mustard-200',    fmt: v => v != null ? `${Math.round(v)}%` : '—' },
  { key: 'best_score_pct',          label: 'Best Score',    icon: Award,      bg: 'bg-terracotta-50', ic: 'text-terracotta-700', border: 'border-terracotta-200', fmt: v => v != null ? `${Math.round(v)}%` : '—' },
];

export default function Progress() {
  const [data, setData]       = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState('');

  const load = async () => {
    setLoading(true);
    setError('');
    try {
      const res = await fetch(`${API_BASE}/progress/stats`, { headers: { Authorization: `Bearer ${getToken()}` } });
      if (!res.ok) throw new Error('Failed to load progress');
      setData(await res.json());
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  if (loading) return (
    <div className="flex items-center justify-center h-64 gap-2">
      <Loader2 className="w-5 h-5 text-terracotta-500 animate-spin" />
      <span className="text-terracotta-700 text-sm font-semibold">Loading progress…</span>
    </div>
  );

  if (error) return (
    <div className="glass rounded-2xl p-6 text-center border border-red-200">
      <p className="text-red-700 text-sm font-bold">{error}</p>
      <button onClick={load} className="mt-3 text-xs text-terracotta-700 hover:text-terracotta-950 flex items-center gap-1 mx-auto font-semibold">
        <RefreshCw className="w-3.5 h-3.5" /> Retry
      </button>
    </div>
  );

  return (
    <div className="space-y-6 max-w-4xl">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-black text-terracotta-950">Progress</h2>
          <p className="text-terracotta-700 text-sm mt-0.5 font-medium">Track your study performance over time</p>
        </div>
        <button onClick={load} className="p-2 rounded-xl glass glass-hover text-terracotta-600 hover:text-terracotta-900 transition-all">
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>

      {/* Score summary */}
      <div className="glass rounded-2xl p-6 flex items-center gap-8">
        <div className="flex flex-col items-center gap-1">
          <ScoreRing pct={data?.average_score_pct} />
          <span className="text-xs text-terracotta-700 font-bold">Average</span>
        </div>
        <div className="flex flex-col items-center gap-1">
          <ScoreRing pct={data?.best_score_pct} />
          <span className="text-xs text-terracotta-700 font-bold">Best</span>
        </div>
        <div className="flex-1 grid grid-cols-2 gap-3">
          {[
            { label: 'Quizzes Taken',     value: data?.total_quizzes_attempted ?? 0 },
            { label: 'Docs Studied',       value: data?.documents_studied ?? 0 },
            { label: 'Qs Answered',        value: data?.total_questions_answered ?? 0 },
            { label: 'Recent Attempts',    value: data?.recent_attempts?.length ?? 0 },
          ].map(s => (
            <div key={s.label} className="bg-white/60 rounded-xl px-3 py-2.5 border border-terracotta-100">
              <p className="text-xl font-black text-terracotta-950">{s.value}</p>
              <p className="text-[11px] text-terracotta-700 mt-0.5 font-semibold">{s.label}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-4 gap-3">
        {STAT_CARDS.map(({ key, label, icon: Icon, bg, ic, border, fmt }, i) => (
          <motion.div key={key} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.07 }}
            className="glass glass-hover rounded-xl p-4">
            <div className={`w-8 h-8 rounded-lg ${bg} border ${border} flex items-center justify-center mb-2`}>
              <Icon className={`w-4 h-4 ${ic}`} />
            </div>
            <p className="text-xl font-black text-terracotta-950">{fmt(data?.[key])}</p>
            <p className="text-[11px] text-terracotta-700 mt-0.5 font-bold">{label}</p>
          </motion.div>
        ))}
      </div>

      {/* Recent attempts */}
      {data?.recent_attempts?.length > 0 && (
        <div className="glass rounded-2xl p-6">
          <h3 className="text-sm font-bold text-terracotta-900 mb-4 flex items-center gap-2">
            <Clock className="w-4 h-4 text-terracotta-500" /> Recent Attempts
          </h3>
          <div className="space-y-2">
            {data.recent_attempts.map((a, i) => {
              const passed = (a.score_pct ?? 0) >= 60;
              return (
                <motion.div key={a.attempt_id} initial={{ opacity: 0 }} animate={{ opacity: 1 }}
                  transition={{ delay: i * 0.05 }}
                  className="flex items-center gap-4 px-4 py-3 bg-white/50 rounded-xl border border-terracotta-100">
                  {a.quiz_type === 'flashcard'
                    ? <BookOpen className="w-4 h-4 text-olive-600 shrink-0" />
                    : passed
                      ? <CheckCircle2 className="w-4 h-4 text-olive-600 shrink-0" />
                      : <XCircle className="w-4 h-4 text-red-500 shrink-0" />
                  }
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-bold text-terracotta-900">
                      {a.quiz_type === 'flashcard' ? 'Flashcard Review' : `Quiz #${a.quiz_id}`}
                    </p>
                    <p className="text-[11px] text-terracotta-600 mt-0.5 font-medium">
                      Doc #{a.document_id} · {a.completed_at ? new Date(a.completed_at).toLocaleDateString() : ''}
                    </p>
                  </div>
                  {a.quiz_type !== 'flashcard' && a.score != null && (
                    <div className="text-right shrink-0">
                      <p className={`text-sm font-black ${passed ? 'text-olive-700' : 'text-red-600'}`}>
                        {a.score}/{a.total}
                      </p>
                      <p className="text-[10px] text-terracotta-600 font-semibold">{(a.score_pct ?? 0).toFixed(0)}%</p>
                    </div>
                  )}
                  {a.quiz_type === 'flashcard' && (
                    <span className="text-xs text-olive-800 bg-olive-50 border border-olive-200 px-2 py-0.5 rounded-full font-bold">
                      Review
                    </span>
                  )}
                </motion.div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
