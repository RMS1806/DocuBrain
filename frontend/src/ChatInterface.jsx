import { useState, useRef, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Send, Bot, User, Sparkles, FileText,
  Plus, MessageSquare, Trash2, ChevronRight, Loader2
} from 'lucide-react';
import { API_BASE } from './api';

const API = API_BASE;

const getToken = () => localStorage.getItem('token');

const apiFetch = async (path, options = {}) => {
  const res = await fetch(`${API}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${getToken()}`,
      ...(options.headers || {}),
    },
  });
  if (!res.ok) {
    const textBody = await res.text();
    try {
      const err = JSON.parse(textBody);
      throw new Error(err.detail || `Request failed (${res.status})`);
    } catch {
      throw new Error(`Request failed (${res.status}): ${textBody.substring(0, 80)}`);
    }
  }
  return res.status === 204 ? null : res.json();
};

// ── Streaming cursor blink ──────────────────────────────────────────────────────
const StreamCursor = () => (
  <motion.span
    className="inline-block w-[2px] h-[1em] bg-cyan-400 align-middle ml-0.5"
    animate={{ opacity: [1, 0, 1] }}
    transition={{ duration: 0.7, repeat: Infinity, ease: 'linear' }}
  />
);

// ── Typing indicator dots ──────────────────────────────────────────────────────
const TypingDots = () => (
  <div className="flex items-center gap-1 px-4 py-3">
    {[0, 1, 2].map((i) => (
      <motion.span
        key={i}
        className="w-2 h-2 rounded-full bg-cyan-400"
        animate={{ opacity: [0.3, 1, 0.3], scale: [0.8, 1.1, 0.8] }}
        transition={{ duration: 1.2, repeat: Infinity, delay: i * 0.2 }}
      />
    ))}
  </div>
);

// ── Single message bubble ──────────────────────────────────────────────────────
const MessageBubble = ({ msg, isStreaming }) => {
  const isUser = msg.role === 'user';
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: 'easeOut' }}
      className={`flex gap-3 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}
    >
      {/* Avatar */}
      <div
        className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 ring-1 ${isUser
          ? 'bg-cyan-500/20 ring-cyan-500/40 text-cyan-400'
          : 'bg-zinc-800 ring-white/10 text-zinc-400'
          }`}
      >
        {isUser ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
      </div>

      {/* Bubble */}
      <div className={`flex flex-col max-w-[78%] gap-2 ${isUser ? 'items-end' : 'items-start'}`}>
        <div
          className={`px-4 py-3 rounded-2xl text-sm leading-relaxed whitespace-pre-wrap ${isUser
            ? 'bg-gradient-to-br from-cyan-500 to-blue-600 text-white font-medium shadow-lg shadow-cyan-500/20'
            : 'bg-white/5 border border-white/10 text-zinc-200 backdrop-blur-sm'
            }`}
        >
          {msg.content}
          {/* Blinking cursor only shown while the message is actively streaming */}
          {isStreaming && !isUser && <StreamCursor />}
        </div>

        {/* Source citation pills */}
        {msg.sources && msg.sources.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {msg.sources.map((src, i) => (
              <span
                key={i}
                className="flex items-center gap-1 text-[10px] bg-zinc-900 px-2 py-1 rounded-full text-zinc-500 border border-zinc-800"
              >
                <FileText className="w-2.5 h-2.5" />
                {src}
              </span>
            ))}
          </div>
        )}
      </div>
    </motion.div>
  );
};

// ── Sidebar session row ────────────────────────────────────────────────────────
const SessionRow = ({ session, isActive, onClick, onDelete }) => (
  <motion.div
    layout
    initial={{ opacity: 0, x: -16 }}
    animate={{ opacity: 1, x: 0 }}
    exit={{ opacity: 0, x: -16 }}
    whileHover={{ scale: 1.02 }}
    className={`group relative flex items-center gap-3 px-3 py-2.5 rounded-xl cursor-pointer transition-all ${isActive
      ? 'bg-cyan-500/10 border border-cyan-500/30'
      : 'hover:bg-white/5 border border-transparent'
      }`}
    onClick={onClick}
  >
    <MessageSquare
      className={`w-4 h-4 shrink-0 ${isActive ? 'text-cyan-400' : 'text-zinc-500'}`}
    />
    <span
      className={`text-sm truncate flex-1 ${isActive ? 'text-white font-medium' : 'text-zinc-400'
        }`}
    >
      {session.title}
    </span>
    {isActive && (
      <button
        onClick={(e) => { e.stopPropagation(); onDelete(); }}
        className="opacity-0 group-hover:opacity-100 p-1 hover:text-red-400 text-zinc-600 transition-all"
        title="Delete session"
      >
        <Trash2 className="w-3.5 h-3.5" />
      </button>
    )}
    {isActive && (
      <ChevronRight className="w-3.5 h-3.5 text-cyan-400 shrink-0" />
    )}
  </motion.div>
);

