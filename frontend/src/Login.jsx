import { useState } from 'react';
import { motion } from 'framer-motion';
import { Mail, Lock, Loader2, Layers, ChevronRight } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { API_BASE } from './api';

export default function Login() {
  const [mode, setMode]         = useState('login');
  const [email, setEmail]       = useState('');
  const [password, setPassword] = useState('');
  const [error, setError]       = useState('');
  const [loading, setLoading]   = useState(false);
  const navigate = useNavigate();

  const extractError = (detail, fallback) => {
    if (!detail) return fallback;
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail)) return detail.map(e => e.msg ?? String(e)).join(' · ');
    return fallback;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      if (mode === 'register') {
        const res = await fetch(`${API_BASE}/auth/register`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email, password }),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) { setError(extractError(data.detail, 'Registration failed')); return; }
        localStorage.setItem('token', data.access_token);
        navigate('/dashboard');
      } else {
        const form = new FormData();
        form.append('username', email);
        form.append('password', password);
        const res = await fetch(`${API_BASE}/auth/login`, { method: 'POST', body: form });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) { setError(extractError(data.detail, 'Invalid credentials')); return; }
        localStorage.setItem('token', data.access_token);
        navigate('/dashboard');
      }
    } catch {
      setError('Connection failed. Is the server running?');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center px-4 relative overflow-hidden">
      {/* Background orbs */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden">
        <div className="absolute w-[600px] h-[600px] rounded-full bg-terracotta-200 blur-[130px] opacity-50 -top-48 -left-32" />
        <div className="absolute w-[500px] h-[500px] rounded-full bg-mustard-100   blur-[120px] opacity-55 -bottom-32 right-0" />
        <div className="absolute w-[300px] h-[300px] rounded-full bg-olive-200    blur-[100px] opacity-35 top-1/2 left-1/2 -translate-x-1/2" />
      </div>

      <motion.div initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }}
        className="relative w-full max-w-sm z-10">

        {/* Logo */}
        <div className="flex flex-col items-center mb-8">
          <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-terracotta-600 to-olive-600 flex items-center justify-center shadow-xl shadow-terracotta-200 mb-4">
            <Layers className="w-7 h-7 text-white" />
          </div>
          <h1 className="text-2xl font-black text-terracotta-950">Docu<span className="grad-text">Brain</span></h1>
          <p className="text-terracotta-700 text-sm mt-1 font-medium">AI Study Workspace</p>
        </div>

        {/* Glass card */}
        <div className="glass rounded-2xl p-8">
          {/* Mode toggle */}
          <div className="flex bg-terracotta-50 rounded-xl p-1 mb-6 gap-1">
            {[['login','Sign In'], ['register','Register']].map(([m, label]) => (
              <button key={m} onClick={() => { setMode(m); setError(''); }}
                className={`flex-1 py-2 rounded-lg text-sm font-bold transition-all ${
                  mode === m
                    ? 'bg-white text-terracotta-800 shadow-sm'
                    : 'text-terracotta-600 hover:text-terracotta-900'
                }`}>
                {label}
              </button>
            ))}
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-bold text-terracotta-800 uppercase tracking-wider mb-1.5">Email</label>
              <div className="relative">
                <Mail className="absolute left-3 top-2.5 w-4 h-4 text-terracotta-400" />
                <input type="email" required value={email} onChange={e => setEmail(e.target.value)}
                  placeholder="you@example.com" autoComplete="email"
                  className="w-full bg-white/90 border border-terracotta-200 rounded-xl py-2.5 pl-10 pr-4 text-sm text-terracotta-950 placeholder:text-terracotta-300 font-medium
                    focus:outline-none focus:border-terracotta-500 focus:ring-2 focus:ring-terracotta-100 transition-all" />
              </div>
            </div>

            <div>
              <label className="block text-xs font-bold text-terracotta-800 uppercase tracking-wider mb-1.5">Password</label>
              <div className="relative">
                <Lock className="absolute left-3 top-2.5 w-4 h-4 text-terracotta-400" />
                <input type="password" required value={password} onChange={e => setPassword(e.target.value)}
                  placeholder="••••••••" autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                  className="w-full bg-white/90 border border-terracotta-200 rounded-xl py-2.5 pl-10 pr-4 text-sm text-terracotta-950 placeholder:text-terracotta-300 font-medium
                    focus:outline-none focus:border-terracotta-500 focus:ring-2 focus:ring-terracotta-100 transition-all" />
              </div>
            </div>

            {error && (
              <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }}
                className="text-red-700 text-xs bg-red-50 border border-red-200 rounded-xl px-3 py-2.5 font-semibold">
                {error}
              </motion.p>
            )}

            <button type="submit" disabled={loading}
              className="w-full mt-1 bg-terracotta-600 hover:bg-terracotta-700 disabled:bg-terracotta-300 text-white font-bold text-sm py-2.5 rounded-xl
                flex items-center justify-center gap-2 transition-all shadow-md shadow-terracotta-200">
              {loading
                ? <Loader2 className="w-4 h-4 animate-spin" />
                : <>{mode === 'login' ? 'Sign In' : 'Create Account'}<ChevronRight className="w-4 h-4" /></>
              }
            </button>
          </form>
        </div>

        <p className="text-center text-xs text-terracotta-700 font-semibold mt-5">Secure · Encrypted · AI-powered</p>
      </motion.div>
    </div>
  );
}
