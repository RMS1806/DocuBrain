import { useState, useRef, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Send, Bot, User, Sparkles, FileText, Plus, MessageSquare, Trash2, Loader2 } from 'lucide-react';
import { API_BASE } from './api';

const getToken = () => localStorage.getItem('token');

const apiFetch = async (path, options = {}) => {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${getToken()}`, ...(options.headers ?? {}) },
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.detail ?? `Request failed (${res.status})`);
  return body;
};

const StreamCursor = () => (
  <motion.span className="inline-block w-[2px] h-[1em] bg-terracotta-500 align-middle ml-0.5"
    animate={{ opacity: [1, 0, 1] }} transition={{ duration: 0.7, repeat: Infinity, ease: 'linear' }} />
);

const TypingDots = () => (
  <div className="flex items-center gap-1 px-4 py-3">
    {[0, 1, 2].map(i => (
      <motion.span key={i} className="w-2 h-2 rounded-full bg-terracotta-300"
        animate={{ opacity: [0.3, 1, 0.3], scale: [0.8, 1.1, 0.8] }}
        transition={{ duration: 1.2, repeat: Infinity, delay: i * 0.2 }} />
    ))}
  </div>
);

const MessageBubble = ({ msg, isStreaming }) => {
  const isUser = msg.role === 'user';
  return (
    <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.2 }}
      className={`flex gap-3 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}>
      <div className={`w-7 h-7 rounded-full flex items-center justify-center shrink-0 border ${
        isUser
          ? 'bg-terracotta-600 text-white border-terracotta-500'
          : 'bg-white/70 text-terracotta-600 border-terracotta-100'
      }`}>
        {isUser ? <User className="w-3.5 h-3.5" /> : <Bot className="w-3.5 h-3.5" />}
      </div>
      <div className={`flex flex-col max-w-[78%] gap-1.5 ${isUser ? 'items-end' : 'items-start'}`}>
        <div className={`px-4 py-2.5 rounded-2xl text-sm leading-relaxed whitespace-pre-wrap font-medium ${
          isUser
            ? 'bg-terracotta-600 text-white shadow-md shadow-terracotta-200'
            : 'glass text-terracotta-950'
        }`}>
          {msg.content}
          {isStreaming && !isUser && <StreamCursor />}
        </div>
        {msg.sources?.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {msg.sources.map((src, i) => (
              <span key={i} className="flex items-center gap-1 text-[10px] bg-white/70 border border-terracotta-200 text-terracotta-700 px-2 py-0.5 rounded-full font-semibold">
                <FileText className="w-2.5 h-2.5" /> {src}
              </span>
            ))}
          </div>
        )}
      </div>
    </motion.div>
  );
};

const SessionRow = ({ session, isActive, onClick, onDelete }) => (
  <motion.div layout initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -8 }}
    className={`group relative flex items-center gap-2.5 px-3 py-2.5 rounded-xl cursor-pointer transition-all border-l-2 ${
      isActive
        ? 'bg-white/70 border-terracotta-500 text-terracotta-900'
        : 'border-transparent hover:bg-white/50 text-terracotta-700 hover:text-terracotta-950'
    }`}
    onClick={onClick}>
    <MessageSquare className={`w-3.5 h-3.5 shrink-0 ${isActive ? 'text-terracotta-500' : 'text-terracotta-400'}`} />
    <span className="text-xs truncate flex-1 font-semibold">{session.title ?? `Session #${session.id}`}</span>
    {isActive && (
      <button onClick={e => { e.stopPropagation(); onDelete(); }}
        className="opacity-0 group-hover:opacity-100 p-1 hover:text-red-600 text-terracotta-400 transition-all rounded-lg hover:bg-red-50">
        <Trash2 className="w-3 h-3" />
      </button>
    )}
  </motion.div>
);

