import { useState, useEffect } from 'react';
import { motion, useMotionValue } from 'framer-motion';
import { Upload, FileText, Cpu, LogOut, User, MessageSquare, Database, Video, Globe } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { API_BASE } from './api';
import DocumentList from './DocumentList';
import ChatInterface from './ChatInterface';
import MeetingInterface from './MeetingInterface';
import NetworkInterface from './NetworkInterface';

// --- VISUAL COMPONENTS (Backgrounds/Cursor) ---
const ParticleBackground = () => {
  return (
    <div className="absolute inset-0 overflow-hidden pointer-events-none">
      {[...Array(20)].map((_, i) => (
        <motion.div key={i} className="absolute bg-neon-blue rounded-full opacity-20" initial={{ x: Math.random() * window.innerWidth, y: Math.random() * window.innerHeight, scale: Math.random() * 0.5 + 0.5 }} animate={{ y: [null, Math.random() * -100], opacity: [0.2, 0] }} transition={{ duration: Math.random() * 5 + 5, repeat: Infinity, ease: "linear" }} style={{ width: Math.random() * 4 + 1 + 'px', height: Math.random() * 4 + 1 + 'px' }} />
      ))}
    </div>
  );
};

// --- UPGRADED SMART CURSOR ---
const CustomCursor = () => {
  const cursorX = useMotionValue(-100);
  const cursorY = useMotionValue(-100);
  const [isHovering, setIsHovering] = useState(false);

  useEffect(() => {
    // 1. Move the cursor
    const moveCursor = (e) => {
      cursorX.set(e.clientX - 16);
      cursorY.set(e.clientY - 16);
    };

    // 2. Check if hovering over clickable elements
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <motion.div
      className="fixed top-0 left-0 pointer-events-none z-[9999] mix-blend-difference"
      style={{
        translateX: cursorX,
        translateY: cursorY,
      }}
    >
      {/* Outer Ring - Expands on Hover */}
      <motion.div
        animate={{
          scale: isHovering ? 1.5 : 1,
          opacity: isHovering ? 1 : 0.5,
          borderColor: isHovering ? '#00f3ff' : '#ffffff'
        }}
        className="w-8 h-8 rounded-full border-2 transition-colors duration-200"
      />

      {/* Inner Dot - Always visible */}
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-1 h-1 bg-neon-blue rounded-full shadow-[0_0_10px_#00f3ff]" />
    </motion.div>
  );
};

// --- MAIN DASHBOARD ---
function Dashboard() {
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState("AWAITING INPUT");
  const [documents, setDocuments] = useState([]);
  const [isLoadingDocs, setIsLoadingDocs] = useState(true);
  const [activeTab, setActiveTab] = useState('vault');
  const [targetUserId, setTargetUserId] = useState(null);
  const userRole = localStorage.getItem('role');
  const navigate = useNavigate();

  // Fetch Documents
  const fetchDocuments = async (targetId = null) => {
    setIsLoadingDocs(true);
    try {
      const token = localStorage.getItem("token");
      let url = `${API_BASE}/documents/`;
      if (targetId) url += `?target_user_id=${targetId}`;
      const res = await fetch(url, { headers: { "Authorization": `Bearer ${token}` } });
      if (res.ok) {
        setDocuments(await res.json());
      }
    } catch (err) { console.error(err); }
    finally { setIsLoadingDocs(false); }
  };

  useEffect(() => { fetchDocuments(targetUserId); }, [targetUserId]);

  const handleLogout = () => { localStorage.clear(); navigate('/login'); };
  const handleSelectClient = (clientId) => { setTargetUserId(clientId); setActiveTab('vault'); };

  // --- 🔴 UPDATED UPLOAD LOGIC ---
  const handleFileUpload = async (event) => {
    const selectedFile = event.target.files[0];
    if (!selectedFile) return;

    // 1. DUPLICATE CHECK
    const isDuplicate = documents.some(doc => doc.filename === selectedFile.name);

    if (isDuplicate) {
      setUploadStatus("ERROR: DUPLICATE FILE DETECTED");
      setTimeout(() => setUploadStatus("AWAITING INPUT"), 3000);
      return;
    }

    setFile(selectedFile);
    setUploading(true);
    setUploadStatus("ENCRYPTING...");

    const formData = new FormData();
    formData.append("file", selectedFile);
    const token = localStorage.getItem("token");

    try {
      const response = await fetch(`${API_BASE}/upload/`, {
        method: "POST",
        headers: { "Authorization": `Bearer ${token}` },
        body: formData,
      });

      if (response.ok) {
        setUploadStatus("UPLOAD SECURED");

        // 2. AUTO-STATUS UPDATE SIMULATION
        const newTempDoc = {
          id: Date.now(),
          filename: selectedFile.name,
          file_size: selectedFile.size,
          upload_date: new Date().toISOString(),
          status: "pending"
        };

        setDocuments(prev => [newTempDoc, ...prev]);

        setTimeout(() => {
          setDocuments(prev => prev.map(d => d.id === newTempDoc.id ? { ...d, status: "processing" } : d));
        }, 2000);

        setTimeout(() => {
          setDocuments(prev => prev.map(d => d.id === newTempDoc.id ? { ...d, status: "completed" } : d));
          fetchDocuments(targetUserId); // Refresh from DB to get real ID
        }, 5000);

        setTimeout(() => { setFile(null); setUploading(false); setUploadStatus("AWAITING INPUT"); }, 3000);
      } else {
        const textData = await response.text();
        try {
          const errorData = JSON.parse(textData);
          setUploadStatus("FAILED: " + (errorData.detail || "Error"));
        } catch {
          setUploadStatus(`FAILED (${response.status}): ${textData.substring(0, 50)}...`);
        }
        setUploading(false);
      }
    } catch (error) {
      setUploadStatus("CONNECTION SEVERED");
      setUploading(false);
    }
  };

  return (
    <div className="min-h-screen bg-black text-white font-sans selection:bg-neon-blue selection:text-black overflow-hidden relative overflow-y-auto">
      <CustomCursor />
      <ParticleBackground />
      <div className="absolute inset-0 bg-[linear-gradient(to_right,#4f4f4f2e_1px,transparent_1px),linear-gradient(to_bottom,#4f4f4f2e_1px,transparent_1px)] bg-[size:4rem_4rem] [mask-image:radial-gradient(ellipse_60%_50%_at_50%_0%,#000_70%,transparent_100%)] pointer-events-none" />

      {/* Header */}
      <nav className="relative z-20 flex justify-between items-center p-6 border-b border-white/10 bg-zinc-900/50 backdrop-blur-md sticky top-0">
        <div className="flex items-center gap-2">
          <Cpu className="text-neon-blue w-6 h-6" />
          <span className="font-bold tracking-wider text-xl">DOCU<span className="text-neon-blue">BRAIN</span></span>
        </div>
        <div className="flex items-center gap-4">
          {targetUserId && (
            <div className="hidden md:flex items-center gap-2 px-3 py-1 bg-neon-blue/10 border border-neon-blue/30 rounded-full animate-pulse">
              <span className="w-2 h-2 bg-neon-blue rounded-full" />
              <span className="text-xs font-bold text-neon-blue">VIEWING CLIENT ID: {targetUserId}</span>
              <button onClick={() => setTargetUserId(null)} className="ml-2 hover:text-white text-neon-blue/50">✕</button>
            </div>
          )}
          <div className="flex items-center gap-2 px-3 py-1 bg-zinc-800 rounded-full border border-white/5">
            <User className="w-4 h-4 text-zinc-400" />
            <span className="text-xs font-mono text-zinc-300 uppercase">{userRole || 'Unknown'}</span>
          </div>
          <button onClick={handleLogout} className="flex items-center gap-2 text-zinc-400 hover:text-red-400 transition-colors text-sm font-mono group cursor-pointer">
            LOGOUT <LogOut className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
          </button>
        </div>
      </nav>

      {/* Tab Navigation */}
      <div className="relative z-10 flex justify-center mt-8 gap-2 md:gap-4 flex-wrap px-4">
        {[
          { id: 'vault', label: 'DATA VAULT', icon: Database },
          { id: 'chat', label: 'NEURAL CHAT', icon: MessageSquare },
          { id: 'meet', label: 'SECURE MEET', icon: Video },
          { id: 'network', label: 'NETWORK', icon: Globe },
        ].map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`px-4 md:px-6 py-2 rounded-full font-bold text-xs md:text-sm tracking-wider transition-all duration-300 border flex items-center gap-2 cursor-pointer ${activeTab === tab.id
              ? 'bg-neon-blue text-black border-neon-blue shadow-[0_0_15px_rgba(0,243,255,0.4)]'
              : 'bg-zinc-900/80 text-zinc-500 border-zinc-800 hover:border-zinc-600 hover:text-zinc-300'
              }`}
          >
            <tab.icon className="w-4 h-4" /> {tab.label}
          </button>
        ))}
      </div>

      {/* Main Content */}
      <main className="relative z-10 flex flex-col items-center justify-start min-h-[calc(100vh-140px)] p-4 pt-8">

        {/* TAB 1: VAULT */}
        <div className={activeTab === 'vault' ? 'w-full flex flex-col items-center' : 'hidden'}>
          {!targetUserId && (
            <motion.div className="relative group w-full max-w-xl mb-12" whileHover={{ scale: 1.01 }}>
              <div className="absolute -inset-1 bg-gradient-to-r from-neon-blue to-purple-600 rounded-2xl opacity-20 group-hover:opacity-50 blur transition duration-1000" />
              <div className="relative bg-zinc-900/80 backdrop-blur-xl border border-white/10 rounded-2xl p-8 flex flex-col items-center text-center">
                {uploading ? (
                  <div className="flex flex-col items-center">
                    <div className="w-16 h-16 border-4 border-zinc-800 border-t-neon-blue rounded-full mb-6 animate-spin" />
                    <p className="font-mono text-neon-blue">{uploadStatus}</p>
                  </div>
                ) : (
                  <>
                    <div className="w-16 h-16 bg-zinc-800/50 rounded-full flex items-center justify-center mb-4">
                      <Upload className="w-8 h-8 text-zinc-400" />
                    </div>
                    <h3 className="text-xl font-bold mb-2">Upload Data</h3>
                    <label className="relative inline-flex items-center px-8 py-3 bg-neon-blue rounded-lg cursor-pointer hover:bg-cyan-400 transition-colors text-black font-bold">
                      <FileText className="w-4 h-4 mr-2" /> SELECT FILE
                      <input type="file" className="hidden" onChange={handleFileUpload} />
                    </label>
                    {uploadStatus.includes("ERROR") && <p className="mt-3 text-red-400 font-mono text-xs">{uploadStatus}</p>}
                  </>
                )}
              </div>
            </motion.div>
          )}

          <DocumentList
            documents={documents}
            isLoading={isLoadingDocs}
            onDelete={() => fetchDocuments(targetUserId)}
          />
        </div>

        {/* TAB 2: CHAT (HIDDEN, NOT UNMOUNTED) */}
        <div className={activeTab === 'chat' ? 'w-full flex justify-center h-full' : 'hidden'}>
          <ChatInterface targetUserId={targetUserId} />
        </div>

        {/* TAB 3: MEET */}
        <div className={activeTab === 'meet' ? 'w-full flex justify-center h-full' : 'hidden'}>
          <MeetingInterface />
        </div>

        {/* TAB 4: NETWORK */}
        <div className={activeTab === 'network' ? 'w-full flex justify-center h-full' : 'hidden'}>
          <NetworkInterface onSelectClient={handleSelectClient} />
        </div>

      </main>
    </div>
  );
}

export default Dashboard;