// ── Empty state ────────────────────────────────────────────────────────────────
const EmptyState = ({ onNew }) => (
  <div className="flex-1 flex flex-col items-center justify-center gap-6 text-center px-8">
    <div className="relative">
      <div className="absolute inset-0 rounded-full bg-cyan-500/20 blur-2xl scale-150" />
      <div className="relative w-20 h-20 rounded-2xl bg-white/5 border border-white/10 flex items-center justify-center">
        <Sparkles className="w-9 h-9 text-cyan-400" />
      </div>
    </div>
    <div>
      <h3 className="text-white font-semibold text-lg mb-1">Neural Interface Ready</h3>
      <p className="text-zinc-500 text-sm leading-relaxed">
        Start a new session to query your document archive with persistent AI memory.
      </p>
    </div>
    <motion.button
      whileHover={{ scale: 1.04 }}
      whileTap={{ scale: 0.97 }}
      onClick={onNew}
      className="flex items-center gap-2 px-5 py-2.5 bg-cyan-500 hover:bg-cyan-400 text-black font-semibold rounded-xl transition-colors shadow-lg shadow-cyan-500/30"
    >
      <Plus className="w-4 h-4" />
      New Chat
    </motion.button>
  </div>
);

// ── SSE stream parser ─────────────────────────────────────────────────────────
// Parses a raw SSE buffer into an array of { type, value } events.
// Handles the case where one network chunk contains multiple events OR
// where a single event is split across two chunks (buffering via caller).
function parseSSEChunk(rawText) {
  const events = [];
  // Split on the double-newline SSE delimiter
  const parts = rawText.split('\n\n');
  for (const part of parts) {
    const trimmed = part.trim();
    if (!trimmed) continue;

    // SSE spec: each event line starts with "data: "
    const dataLine = trimmed.startsWith('data: ')
      ? trimmed.slice(6)       // strip the "data: " prefix
      : trimmed;               // handle edge case of no prefix

    if (dataLine === '[DONE]') {
      events.push({ type: 'done' });
    } else if (dataLine.startsWith('[SOURCES]')) {
      try {
        const json = JSON.parse(dataLine.slice(9));
        events.push({ type: 'sources', value: json });
      } catch {
        events.push({ type: 'sources', value: [] });
      }
    } else if (dataLine.startsWith('[ERROR]')) {
      events.push({ type: 'error', value: dataLine.slice(7) });
    } else {
      // Regular token — unescape newlines the backend escaped for SSE wire format
      events.push({ type: 'token', value: dataLine.replace(/\\n/g, '\n') });
    }
  }
  return events;
}

