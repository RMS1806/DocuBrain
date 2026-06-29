import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { BarChart2, FileText, Brain, MessageSquare, TrendingUp, BookOpen, Loader2, RefreshCw } from 'lucide-react';
import { API_BASE } from './api';

const getToken = () => localStorage.getItem('token');

const STAT_CARDS = [
  { key: 'documents_uploaded', label: 'Documents',     icon: FileText,      bg: 'bg-terracotta-50', ic: 'text-terracotta-600', border: 'border-terracotta-200' },
  { key: 'quizzes_generated',  label: 'Quizzes',       icon: Brain,         bg: 'bg-olive-50',      ic: 'text-olive-700',      border: 'border-olive-200'      },
  { key: 'chat_messages_sent', label: 'Chat Messages', icon: MessageSquare, bg: 'bg-mustard-50',    ic: 'text-mustard-700',    border: 'border-mustard-200'    },
];

const StatCard = ({ label, value, icon: Icon, bg, ic, border, i }) => (
  <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.07 }}
    className="glass glass-hover rounded-2xl p-5">
    <div className="flex items-start justify-between">
      <div>
        <p className="text-xs font-bold text-terracotta-700 uppercase tracking-wider">{label}</p>
        <p className="text-3xl font-black text-terracotta-950 mt-1.5">{value ?? 0}</p>
      </div>
      <div className={`w-10 h-10 rounded-xl ${bg} border ${border} flex items-center justify-center`}>
        <Icon className={`w-5 h-5 ${ic}`} />
      </div>
    </div>
  </motion.div>
);

const WeeklyBarChart = ({ data }) => {
  if (!data?.length) return <p className="text-terracotta-600 text-sm text-center py-8 font-semibold">No data yet</p>;
  const max = Math.max(...data.map(w => w.avg_score_pct ?? 0), 1);

  const fmtWeek = (isoStr) => {
    const d = new Date(isoStr);
    return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
  };

  return (
    <div className="flex items-end gap-2 h-36 pt-4">
      {data.map((w, i) => {
        const pct = ((w.avg_score_pct ?? 0) / max) * 100;
        return (
          <div key={i} className="flex-1 flex flex-col items-center gap-1.5 group">
            <span className="text-[10px] text-terracotta-700 opacity-0 group-hover:opacity-100 transition-opacity font-bold">
              {(w.avg_score_pct ?? 0).toFixed(0)}%
            </span>
            <div className="w-full relative rounded-t-md overflow-hidden bg-white/50" style={{ height: '80px' }}>
              <motion.div
                initial={{ height: 0 }}
                animate={{ height: `${pct}%` }}
                transition={{ delay: i * 0.05, duration: 0.5, ease: 'easeOut' }}
                className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-terracotta-600 to-terracotta-400 rounded-t-md"
              />
            </div>
            <span className="text-[9px] text-terracotta-600 font-semibold">{fmtWeek(w.week_start)}</span>
            {w.attempts > 0 && <span className="text-[9px] text-terracotta-500 font-medium">{w.attempts}×</span>}
          </div>
        );
      })}
    </div>
  );
};

export default function Analytics() {
  const [data, setData]       = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState('');

  const load = async () => {
    setLoading(true);
    setError('');
    try {
      const res = await fetch(`${API_BASE}/analytics/dashboard`, { headers: { Authorization: `Bearer ${getToken()}` } });
      if (!res.ok) throw new Error('Failed to load analytics');
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
      <span className="text-terracotta-700 text-sm font-semibold">Loading analytics…</span>
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
          <h2 className="text-xl font-black text-terracotta-950">Analytics</h2>
          <p className="text-terracotta-700 text-sm mt-0.5 font-medium">Your study performance at a glance</p>
        </div>
        <button onClick={load} className="p-2 rounded-xl glass glass-hover text-terracotta-600 hover:text-terracotta-900 transition-all">
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>

      <div className="grid grid-cols-3 gap-4">
        {STAT_CARDS.map((cfg, i) => (
          <StatCard key={cfg.key} i={i} label={cfg.label} value={data?.[cfg.key]}
            icon={cfg.icon} bg={cfg.bg} ic={cfg.ic} border={cfg.border} />
        ))}
      </div>

      <div className="glass rounded-2xl p-6">
        <div className="flex items-center gap-2 mb-4">
          <TrendingUp className="w-4 h-4 text-terracotta-500" />
          <h3 className="text-sm font-bold text-terracotta-900">Weekly Score Trend</h3>
          <span className="text-xs text-terracotta-600 ml-auto font-semibold">avg % correct</span>
        </div>
        <WeeklyBarChart data={data?.weekly_score_trend} />
      </div>

      {data?.most_studied_documents?.length > 0 && (
        <div className="glass rounded-2xl p-6">
          <div className="flex items-center gap-2 mb-4">
            <BookOpen className="w-4 h-4 text-olive-600" />
            <h3 className="text-sm font-bold text-terracotta-900">Most Studied</h3>
          </div>
          <div className="space-y-3">
            {data.most_studied_documents.map((doc, i) => {
              const maxCount = data.most_studied_documents[0]?.quiz_count ?? 1;
              const pct = (doc.quiz_count / maxCount) * 100;
              return (
                <div key={doc.document_id} className="space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-terracotta-900 font-semibold truncate flex-1 mr-3">{doc.filename}</span>
                    <span className="text-xs font-bold text-terracotta-600 shrink-0">{doc.quiz_count} quiz{doc.quiz_count !== 1 ? 'zes' : ''}</span>
                  </div>
                  <div className="h-1.5 bg-white/60 rounded-full overflow-hidden">
                    <motion.div
                      initial={{ width: 0 }}
                      animate={{ width: `${pct}%` }}
                      transition={{ delay: i * 0.1, duration: 0.5 }}
                      className="h-full bg-gradient-to-r from-terracotta-500 to-olive-500 rounded-full"
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
