import React, { useState, useEffect } from 'react';
import { motion, useMotionValue } from 'framer-motion'; // Added useMotionValue
import { Brain, Lock, User, AlertCircle, ChevronRight, Briefcase } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

// --- ADDED CURSOR COMPONENT ---
const CustomCursor = () => {
  const cursorX = useMotionValue(-100);
  const cursorY = useMotionValue(-100);
  const [isHovering, setIsHovering] = useState(false);

  useEffect(() => {
    const moveCursor = (e) => { 
      cursorX.set(e.clientX - 16); 
      cursorY.set(e.clientY - 16); 
    };
    const handleMouseOver = (e) => {
      if (e.target.tagName === 'BUTTON' || e.target.tagName === 'A' || e.target.tagName === 'INPUT' || e.target.closest('button')) {
        setIsHovering(true);
      } else {
        setIsHovering(false);
      }
    };
    window.addEventListener('mousemove', moveCursor);
    window.addEventListener('mouseover', handleMouseOver);
    return () => {
      window.removeEventListener('mousemove', moveCursor);
      window.removeEventListener('mouseover', handleMouseOver);
    };
  }, []);

  return (
    <motion.div
      className="fixed top-0 left-0 pointer-events-none z-[9999] mix-blend-difference"
      style={{ translateX: cursorX, translateY: cursorY }}
    >
      <motion.div 
        animate={{ scale: isHovering ? 1.5 : 1, opacity: isHovering ? 1 : 0.5 }}
        className="w-8 h-8 rounded-full border-2 border-neon-blue transition-colors duration-200"
      />
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-1 h-1 bg-white rounded-full" />
    </motion.div>
  );
};

