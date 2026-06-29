import { useState, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { FileText, CheckCircle2, Clock, Loader2, Trash2, Upload, AlertCircle } from 'lucide-react';
import { API_BASE } from './api';

const getToken = () => localStorage.getItem('token');

const STATUS_CONFIG = {
  ready:      { label: 'Ready',      bg: 'bg-olive-50',       border: 'border-olive-300',      text: 'text-olive-800',      dot: 'bg-olive-500' },
  processing: { label: 'Processing', bg: 'bg-mustard-50',     border: 'border-mustard-300',    text: 'text-mustard-800',    dot: 'bg-mustard-500 animate-pulse' },
  pending:    { label: 'Pending',    bg: 'bg-terracotta-50',  border: 'border-terracotta-200', text: 'text-terracotta-700', dot: 'bg-terracotta-300' },
  failed:     { label: 'Failed',     bg: 'bg-red-50',         border: 'border-red-300',        text: 'text-red-700',        dot: 'bg-red-500' },
};

const StatusBadge = ({ status }) => {
  const cfg = STATUS_CONFIG[status] ?? STATUS_CONFIG.pending;
  return (
    <span className={`inline-flex items-center gap-1.5 text-[11px] font-bold px-2.5 py-1 rounded-full border ${cfg.bg} ${cfg.border} ${cfg.text}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${cfg.dot}`} />
      {cfg.label}
    </span>
  );
};

export default function DocumentList({ documents, isLoading, onDelete, onUpload }) {
  const [uploading, setUploading] = useState(false);
  const [deleting, setDeleting]   = useState(null);
  const [error, setError]         = useState('');
  const [dragOver, setDragOver]   = useState(false);
  const inputRef = useRef();

  const uploadFile = async (file) => {
    if (!file) return;
    if (file.type !== 'application/pdf') { setError('Only PDF files are accepted'); return; }
    setError('');
    setUploading(true);
    try {
      const body = new FormData();
      body.append('file', file);
      const res = await fetch(`${API_BASE}/upload/`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${getToken()}` },
        body,
      });
      if (!res.ok) {
        const d = await res.json().catch(() => ({}));
        setError(d.detail ?? 'Upload failed');
      } else {
        onUpload?.();
      }
    } catch {
      setError('Upload failed — check connection');
    } finally {
      setUploading(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    uploadFile(e.dataTransfer.files?.[0]);
  };

  const handleDelete = async (id) => {
    setDeleting(id);
    try {
      await fetch(`${API_BASE}/documents/${id}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${getToken()}` },
      });
      onDelete?.();
    } catch { /* ignore */ }
    finally { setDeleting(null); }
  };

  return (
    <div className="space-y-6 max-w-4xl">
      <div>
        <h2 className="text-xl font-black text-terracotta-950">Documents</h2>
        <p className="text-terracotta-700 text-sm mt-0.5 font-medium">Upload PDFs to study with AI</p>
      </div>

      {/* Upload zone */}
      <div
        onDragOver={e => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        onClick={() => !uploading && inputRef.current?.click()}
        className={`relative rounded-2xl p-10 flex flex-col items-center gap-3 cursor-pointer transition-all border-2 border-dashed ${
          dragOver
            ? 'bg-terracotta-50 border-terracotta-400'
            : 'glass border-terracotta-200/60 hover:border-terracotta-300'
        }`}>
        <input ref={inputRef} type="file" accept=".pdf" className="hidden"
          onChange={e => uploadFile(e.target.files?.[0])} />
        <div className={`w-12 h-12 rounded-2xl flex items-center justify-center transition-all ${
          dragOver ? 'bg-terracotta-100' : 'bg-white/70'
        }`}>
          {uploading
            ? <Loader2 className="w-6 h-6 text-terracotta-500 animate-spin" />
            : <Upload className={`w-6 h-6 ${dragOver ? 'text-terracotta-600' : 'text-terracotta-400'}`} />
          }
        </div>
        <div className="text-center">
          <p className={`text-sm font-bold ${dragOver ? 'text-terracotta-800' : 'text-terracotta-700'}`}>
            {uploading ? 'Uploading…' : dragOver ? 'Drop to upload' : 'Drop a PDF here or click to browse'}
          </p>
          <p className="text-xs text-terracotta-500 mt-1 font-medium">PDF only · Max 20 MB</p>
        </div>
        {error && (
          <div className="flex items-center gap-2 text-red-700 text-xs bg-red-50 border border-red-200 rounded-xl px-3 py-2 font-semibold">
            <AlertCircle className="w-3.5 h-3.5 shrink-0" /> {error}
          </div>
        )}
      </div>

      {/* Document list */}
      {isLoading ? (
        <div className="flex items-center justify-center h-32 gap-2">
          <Loader2 className="w-5 h-5 text-terracotta-500 animate-spin" />
          <span className="text-terracotta-700 text-sm font-semibold">Loading documents…</span>
        </div>
      ) : documents.length === 0 ? (
        <div className="glass rounded-2xl p-12 flex flex-col items-center gap-3 text-center border-2 border-dashed border-terracotta-200/60">
          <div className="w-12 h-12 rounded-xl bg-white/70 flex items-center justify-center">
            <FileText className="w-6 h-6 text-terracotta-400" />
          </div>
          <div>
            <p className="text-terracotta-800 text-sm font-bold">No documents yet</p>
            <p className="text-terracotta-600 text-xs mt-1 font-medium">Upload a PDF to get started</p>
          </div>
        </div>
      ) : (
        <div className="space-y-2">
          <p className="text-xs font-bold text-terracotta-700 uppercase tracking-wider">
            {documents.length} document{documents.length !== 1 ? 's' : ''}
          </p>
          <AnimatePresence>
            {documents.map((doc, i) => (
              <motion.div key={doc.id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, x: -20 }} transition={{ delay: i * 0.04 }}
                className="glass glass-hover rounded-xl px-4 py-3.5 flex items-center gap-4 group transition-all">
                <div className="w-9 h-9 rounded-lg bg-terracotta-50 flex items-center justify-center shrink-0 border border-terracotta-200">
                  <FileText className="w-4 h-4 text-terracotta-600" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-bold text-terracotta-950 truncate">{doc.filename}</p>
                  <div className="flex items-center gap-3 mt-1">
                    <StatusBadge status={doc.status} />
                    <span className="text-[11px] text-terracotta-600 flex items-center gap-1 font-medium">
                      <Clock className="w-3 h-3" />
                      {doc.upload_date ? new Date(doc.upload_date).toLocaleDateString() : ''}
                    </span>
                  </div>
                </div>
                {doc.status === 'ready' && <CheckCircle2 className="w-4 h-4 text-olive-600 shrink-0" />}
                <button
                  onClick={() => handleDelete(doc.id)}
                  disabled={deleting === doc.id}
                  className="p-1.5 rounded-lg text-terracotta-300 hover:text-red-600 hover:bg-red-50 transition-all opacity-0 group-hover:opacity-100 disabled:opacity-50">
                  {deleting === doc.id ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
                </button>
              </motion.div>
            ))}
          </AnimatePresence>
        </div>
      )}
    </div>
  );
}
