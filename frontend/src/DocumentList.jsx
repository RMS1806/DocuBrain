import { motion } from 'framer-motion';
import { FileText, CheckCircle, Clock, Loader2, Database, Trash2 } from 'lucide-react';
import { API_BASE } from './api';

const DocumentList = ({ documents, isLoading, onDelete }) => {

  const handleDelete = async (docId, filename) => {
    if (!confirm(`Are you sure you want to PERMANENTLY delete "${filename}"? This cannot be undone.`)) {
      return;
    }

    try {
      const token = localStorage.getItem("token");
      const res = await fetch(`${API_BASE}/documents/${docId}`, {
        method: "DELETE",
        headers: { "Authorization": `Bearer ${token}` }
      });

      if (res.ok) {
        // Trigger a refresh in the parent component
        if (onDelete) onDelete();
      } else {
        alert("Failed to delete document");
      }
    } catch (err) {
      console.error(err);
      alert("Error connecting to server");
    }
  };

  if (isLoading) {
    return (
      <div className="w-full flex flex-col items-center justify-center py-12 gap-4">
        <Loader2 className="w-8 h-8 text-neon-blue animate-spin" />
        <span className="text-zinc-500 font-mono text-xs animate-pulse">ACCESSING NEURAL ARCHIVE...</span>
      </div>
    );
  }

  if (documents.length === 0) {
    return (
      <div className="text-center py-12 border border-dashed border-zinc-800 rounded-xl mt-8 bg-zinc-900/20">
        <Database className="w-12 h-12 text-zinc-700 mx-auto mb-3" />
        <p className="text-zinc-500 font-mono text-sm">NO DATA ARTIFACTS FOUND</p>
      </div>
    );
  }

  return (
    <div className="w-full max-w-4xl mt-12 mb-20">
      <div className="flex items-center gap-2 mb-6 border-b border-white/10 pb-2">
        <Database className="w-5 h-5 text-neon-blue" />
        <h3 className="text-lg font-bold tracking-wider text-white">YOUR DATA VAULT</h3>
        <span className="ml-auto text-xs font-mono text-zinc-500">{documents.length} FILES SECURED</span>
      </div>

      <div className="grid gap-3">
        {documents.map((doc, index) => (
          <motion.div
            key={doc.id}
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: index * 0.1 }}
            className="group relative bg-zinc-900/40 border border-white/5 hover:border-neon-blue/50 rounded-lg p-4 transition-all duration-300 hover:bg-zinc-900/80 flex items-center justify-between"
          >

            {/* File Info */}
            <div className="flex items-center gap-4">
              <div className="p-3 bg-zinc-800 rounded-lg group-hover:bg-neon-blue/10 transition-colors">
                <FileText className="w-6 h-6 text-zinc-400 group-hover:text-neon-blue" />
              </div>
              <div>
                <h4 className="font-bold text-sm tracking-wide text-zinc-200 group-hover:text-white">
                  {doc.filename}
                </h4>
                <div className="flex items-center gap-3 mt-1">
                  <span className="text-xs font-mono text-zinc-500">
                    {(doc.file_size / 1024).toFixed(1)} KB
                  </span>
                  <span className="text-zinc-700">|</span>
                  <span className="text-xs font-mono text-zinc-500">
                    {new Date(doc.upload_date).toLocaleDateString()}
                  </span>
                </div>
              </div>
            </div>

            {/* Right Side Actions */}
            <div className="flex items-center gap-4">
              {/* Status Badge */}
              <div className={`px-3 py-1 rounded-full border flex items-center gap-2 text-xs font-bold tracking-wider ${doc.status === 'completed'
                ? 'bg-green-500/10 border-green-500/20 text-green-400'
                : doc.status === 'processing'
                  ? 'bg-blue-500/10 border-blue-500/20 text-blue-400 animate-pulse'
                  : 'bg-zinc-800 border-zinc-700 text-zinc-500'
                }`}>
                {doc.status === 'completed' && <CheckCircle className="w-3 h-3" />}
                {doc.status === 'processing' && <Loader2 className="w-3 h-3 animate-spin" />}
                {doc.status === 'pending' && <Clock className="w-3 h-3" />}
                {doc.status.toUpperCase()}
              </div>

              {/* Delete Button (Only appears on hover) */}
              <button
                onClick={() => handleDelete(doc.id, doc.filename)}
                className="p-2 text-zinc-600 hover:text-red-500 hover:bg-red-500/10 rounded-lg transition-all opacity-0 group-hover:opacity-100"
                title="Purge File"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          </motion.div>
        ))}
      </div>
    </div>
  );
};

export default DocumentList;