const Login = () => {
  // ... (Keep all your existing state and logic exactly as is) ...
  const [isLogin, setIsLogin] = useState(true);
  const [role, setRole] = useState('client');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const endpoint = isLogin ? "/auth/login" : "/auth/register";
      const url = `http://localhost:8000${endpoint}`;

      let options = {};
      
      if (isLogin) {
        // Login uses FormData (OAuth2 Standard)
        const formData = new FormData();
        formData.append('username', email); // Note: Backend expects 'username', we send email
        formData.append('password', password);
        options = { method: "POST", body: formData };
      } else {
        // Register uses JSON
        options = {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ 
            email: email, 
            password: password, 
            role: role 
          }),
        };
      }

      const response = await fetch(url, options);
      const data = await response.json();

      if (!response.ok) {
        // --- 🔴 FIX: Handle Object Errors (422 Validation) ---
        let errorMessage = "Authentication Failed";
        
        if (data.detail) {
            if (typeof data.detail === 'string') {
                // Simple error string
                errorMessage = data.detail;
            } else if (Array.isArray(data.detail)) {
                // FastAPI Validation array (e.g. invalid email format)
                // We grab the first error message from the list
                errorMessage = `${data.detail[0].loc[1]}: ${data.detail[0].msg}`;
            } else {
                errorMessage = JSON.stringify(data.detail);
            }
        }
        throw new Error(errorMessage);
        // -----------------------------------------------------
      }

      // Success!
      localStorage.setItem('token', data.access_token);
      localStorage.setItem('role', data.role);
      navigate('/dashboard');

    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-black flex items-center justify-center p-4 font-sans relative overflow-hidden">
      
      {/* 🔴 INSERT CURSOR HERE */}
      <CustomCursor />

      {/* Background Ambience */}
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_50%,rgba(0,243,255,0.1),transparent_70%)]" />
      <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-transparent via-neon-blue to-transparent opacity-30" />

      {/* Login Card */}
      <motion.div 
        initial={{ opacity: 0, scale: 0.9 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.5 }}
        className="w-full max-w-md bg-zinc-900/80 border border-white/10 backdrop-blur-xl rounded-2xl p-8 shadow-2xl relative z-10"
      >
        {/* ... (Rest of your existing Login JSX) ... */}
         <div className="flex flex-col items-center mb-8">
          <div className="p-4 bg-zinc-800/50 rounded-full mb-4 border border-neon-blue/20 shadow-[0_0_15px_rgba(0,243,255,0.2)]">
            <Brain className="w-8 h-8 text-neon-blue" />
          </div>
          <h1 className="text-3xl font-bold tracking-tighter text-white mb-1">DOCU<span className="text-neon-blue">BRAIN</span></h1>
          <p className="text-zinc-500 text-xs font-mono tracking-widest">SECURE NEURAL ACCESS</p>
        </div>

        {!isLogin && (
          <div className="flex bg-zinc-950 p-1 rounded-lg mb-6 border border-white/5">
            <button type="button" onClick={() => setRole('client')} className={`flex-1 flex items-center justify-center gap-2 py-2 rounded-md text-xs font-bold transition-all ${role === 'client' ? 'bg-zinc-800 text-white shadow-md' : 'text-zinc-500 hover:text-zinc-300'}`}>
              <User className="w-3 h-3" /> Client
            </button>
            <button type="button" onClick={() => setRole('professional')} className={`flex-1 flex items-center justify-center gap-2 py-2 rounded-md text-xs font-bold transition-all ${role === 'professional' ? 'bg-zinc-800 text-white shadow-md' : 'text-zinc-500 hover:text-zinc-300'}`}>
              <Briefcase className="w-3 h-3" /> Professional
            </button>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1">
            <label className="text-xs font-mono text-zinc-500 ml-1">IDENTITY_STRING (EMAIL)</label>
            <div className="relative">
              <User className="absolute left-3 top-3.5 w-4 h-4 text-zinc-600" />
              <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} className="w-full bg-black/50 border border-zinc-800 rounded-xl py-3 pl-10 pr-4 text-white focus:outline-none focus:border-neon-blue transition-colors text-sm" placeholder="user@neural.net" />
            </div>
          </div>

          <div className="space-y-1">
            <label className="text-xs font-mono text-zinc-500 ml-1">SECURITY_KEY (PASSWORD)</label>
            <div className="relative">
              <Lock className="absolute left-3 top-3.5 w-4 h-4 text-zinc-600" />
              <input type="password" required value={password} onChange={(e) => setPassword(e.target.value)} className="w-full bg-black/50 border border-zinc-800 rounded-xl py-3 pl-10 pr-4 text-white focus:outline-none focus:border-neon-blue transition-colors text-sm" placeholder="••••••••" />
            </div>
          </div>

          {error && (
            <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} className="p-3 bg-red-500/10 border border-red-500/20 rounded-lg flex items-center gap-2 text-red-400 text-xs font-mono">
              <AlertCircle className="w-4 h-4 shrink-0" /> <span className="truncate">{error}</span>
            </motion.div>
          )}

          <button 
            type="submit" 
            disabled={loading}
            className="w-full bg-neon-blue hover:bg-cyan-300 text-black font-bold py-3 rounded-xl transition-all duration-300 shadow-[0_0_10px_rgba(0,243,255,0.2)] hover:shadow-[0_0_20px_rgba(0,243,255,0.5)] flex items-center justify-center gap-2 mt-4 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? <span className="animate-pulse">PROCESSING...</span> : <>{isLogin ? 'INITIATE LINK' : 'CREATE IDENTITY'} <ChevronRight className="w-4 h-4" /></>}
          </button>
        </form>

        <div className="mt-6 text-center">
          <p className="text-zinc-600 text-xs">
            {isLogin ? "New to the network?" : "Already linked?"}
            <button type="button" onClick={() => { setIsLogin(!isLogin); setError(''); }} className="text-neon-blue hover:underline font-bold ml-1">
              {isLogin ? "Register Access" : "Login"}
            </button>
          </p>
        </div>
      </motion.div>
    </div>
  );
};

export default Login;