// ── Main component ─────────────────────────────────────────────────────────────
const ChatInterface = ({ targetUserId }) => {
  const [sessions, setSessions] = useState([]);
  const [activeSessionId, setActiveSessionId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [streamingMsgId, setStreamingMsgId] = useState(null); // tracks which msg is being streamed
  const [loadingSession, setLoadingSession] = useState(false);
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);
  // Allows us to abort an in-flight stream if the user navigates away
  const abortControllerRef = useRef(null);

  // Auto-scroll whenever messages update or a stream token arrives
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isTyping]);

  // Cleanup abort controller on unmount
  useEffect(() => () => abortControllerRef.current?.abort(), []);

  // ── Fetch session list ──────────────────────────────────────────────────────
  const fetchSessions = useCallback(async () => {
    try {
      const data = await apiFetch('/chat/sessions');
      setSessions(data);
    } catch (err) {
      console.error('Failed to load sessions:', err);
    }
  }, []);

  useEffect(() => { fetchSessions(); }, [fetchSessions]);

  // ── Switch to a session ─────────────────────────────────────────────────────
  const openSession = useCallback(async (sessionId) => {
    // abort any running stream first
    abortControllerRef.current?.abort();
    setLoadingSession(true);
    setActiveSessionId(sessionId);
    setStreamingMsgId(null);
    try {
      const msgs = await apiFetch(`/chat/sessions/${sessionId}`);
      setMessages(msgs);
    } catch (err) {
      console.error('Failed to load messages:', err);
    } finally {
      setLoadingSession(false);
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  }, []);

  // ── Create new session ──────────────────────────────────────────────────────
  const createSession = useCallback(async () => {
    try {
      const session = await apiFetch('/chat/sessions', { method: 'POST' });
      setSessions((prev) => [session, ...prev]);
      setMessages([]);
      setActiveSessionId(session.id);
      setStreamingMsgId(null);
      setTimeout(() => inputRef.current?.focus(), 100);
    } catch (err) {
      console.error('Failed to create session:', err);
    }
  }, []);

  // ── Delete session ──────────────────────────────────────────────────────────
  const deleteSession = useCallback(async (sessionId) => {
    try {
      await apiFetch(`/chat/sessions/${sessionId}`, { method: 'DELETE' });
      setSessions((prev) => prev.filter((s) => s.id !== sessionId));
      if (activeSessionId === sessionId) {
        setActiveSessionId(null);
        setMessages([]);
        setStreamingMsgId(null);
      }
    } catch (err) {
      console.error('Failed to delete session:', err);
    }
  }, [activeSessionId]);

  // ── Send message — SSE streaming ────────────────────────────────────────────
  const handleSend = async (e) => {
    e.preventDefault();
    if (!input.trim() || !activeSessionId || isTyping) return;

    const userContent = input.trim();

    // Clear input immediately so the user can read what they typed in the bubble
    // We do NOT call setInput here via the controlled input path — we blur and
    // reset so that React does not re-focus and then lose cursor position.
    setInput('');
    setIsTyping(true);

    // 1. Optimistically add the user's message bubble
    const userMsgId = `user-${Date.now()}`;
    setMessages((prev) => [
      ...prev,
      { id: userMsgId, role: 'user', content: userContent, sources: [] },
    ]);

    // 2. Add a placeholder assistant bubble that we'll fill with streaming tokens
    const asstMsgId = `asst-stream-${Date.now()}`;
    setStreamingMsgId(asstMsgId);
    setMessages((prev) => [
      ...prev,
      { id: asstMsgId, role: 'assistant', content: '', sources: [] },
    ]);

    // 3. Create a fresh AbortController so the user can navigate away cleanly
    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      const res = await fetch(
        `${API}/chat/sessions/${activeSessionId}/stream`,
        {
          method: 'POST',
          signal: controller.signal,
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${getToken()}`,
            Accept: 'text/event-stream',
          },
          body: JSON.stringify({
            content: userContent,
            target_user_id: targetUserId ?? null,
          }),
        },
      );

      if (!res.ok) {
        const textBody = await res.text();
        try {
          const errBody = JSON.parse(textBody);
          throw new Error(errBody.detail || `Stream request failed (${res.status})`);
        } catch {
          throw new Error(`Stream request failed (${res.status}): ${textBody.substring(0, 80)}`);
        }
      }

      // 4. Read the body as a stream
      const reader = res.body.getReader();
      const decoder = new TextDecoder('utf-8');
      // leftover holds an incomplete SSE event between chunks
      let leftover = '';
      // eslint-disable-next-line no-constant-condition
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        // Decode the raw bytes and prepend any leftover from the previous chunk
        const text = leftover + decoder.decode(value, { stream: true });

        // SSE events are delimited by \n\n. The last slice may be incomplete —
        // we hold it in `leftover` and prepend it on the next iteration.
        const lastDelimiterIdx = text.lastIndexOf('\n\n');
        if (lastDelimiterIdx === -1) {
          // No complete event yet — buffer everything
          leftover = text;
          continue;
        }

        // Process every complete event in this chunk
        const completeText = text.slice(0, lastDelimiterIdx + 2);
        leftover = text.slice(lastDelimiterIdx + 2);

        const events = parseSSEChunk(completeText);
        let isDone = false;

        for (const event of events) {
          if (event.type === 'done') {
            isDone = true;
            break;
          }

          if (event.type === 'sources') {
            // Attach the sources array to the streaming assistant bubble
            setMessages((prev) =>
              prev.map((m) =>
                m.id === asstMsgId ? { ...m, sources: event.value } : m,
              ),
            );
          } else if (event.type === 'token') {
            // Append the token to the assistant bubble in real-time
            setMessages((prev) =>
              prev.map((m) =>
                m.id === asstMsgId
                  ? { ...m, content: m.content + event.value }
                  : m,
              ),
            );
          } else if (event.type === 'error') {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === asstMsgId
                  ? { ...m, content: `❌ ${event.value}` }
                  : m,
              ),
            );
            isDone = true;
            break;
          }
        }

        if (isDone) {
          reader.cancel();
          break;
        }
      }

      // 5. Update sidebar title from first message
      setSessions((prev) =>
        prev.map((s) =>
          s.id === activeSessionId
            ? { ...s, title: userContent.slice(0, 60) }
            : s,
        ),
      );

    } catch (err) {
      if (err.name === 'AbortError') {
        // User navigated away — silently swallow
        return;
      }
      // Show the error inside the assistant bubble
      setMessages((prev) =>
        prev.map((m) =>
          m.id === asstMsgId
            ? { ...m, content: `❌ ${err.message}` }
            : m,
        ),
      );
    } finally {
      setStreamingMsgId(null);
      setIsTyping(false);
      // Restore focus to input without causing a scroll jump
      requestAnimationFrame(() => inputRef.current?.focus({ preventScroll: true }));
    }
  };

  const activeSession = sessions.find((s) => s.id === activeSessionId);

  return (
    <div className="w-full h-[680px] flex rounded-2xl overflow-hidden border border-white/10 shadow-2xl shadow-black/50 bg-black">

      {/* ── Left Sidebar ─────────────────────────────────────────────────────── */}
      <div className="w-72 shrink-0 flex flex-col bg-zinc-950 border-r border-white/8">

        {/* Sidebar header */}
        <div className="p-4 border-b border-white/8">
          <div className="flex items-center gap-2 mb-4">
            <div className="w-7 h-7 rounded-lg bg-cyan-500/20 flex items-center justify-center">
              <Sparkles className="w-4 h-4 text-cyan-400" />
            </div>
            <span className="text-sm font-bold tracking-widest text-white uppercase">DocuBrain</span>
          </div>

          {/* New Chat button */}
          <motion.button
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.97 }}
            onClick={createSession}
            className="w-full flex items-center justify-center gap-2 py-2.5 px-3 rounded-xl
                       bg-cyan-500/10 hover:bg-cyan-500/20 border border-cyan-500/30 hover:border-cyan-500/60
                       text-cyan-400 font-medium text-sm transition-all
                       shadow-[0_0_20px_rgba(6,182,212,0.15)] hover:shadow-[0_0_30px_rgba(6,182,212,0.25)]"
          >
            <Plus className="w-4 h-4" />
            New Chat
          </motion.button>
        </div>

        {/* Session list */}
        <div className="flex-1 overflow-y-auto p-2 space-y-1">
          {sessions.length === 0 ? (
            <p className="text-zinc-600 text-xs text-center mt-6 px-4">
              No sessions yet. Start a new chat above.
            </p>
          ) : (
            <AnimatePresence>
              {sessions.map((s) => (
                <SessionRow
                  key={s.id}
                  session={s}
                  isActive={s.id === activeSessionId}
                  onClick={() => openSession(s.id)}
                  onDelete={() => deleteSession(s.id)}
                />
              ))}
            </AnimatePresence>
          )}
        </div>

        {/* Sidebar footer — professional mode indicator */}
        {targetUserId && (
          <div className="p-3 border-t border-white/8">
            <span className="flex items-center justify-center gap-1.5 text-[10px] font-mono bg-cyan-500/10 text-cyan-400 px-2 py-1.5 rounded-lg border border-cyan-500/20">
              CONTEXT: CLIENT ID {targetUserId}
            </span>
          </div>
        )}
      </div>

      {/* ── Main Chat Area ───────────────────────────────────────────────────── */}
      <div className="flex-1 flex flex-col bg-zinc-900/60 backdrop-blur-sm">

        {/* Chat header */}
        <div className="px-5 py-3.5 border-b border-white/8 bg-zinc-900/80 backdrop-blur-xl flex items-center gap-3">
          <div
            className={`w-2 h-2 rounded-full transition-all duration-500 ${streamingMsgId
              ? 'bg-cyan-400 shadow-[0_0_10px_rgba(6,182,212,1)] animate-pulse'
              : activeSessionId
                ? 'bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.8)]'
                : 'bg-zinc-600'
              }`}
          />
          <span className="text-sm font-medium text-zinc-300 truncate">
            {streamingMsgId
              ? 'Streaming response…'
              : activeSession
                ? activeSession.title
                : 'Neural Chat — Select or create a session'}
          </span>
          {activeSessionId && (
            <span className="ml-auto text-[10px] text-zinc-600 font-mono">
              Session #{activeSessionId}
            </span>
          )}
        </div>

        {/* Messages / Empty state */}
        {!activeSessionId ? (
          <EmptyState onNew={createSession} />
        ) : (
          <div className="flex-1 overflow-y-auto px-5 py-5 space-y-5 scroll-smooth">
            {loadingSession ? (
              <div className="flex items-center justify-center h-full">
                <Loader2 className="w-6 h-6 text-cyan-400 animate-spin" />
              </div>
            ) : (
              <>
                {messages.length === 0 && !isTyping && (
                  <div className="flex flex-col items-center justify-center h-full gap-3 text-center">
                    <Bot className="w-10 h-10 text-zinc-700" />
                    <p className="text-zinc-600 text-sm">Send a message to begin this session.</p>
                  </div>
                )}

                <AnimatePresence initial={false}>
                  {messages.map((msg, idx) => (
                    <MessageBubble
                      key={msg.id ?? idx}
                      msg={msg}
                      isStreaming={streamingMsgId === msg.id}
                    />
                  ))}
                </AnimatePresence>

                {/* Typing indicator — visible only before the first token arrives */}
                {isTyping && streamingMsgId && messages.find((m) => m.id === streamingMsgId)?.content === '' && (
                  <motion.div
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0 }}
                    className="flex gap-3 items-start"
                  >
                    <div className="w-8 h-8 rounded-full bg-zinc-800 ring-1 ring-white/10 flex items-center justify-center">
                      <Bot className="w-4 h-4 text-zinc-400" />
                    </div>
                    <div className="bg-white/5 border border-white/10 rounded-2xl backdrop-blur-sm">
                      <TypingDots />
                    </div>
                  </motion.div>
                )}

                <div ref={messagesEndRef} />
              </>
            )}
          </div>
        )}

        {/* Input bar */}
        <div className="p-4 border-t border-white/8 bg-zinc-900/80 backdrop-blur-xl">
          <form onSubmit={handleSend}>
            <div className="relative flex items-center gap-3">
              <input
                ref={inputRef}
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder={
                  !activeSessionId
                    ? 'Create or select a session first…'
                    : targetUserId
                      ? `Querying Client ${targetUserId}'s documents…`
                      : isTyping
                        ? 'Streaming response…'
                        : 'Ask anything about your documents…'
                }
                disabled={!activeSessionId || isTyping}
                className="flex-1 bg-zinc-950 border border-zinc-800 rounded-xl py-3.5 pl-4 pr-4
                           text-white text-sm placeholder:text-zinc-600
                           focus:outline-none focus:border-cyan-500/50 focus:ring-1 focus:ring-cyan-500/30
                           disabled:opacity-40 disabled:cursor-not-allowed transition-all"
              />
              <motion.button
                type="submit"
                disabled={!input.trim() || !activeSessionId || isTyping}
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                className="p-3 bg-cyan-500 hover:bg-cyan-400 disabled:bg-zinc-800 disabled:text-zinc-600
                           text-black rounded-xl transition-colors shadow-lg shadow-cyan-500/20
                           disabled:shadow-none disabled:cursor-not-allowed"
              >
                {isTyping
                  ? <Loader2 className="w-5 h-5 animate-spin" />
                  : <Send className="w-5 h-5" />
                }
              </motion.button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
};

export default ChatInterface;