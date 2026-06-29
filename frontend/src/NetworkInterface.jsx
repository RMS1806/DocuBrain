import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { UserPlus, Shield, Users, ChevronRight, CheckCircle2, AlertCircle, Loader2 } from 'lucide-react';
import { API_BASE } from './api';

const getToken = () => localStorage.getItem('token');

export default function NetworkInterface({ onSelectClient }) {
  const role                    = localStorage.getItem('role') ?? 'client';
  const [email, setEmail]       = useState('');
  const [clients, setClients]   = useState([]);
  const [status, setStatus]     = useState(null);
  const [loading, setLoading]   = useState(false);
  const [fetching, setFetching] = useState(false);

  useEffect(() => {
    if (role !== 'professional') return;
    setFetching(true);
    fetch(`${API_BASE}/professional/clients`, { headers: { Authorization: `Bearer ${getToken()}` } })
      .then(r => r.ok ? r.json() : [])
      .then(setClients)
      .catch(() => {})
      .finally(() => setFetching(false));
  }, [role]);

  const handleInvite = async (e) => {
    e.preventDefault();
    setLoading(true);
    setStatus(null);
    try {
      const res = await fetch(`${API_BASE}/link/invite`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${getToken()}` },
        body: JSON.stringify({ professional_email: email }),
      });
      const data = await res.json().catch(() => ({}));
      if (res.ok) { setStatus({ ok: true, msg: data.message ?? 'Linked successfully!' }); setEmail(''); }
      else         { setStatus({ ok: false, msg: data.detail ?? 'Error sending invitation' }); }
    } catch {
      setStatus({ ok: false, msg: 'Connection failed.' });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6 max-w-2xl">
      <div>
        <h2 className="text-xl font-black text-terracotta-950">Network</h2>
        <p className="text-terracotta-700 text-sm mt-0.5 font-medium">
          {role === 'client' ? 'Grant a professional access to your document vault' : 'Manage your connected clients'}
        </p>
      </div>

      {role === 'client' && (
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}
          className="glass rounded-2xl p-6">
          <div className="flex items-center gap-3 mb-6">
            <div className="w-10 h-10 rounded-xl bg-terracotta-50 border border-terracotta-200 flex items-center justify-center">
              <Shield className="w-5 h-5 text-terracotta-600" />
            </div>
            <div>
              <h3 className="font-bold text-terracotta-950 text-sm">Invite a Professional</h3>
              <p className="text-terracotta-700 text-xs mt-0.5 font-medium">They'll get read access to your documents</p>
            </div>
          </div>

          <form onSubmit={handleInvite} className="space-y-4">
            <div>
              <label className="block text-xs font-bold text-terracotta-800 uppercase tracking-wider mb-1.5">Professional's Email</label>
              <div className="relative">
                <UserPlus className="absolute left-3 top-2.5 w-4 h-4 text-terracotta-400" />
                <input type="email" required value={email} onChange={e => setEmail(e.target.value)}
                  placeholder="doctor@clinic.com"
                  className="w-full bg-white/90 border border-terracotta-200 rounded-xl py-2.5 pl-10 pr-4 text-sm text-terracotta-950 placeholder:text-terracotta-300 font-medium
                    focus:outline-none focus:border-terracotta-500 focus:ring-2 focus:ring-terracotta-100 transition-all" />
              </div>
            </div>

            {status && (
              <motion.div initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }}
                className={`flex items-center gap-2 p-3 rounded-xl text-xs font-bold ${
                  status.ok
                    ? 'bg-olive-50 border border-olive-300 text-olive-800'
                    : 'bg-red-50 border border-red-300 text-red-700'
                }`}>
                {status.ok ? <CheckCircle2 className="w-4 h-4 shrink-0" /> : <AlertCircle className="w-4 h-4 shrink-0" />}
                {status.msg}
              </motion.div>
            )}

            <button type="submit" disabled={loading}
              className="w-full py-2.5 rounded-xl font-bold text-sm bg-terracotta-600 hover:bg-terracotta-700 disabled:bg-terracotta-300 text-white flex items-center justify-center gap-2 transition-all shadow-md shadow-terracotta-200">
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <UserPlus className="w-4 h-4" />}
              {loading ? 'Sending…' : 'Send Invitation'}
            </button>
          </form>
        </motion.div>
      )}

      {role === 'professional' && (
        <div>
          {fetching ? (
            <div className="flex items-center justify-center h-32 gap-2">
              <Loader2 className="w-5 h-5 text-terracotta-500 animate-spin" />
              <span className="text-terracotta-700 text-sm font-semibold">Loading clients…</span>
            </div>
          ) : clients.length === 0 ? (
            <div className="glass rounded-2xl p-12 flex flex-col items-center gap-3 text-center border-2 border-dashed border-terracotta-200/60">
              <div className="w-12 h-12 rounded-xl bg-white/70 flex items-center justify-center">
                <Users className="w-6 h-6 text-terracotta-400" />
              </div>
              <div>
                <p className="text-terracotta-900 text-sm font-bold">No clients yet</p>
                <p className="text-terracotta-600 text-xs mt-1 font-medium">When a client links you, they'll appear here.</p>
              </div>
            </div>
          ) : (
            <div className="space-y-2">
              <p className="text-xs font-bold text-terracotta-700 uppercase tracking-wider mb-3">
                {clients.length} connected client{clients.length !== 1 ? 's' : ''}
              </p>
              {clients.map((client, i) => (
                <motion.div key={client.id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.05 }}
                  onClick={() => onSelectClient?.(client.id)}
                  className="glass glass-hover rounded-xl px-4 py-3.5 flex items-center gap-4 cursor-pointer transition-all group">
                  <div className="w-9 h-9 rounded-full bg-terracotta-50 border border-terracotta-200 flex items-center justify-center shrink-0">
                    <Users className="w-4 h-4 text-terracotta-600" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-bold text-terracotta-950 truncate">{client.email}</p>
                    <p className="text-[11px] text-terracotta-600 font-medium mt-0.5">
                      ID #{client.id} · Linked {client.joined_at ? new Date(client.joined_at).toLocaleDateString() : '—'}
                    </p>
                  </div>
                  <span className="text-xs text-terracotta-500 group-hover:text-terracotta-800 transition-colors flex items-center gap-1 shrink-0 font-semibold">
                    View vault <ChevronRight className="w-3.5 h-3.5" />
                  </span>
                </motion.div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
