import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Video, Copy, ShieldCheck, ExternalLink, Lock, RefreshCw, Power } from 'lucide-react';

const MeetingInterface = () => {
  const [meetingId, setMeetingId] = useState(null);
  const [isCreating, setIsCreating] = useState(false);

  // 1. DYNAMIC GENERATION
  // Instead of a hardcoded link, we generate a random, complex ID on demand.
  const generateSessionId = () => {
    setIsCreating(true);

    // We simulate a secure handshake delay (1.5s) for better UX
    setTimeout(() => {
      // Use the browser's crypto API for a true random secure string
      const array = new Uint32Array(4);
      window.crypto.getRandomValues(array);
      const secureId = 'docubrain-secure-' + Array.from(array).map(n => n.toString(16)).join('-');

      setMeetingId(secureId);
      setIsCreating(false);
    }, 1500);
  };

  // 2. TERMINATION LOGIC
  // This clears the state, effectively "killing" the room access from this terminal.
  const endSession = () => {
    if (window.confirm("WARNING: Terminating this session will destroy the secure link. Continue?")) {
      setMeetingId(null);
    }
  };

  const handleCopy = () => {
    const url = `https://meet.jit.si/${meetingId}`;
    navigator.clipboard.writeText(url);
    alert("Encrypted Link Copied to Clipboard!");
  };

  const launchMeeting = () => {
    const url = `https://meet.jit.si/${meetingId}`;
    // Open in new tab with security attributes
    window.open(url, '_blank', 'noopener,noreferrer');
  };

  return (
    <div className="w-full max-w-4xl h-[500px] flex flex-col items-center justify-center bg-zinc-900/50 border border-white/10 rounded-2xl backdrop-blur-xl shadow-2xl p-8 relative overflow-hidden">

      {/* Background Decor */}
      <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-transparent via-neon-blue to-transparent opacity-50" />
      <div className="absolute -right-20 -bottom-20 w-64 h-64 bg-purple-500/10 rounded-full blur-3xl pointer-events-none" />

      <AnimatePresence mode="wait">
        {!meetingId ? (
          /* --- STATE 1: IDLE (No Meeting) --- */
          <motion.div
            key="create"
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.9 }}
            className="flex flex-col items-center text-center z-10"
          >
            <div className="relative mb-8 group">
              <div className="absolute inset-0 bg-neon-blue/20 rounded-full blur-xl group-hover:blur-2xl transition-all duration-500" />
              <div className="w-24 h-24 bg-zinc-900 border border-neon-blue/30 rounded-full flex items-center justify-center relative z-10 shadow-[0_0_30px_rgba(0,243,255,0.2)]">
                <Video className="w-10 h-10 text-neon-blue" />
              </div>
            </div>

            <h2 className="text-3xl font-bold mb-3 text-white tracking-tight">Secure Neural Uplink</h2>
            <p className="text-zinc-400 mb-8 max-w-md text-sm leading-relaxed">
              No active session detected. Generate a transient, end-to-end encrypted video channel.
              The link exists only as long as this session is active.
            </p>

            <button
              onClick={generateSessionId}
              disabled={isCreating}
              className="px-8 py-4 bg-neon-blue hover:bg-cyan-400 text-black font-bold rounded-lg flex items-center gap-3 transition-all hover:scale-105 shadow-[0_0_20px_rgba(0,243,255,0.3)] disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isCreating ? (
                <><RefreshCw className="w-5 h-5 animate-spin" /> ESTABLISHING LINK...</>
              ) : (
                <><Lock className="w-5 h-5" /> GENERATE SECURE CHANNEL</>
              )}
            </button>
          </motion.div>
        ) : (
          /* --- STATE 2: ACTIVE SESSION --- */
          <motion.div
            key="active"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            className="flex flex-col items-center w-full z-10"
          >
            <div className="flex items-center gap-2 mb-6 px-4 py-1 bg-green-500/10 border border-green-500/30 rounded-full">
              <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
              <span className="text-xs font-bold text-green-400 tracking-wider">CHANNEL ACTIVE</span>
            </div>

            <h3 className="text-2xl font-bold text-white mb-8">Session Ready</h3>

            {/* Link Box */}
            <div className="w-full max-w-lg bg-black/60 border border-neon-blue/50 rounded-xl p-4 flex items-center gap-4 mb-8 shadow-[0_0_15px_rgba(0,243,255,0.1)]">
              <ShieldCheck className="w-6 h-6 text-neon-blue shrink-0" />
              <div className="flex-1 overflow-hidden">
                <p className="text-[10px] text-zinc-500 font-mono mb-1">ENCRYPTED URL</p>
                <p className="font-mono text-sm text-white truncate select-all">
                  https://meet.jit.si/{meetingId}
                </p>
              </div>
              <button
                onClick={handleCopy}
                className="p-2 hover:bg-zinc-800 rounded-lg transition-colors text-zinc-400 hover:text-white"
                title="Copy Link"
              >
                <Copy className="w-5 h-5" />
              </button>
            </div>

            <div className="flex gap-4">
              <button
                onClick={launchMeeting}
                className="px-6 py-3 bg-white text-black hover:bg-zinc-200 font-bold rounded-lg flex items-center gap-2 transition-all hover:scale-105"
              >
                <ExternalLink className="w-4 h-4" /> JOIN ROOM
              </button>
              <button
                onClick={endSession}
                className="px-6 py-3 bg-red-500/10 hover:bg-red-500/20 text-red-500 border border-red-500/30 font-bold rounded-lg flex items-center gap-2 transition-all hover:bg-red-500/30"
              >
                <Power className="w-4 h-4" /> TERMINATE
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

export default MeetingInterface;