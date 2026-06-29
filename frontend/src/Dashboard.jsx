import { useState, useEffect, useCallback, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  FileText, MessageSquare, Brain, BarChart2, TrendingUp,
  LogOut, Bell, X, CheckCircle2, ChevronRight, User, Layers,
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { API_BASE } from './api';
import DocumentList  from './DocumentList';
import ChatInterface  from './ChatInterface';
import Analytics     from './Analytics';
import Progress      from './Progress';
import Quizzes       from './Quizzes';

const getToken = () => localStorage.getItem('token');

/* ─── Background orbs ────────────────────────────────────────────────────── */
const Orbs = () => (
  <div className="fixed inset-0 pointer-events-none overflow-hidden z-0">
    <div className="absolute w-[700px] h-[700px] rounded-full bg-terracotta-200 blur-[140px] opacity-40 -top-64 -left-48" />
    <div className="absolute w-[500px] h-[500px] rounded-full bg-mustard-100   blur-[120px] opacity-50 -bottom-40 right-0" />
    <div className="absolute w-[350px] h-[350px] rounded-full bg-olive-200     blur-[100px] opacity-30 top-1/2 right-1/3 -translate-y-1/2" />
  </div>
);

/* ─── Toast ───────────────────────────────────────────────────────────────── */
const Toast = ({ notif, onDismiss }) => (
  <motion.div initial={{ opacity: 0, x: 40, scale: 0.9 }} animate={{ opacity: 1, x: 0, scale: 1 }}
    exit={{ opacity: 0, x: 40 }}
    className="flex items-start gap-3 glass rounded-xl px-4 py-3 max-w-xs shadow-lg">
    <CheckCircle2 className="w-4 h-4 text-olive-600 mt-0.5 shrink-0" />
    <p className="text-sm text-terracotta-900 flex-1 leading-snug font-medium">{notif.message}</p>
    <button onClick={() => onDismiss(notif.id)} className="text-terracotta-400 hover:text-terracotta-700 transition-colors">
      <X className="w-3.5 h-3.5" />
    </button>
  </motion.div>
);

const NAV = [
  { id: 'documents', label: 'Documents',   icon: FileText      },
  { id: 'chat',      label: 'Neural Chat', icon: MessageSquare },
  { id: 'quizzes',   label: 'Quizzes',     icon: Brain         },
  { id: 'analytics', label: 'Analytics',   icon: BarChart2     },
  { id: 'progress',  label: 'Progress',    icon: TrendingUp    },
];

const NavItem = ({ id, label, icon: Icon, active, onClick }) => (
  <button onClick={() => onClick(id)}
    className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-semibold transition-all text-left border-l-2 ${
      active
        ? 'bg-white/75 border-terracotta-500 text-terracotta-900 shadow-sm'
        : 'border-transparent text-terracotta-700 hover:bg-white/50 hover:text-terracotta-950'
    }`}>
    <Icon className={`w-4 h-4 shrink-0 ${active ? 'text-terracotta-600' : 'text-terracotta-500'}`} />
    {label}
    {active && <ChevronRight className="w-3.5 h-3.5 ml-auto text-terracotta-400" />}
  </button>
);

export default function Dashboard() {
  const [activeTab, setActiveTab]       = useState('documents');
  const [documents, setDocuments]       = useState([]);
  const [isLoadingDocs, setLoadingDocs] = useState(true);
  const [notifications, setNotifs]      = useState([]);
  const [showNotifs, setShowNotifs]     = useState(false);
  const [unread, setUnread]             = useState(0);
  const wsRef    = useRef(null);
  const navigate = useNavigate();

  const fetchDocuments = useCallback(async () => {
    setLoadingDocs(true);
    try {
      const res = await fetch(`${API_BASE}/documents/`, { headers: { Authorization: `Bearer ${getToken()}` } });
      if (res.ok) setDocuments(await res.json());
    } catch { /* ignore */ }
    finally { setLoadingDocs(false); }
  }, []);

  useEffect(() => { fetchDocuments(); }, [fetchDocuments]);

  const addNotif = useCallback((message) => {
    const id = Date.now();
    setNotifs(p => [...p, { id, message }]);
    setUnread(u => u + 1);
    setTimeout(() => setNotifs(p => p.filter(n => n.id !== id)), 6000);
  }, []);

  useEffect(() => {
    const token = getToken();
    if (!token) return;
    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const ws = new WebSocket(`${proto}://${window.location.host}/ws/notifications?token=${token}`);
    wsRef.current = ws;
    ws.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data);
        if (data.type === 'document.ready') {
          addNotif(`Document ready: ${data.filename ?? `#${data.document_id}`}`);
          fetchDocuments();
        }
      } catch { /* ignore */ }
    };
    ws.onerror = () => {};
    return () => ws.close();
  }, [addNotif, fetchDocuments]);

  const dismissNotif = (id) => setNotifs(p => p.filter(n => n.id !== id));
  const handleLogout = () => { localStorage.clear(); navigate('/login'); };

  return (
    <div className="min-h-screen flex relative">
      <Orbs />

      {/* ── Sidebar ─────────────────────────────────────────────────────────── */}
      <aside className="fixed top-0 left-0 h-full w-56 z-20 flex flex-col"
        style={{
          background: 'rgba(253,245,242,0.78)',
          backdropFilter: 'blur(24px)',
          WebkitBackdropFilter: 'blur(24px)',
          borderRight: '1px solid rgba(255,248,240,0.90)',
          boxShadow: 'inset -1px 0 0 rgba(193,112,90,0.18)',
        }}>

        {/* Logo */}
        <div className="px-4 py-5" style={{ borderBottom: '1px solid rgba(255,248,240,0.85)' }}>
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-terracotta-600 to-olive-600 flex items-center justify-center shadow-md shadow-terracotta-200">
              <Layers className="w-4 h-4 text-white" />
            </div>
            <span className="font-black tracking-tight text-terracotta-950">Docu<span className="grad-text">Brain</span></span>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 px-3 py-3 space-y-0.5 overflow-y-auto">
          {NAV.map(item => (
            <NavItem key={item.id} {...item} active={activeTab === item.id} onClick={setActiveTab} />
          ))}
        </nav>

        {/* Footer */}
        <div className="p-3 space-y-1" style={{ borderTop: '1px solid rgba(255,248,240,0.85)' }}>
          <div className="flex items-center gap-2.5 px-2 py-1.5">
            <div className="w-7 h-7 rounded-full bg-terracotta-100 flex items-center justify-center">
              <User className="w-3.5 h-3.5 text-terracotta-700" />
            </div>
            <span className="text-xs text-terracotta-800 font-bold">User</span>
          </div>
          <button onClick={handleLogout}
            className="w-full flex items-center gap-2.5 px-3 py-2 rounded-xl text-sm text-terracotta-600 font-semibold hover:text-red-700 hover:bg-red-50/60 transition-all">
            <LogOut className="w-4 h-4" /> Sign out
          </button>
        </div>
      </aside>

      {/* ── Main ────────────────────────────────────────────────────────────── */}
      <div className="flex-1 ml-56 flex flex-col min-h-screen relative z-10">

        {/* Top bar */}
        <header className="sticky top-0 z-10 h-14 flex items-center justify-between px-6"
          style={{
            background: 'rgba(253,245,242,0.72)',
            backdropFilter: 'blur(20px)',
            WebkitBackdropFilter: 'blur(20px)',
            borderBottom: '1px solid rgba(255,248,240,0.88)',
          }}>
          <h1 className="text-sm font-bold text-terracotta-900 capitalize">
            {NAV.find(n => n.id === activeTab)?.label ?? 'Dashboard'}
          </h1>

          <div className="relative">
            <button onClick={() => { setShowNotifs(v => !v); setUnread(0); }}
              className="relative p-2 rounded-xl bg-white/60 hover:bg-white/80 border border-terracotta-100 transition-all text-terracotta-600 hover:text-terracotta-900">
              <Bell className="w-4 h-4" />
              {unread > 0 && (
                <span className="absolute -top-0.5 -right-0.5 w-4 h-4 rounded-full bg-terracotta-500 text-white text-[9px] font-bold flex items-center justify-center">
                  {unread > 9 ? '9+' : unread}
                </span>
              )}
            </button>

            <AnimatePresence>
              {showNotifs && (
                <motion.div initial={{ opacity: 0, y: -8, scale: 0.95 }} animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0, y: -8, scale: 0.95 }}
                  className="absolute right-0 top-11 w-72 glass rounded-xl overflow-hidden z-50 shadow-xl">
                  <div className="px-4 py-3 flex items-center justify-between" style={{ borderBottom: '1px solid rgba(255,248,240,0.80)' }}>
                    <span className="text-xs font-bold text-terracotta-800">Notifications</span>
                    <button onClick={() => setShowNotifs(false)} className="text-terracotta-400 hover:text-terracotta-700 transition-colors">
                      <X className="w-3.5 h-3.5" />
                    </button>
                  </div>
                  {notifications.length === 0
                    ? <p className="text-terracotta-500 text-xs text-center py-6 font-medium">No notifications yet</p>
                    : <div className="divide-y divide-terracotta-50 max-h-64 overflow-y-auto">
                        {notifications.map(n => (
                          <div key={n.id} className="flex items-start gap-2.5 px-4 py-3">
                            <CheckCircle2 className="w-3.5 h-3.5 text-olive-600 mt-0.5 shrink-0" />
                            <p className="text-xs text-terracotta-900 flex-1 font-medium">{n.message}</p>
                            <button onClick={() => dismissNotif(n.id)} className="text-terracotta-300 hover:text-terracotta-600 transition-colors">
                              <X className="w-3 h-3" />
                            </button>
                          </div>
                        ))}
                      </div>
                  }
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 p-6 overflow-y-auto">
          <AnimatePresence mode="wait">
            <motion.div key={activeTab} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }} transition={{ duration: 0.18 }}>
              {activeTab === 'documents' && <DocumentList documents={documents} isLoading={isLoadingDocs} onDelete={fetchDocuments} onUpload={fetchDocuments} />}
              {activeTab === 'chat'      && <ChatInterface />}
              {activeTab === 'quizzes'   && <Quizzes documents={documents} />}
              {activeTab === 'analytics' && <Analytics />}
              {activeTab === 'progress'  && <Progress />}
            </motion.div>
          </AnimatePresence>
        </main>
      </div>

      {/* Floating toasts */}
      <div className="fixed bottom-6 right-6 z-50 flex flex-col gap-2 items-end">
        <AnimatePresence>
          {notifications.slice(-3).map(n => <Toast key={n.id} notif={n} onDismiss={dismissNotif} />)}
        </AnimatePresence>
      </div>
    </div>
  );
}