function parseSSEChunk(raw) {
  const events = [];
  for (const part of raw.split('\n\n')) {
    const trimmed = part.trim();
    if (!trimmed) continue;
    const data = trimmed.startsWith('data: ') ? trimmed.slice(6) : trimmed;
    if (data === '[DONE]')                events.push({ type: 'done' });
    else if (data.startsWith('[SOURCES]')) {
      try { events.push({ type: 'sources', value: JSON.parse(data.slice(9)) }); }
      catch { events.push({ type: 'sources', value: [] }); }
    } else if (data.startsWith('[ERROR]')) {
      events.push({ type: 'error', value: data.slice(7) });
    } else {
      events.push({ type: 'token', value: data.replace(/\\n/g, '\n') });
    }
  }
  return events;
}

export default function ChatInterface() {
  const targetUserId = null;
  const [sessions, setSessions]               = useState([]);
  const [activeSessionId, setActiveSessionId] = useState(null);
  const [messages, setMessages]               = useState([]);
  const [input, setInput]                     = useState('');
  const [isTyping, setIsTyping]               = useState(false);
  const [streamingMsgId, setStreamingMsgId]   = useState(null);
  const [loadingSession, setLoadingSession]   = useState(false);
  const messagesEndRef = useRef(null);
  const inputRef       = useRef(null);
  const abortRef       = useRef(null);

  useEffect(() => { messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages, isTyping]);
  useEffect(() => () => abortRef.current?.abort(), []);

  const fetchSessions = useCallback(async () => {
    try { setSessions(await apiFetch('/chat/sessions')); } catch { /* ignore */ }
  }, []);
  useEffect(() => { fetchSessions(); }, [fetchSessions]);

  const openSession = useCallback(async (id) => {
    abortRef.current?.abort();
    setLoadingSession(true);
    setActiveSessionId(id);
    setStreamingMsgId(null);
    try { setMessages(await apiFetch(`/chat/sessions/${id}`)); }
    catch { /* ignore */ }
    finally { setLoadingSession(false); setTimeout(() => inputRef.current?.focus(), 100); }
  }, []);

  const createSession = useCallback(async () => {
    try {
      const s = await apiFetch('/chat/sessions', { method: 'POST' });
      setSessions(p => [s, ...p]);
      setMessages([]);
      setActiveSessionId(s.id);
      setStreamingMsgId(null);
      setTimeout(() => inputRef.current?.focus(), 100);
    } catch { /* ignore */ }
  }, []);

  const deleteSession = useCallback(async (id) => {
    try {
      await apiFetch(`/chat/sessions/${id}`, { method: 'DELETE' });
      setSessions(p => p.filter(s => s.id !== id));
      if (activeSessionId === id) { setActiveSessionId(null); setMessages([]); setStreamingMsgId(null); }
    } catch { /* ignore */ }
  }, [activeSessionId]);

  const handleSend = async (e) => {
    e.preventDefault();
    if (!input.trim() || !activeSessionId || isTyping) return;
    const userContent = input.trim();
    setInput('');
    setIsTyping(true);

    const userMsgId = `user-${Date.now()}`;
    setMessages(p => [...p, { id: userMsgId, role: 'user', content: userContent, sources: [] }]);
    const asstMsgId = `asst-${Date.now()}`;
    setStreamingMsgId(asstMsgId);
    setMessages(p => [...p, { id: asstMsgId, role: 'assistant', content: '', sources: [] }]);

    const ctrl = new AbortController();
    abortRef.current = ctrl;

    try {
      const res = await fetch(`${API_BASE}/chat/sessions/${activeSessionId}/stream`, {
        method: 'POST', signal: ctrl.signal,
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${getToken()}`, Accept: 'text/event-stream' },
        body: JSON.stringify({ content: userContent, target_user_id: targetUserId ?? null }),
      });
      if (!res.ok) {
        const body = await res.text();
        try { throw new Error(JSON.parse(body).detail || `Stream failed (${res.status})`); }
        catch { throw new Error(`Stream failed (${res.status})`); }
      }

      const reader  = res.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let leftover  = '';
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const text = leftover + decoder.decode(value, { stream: true });
        const lastDelim = text.lastIndexOf('\n\n');
        if (lastDelim === -1) { leftover = text; continue; }
        const complete = text.slice(0, lastDelim + 2);
        leftover = text.slice(lastDelim + 2);
        let isDone = false;
        for (const ev of parseSSEChunk(complete)) {
          if (ev.type === 'done') { isDone = true; break; }
          if (ev.type === 'sources') {
            setMessages(p => p.map(m => m.id === asstMsgId ? { ...m, sources: ev.value } : m));
          } else if (ev.type === 'token') {
            setMessages(p => p.map(m => m.id === asstMsgId ? { ...m, content: m.content + ev.value } : m));
          } else if (ev.type === 'error') {
            setMessages(p => p.map(m => m.id === asstMsgId ? { ...m, content: `Error: ${ev.value}` } : m));
            isDone = true; break;
          }
        }
        if (isDone) { reader.cancel(); break; }
      }
      setSessions(p => p.map(s => s.id === activeSessionId ? { ...s, title: userContent.slice(0, 60) } : s));
    } catch (err) {
      if (err.name !== 'AbortError') {
        setMessages(p => p.map(m => m.id === asstMsgId ? { ...m, content: `Error: ${err.message}` } : m));
      }
    } finally {
      setStreamingMsgId(null);
      setIsTyping(false);
      requestAnimationFrame(() => inputRef.current?.focus({ preventScroll: true }));
    }
  };

  const activeSession = sessions.find(s => s.id === activeSessionId);

  return (
    <div className="space-y-4 max-w-5xl">
      <div>
        <h2 className="text-xl font-black text-terracotta-950">Neural Chat</h2>
        <p className="text-terracotta-700 text-sm mt-0.5 font-medium">AI answers with citations from your documents</p>
      </div>

      <div className="flex h-[620px] rounded-2xl overflow-hidden"
        style={{
          background: 'rgba(255,252,248,0.40)',
          backdropFilter: 'blur(24px)',
          WebkitBackdropFilter: 'blur(24px)',
          border: '1px solid rgba(255,248,240,0.88)',
          boxShadow: '0 8px 32px rgba(181,71,54,0.10), inset 0 1px 0 rgba(255,255,255,0.92)',
        }}>

        {/* Session sidebar */}
        <div className="w-56 shrink-0 flex flex-col"
          style={{ background: 'rgba(253,245,242,0.72)', borderRight: '1px solid rgba(255,248,240,0.85)' }}>
          <div className="p-3" style={{ borderBottom: '1px solid rgba(255,248,240,0.85)' }}>
            <button onClick={createSession}
              className="w-full flex items-center justify-center gap-2 py-2 px-3 rounded-xl bg-terracotta-600 hover:bg-terracotta-700 text-white text-xs font-bold transition-all shadow-sm shadow-terracotta-200">
              <Plus className="w-3.5 h-3.5" /> New Chat
            </button>
          </div>
          <div className="flex-1 overflow-y-auto p-2 space-y-0.5">
            {sessions.length === 0
              ? <p className="text-terracotta-600 text-xs text-center mt-4 px-2 font-semibold">No sessions yet</p>
              : <AnimatePresence>
                  {sessions.map(s => (
                    <SessionRow key={s.id} session={s} isActive={s.id === activeSessionId}
                      onClick={() => openSession(s.id)} onDelete={() => deleteSession(s.id)} />
                  ))}
                </AnimatePresence>
            }
          </div>
          {targetUserId && (
            <div className="p-2" style={{ borderTop: '1px solid rgba(255,248,240,0.85)' }}>
              <span className="flex items-center justify-center text-[10px] font-bold bg-terracotta-50 text-terracotta-800 border border-terracotta-200 px-2 py-1 rounded-lg">
                CLIENT #{targetUserId}
              </span>
            </div>
          )}
        </div>

        {/* Main area */}
        <div className="flex-1 flex flex-col" style={{ background: 'rgba(255,252,248,0.50)' }}>
          <div className="px-4 py-3 flex items-center gap-2.5" style={{ borderBottom: '1px solid rgba(255,248,240,0.85)' }}>
            <div className={`w-2 h-2 rounded-full transition-all ${
              streamingMsgId ? 'bg-terracotta-500 animate-pulse' : activeSessionId ? 'bg-olive-500' : 'bg-terracotta-200'
            }`} />
            <span className="text-xs font-semibold text-terracotta-700 truncate flex-1">
              {streamingMsgId ? 'Generating response…' : activeSession?.title ?? 'Select or create a session'}
            </span>
          </div>

          {!activeSessionId ? (
            <div className="flex-1 flex flex-col items-center justify-center gap-4 text-center px-8">
              <div className="w-14 h-14 rounded-2xl glass flex items-center justify-center">
                <Sparkles className="w-7 h-7 text-terracotta-500" />
              </div>
              <div>
                <h3 className="text-terracotta-900 font-bold">Start a conversation</h3>
                <p className="text-terracotta-600 text-xs mt-1 leading-relaxed font-medium">Create a session and ask anything about your uploaded documents.</p>
              </div>
              <button onClick={createSession}
                className="flex items-center gap-2 px-4 py-2 bg-terracotta-600 hover:bg-terracotta-700 text-white font-bold rounded-xl text-sm transition-all shadow-md shadow-terracotta-200">
                <Plus className="w-4 h-4" /> New Session
              </button>
            </div>
          ) : (
            <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
              {loadingSession
                ? <div className="flex items-center justify-center h-full gap-2">
                    <Loader2 className="w-5 h-5 text-terracotta-500 animate-spin" />
                  </div>
                : <>
                    {messages.length === 0 && !isTyping && (
                      <div className="flex flex-col items-center justify-center h-full gap-2 text-center">
                        <Bot className="w-8 h-8 text-terracotta-300" />
                        <p className="text-terracotta-600 text-xs font-semibold">Ask a question to begin.</p>
                      </div>
                    )}
                    <AnimatePresence initial={false}>
                      {messages.map((msg, i) => (
                        <MessageBubble key={msg.id ?? i} msg={msg} isStreaming={streamingMsgId === msg.id} />
                      ))}
                    </AnimatePresence>
                    {isTyping && streamingMsgId && messages.find(m => m.id === streamingMsgId)?.content === '' && (
                      <div className="flex gap-3 items-start">
                        <div className="w-7 h-7 rounded-full glass border border-terracotta-100 flex items-center justify-center">
                          <Bot className="w-3.5 h-3.5 text-terracotta-500" />
                        </div>
                        <div className="glass rounded-2xl"><TypingDots /></div>
                      </div>
                    )}
                    <div ref={messagesEndRef} />
                  </>
              }
            </div>
          )}

          <div className="p-3" style={{ borderTop: '1px solid rgba(255,248,240,0.85)' }}>
            <form onSubmit={handleSend}>
              <div className="flex items-center gap-2">
                <input ref={inputRef} type="text" value={input} onChange={e => setInput(e.target.value)}
                  placeholder={!activeSessionId ? 'Create a session first…' : isTyping ? 'Generating…' : 'Ask about your documents…'}
                  disabled={!activeSessionId || isTyping}
                  className="flex-1 bg-white/80 border border-terracotta-200 rounded-xl py-2.5 px-4 text-sm text-terracotta-950 placeholder:text-terracotta-400 font-medium
                    focus:outline-none focus:border-terracotta-500 focus:ring-2 focus:ring-terracotta-100
                    disabled:opacity-40 disabled:cursor-not-allowed transition-all" />
                <button type="submit" disabled={!input.trim() || !activeSessionId || isTyping}
                  className="p-2.5 bg-terracotta-600 hover:bg-terracotta-700 disabled:bg-terracotta-200 text-white rounded-xl
                    transition-all shadow-md shadow-terracotta-200 disabled:shadow-none disabled:cursor-not-allowed">
                  {isTyping ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                </button>
              </div>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}
