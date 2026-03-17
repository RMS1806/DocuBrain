import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { UserPlus, Shield, Users, ChevronRight, CheckCircle, AlertCircle } from 'lucide-react';

const NetworkInterface = ({ onSelectClient }) => {
  const [role] = useState(localStorage.getItem('role') || 'client');
  const [email, setEmail] = useState('');
  const [clients, setClients] = useState([]);
  const [status, setStatus] = useState('');
  const [loading, setLoading] = useState(false);

  // --- PROFESSIONAL LOGIC: Fetch Clients ---
  useEffect(() => {
    if (role === 'professional') {
      fetchClients();
    }
  }, [role]);

  const fetchClients = async () => {
    try {
      const token = localStorage.getItem("token");
      const res = await fetch("http://localhost:8000/professional/clients", {
        headers: { "Authorization": `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setClients(data);
      }
    } catch (err) {
      console.error("Failed to fetch client network");
    }
  };

  // --- CLIENT LOGIC: Invite Professional ---
  const handleInvite = async (e) => {
    e.preventDefault();
    setLoading(true);
    setStatus('');

    try {
      const token = localStorage.getItem("token");
      const res = await fetch("http://localhost:8000/link/invite", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${token}`
        },
        body: JSON.stringify({ professional_email: email })
      });

      const data = await res.json();
      if (res.ok) {
        setStatus(`SUCCESS: ${data.message}`);
        setEmail('');
      } else {
        setStatus(`ERROR: ${data.detail}`);
      }
    } catch (err) {
      setStatus("ERROR: Neural Link Failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="w-full max-w-4xl flex flex-col items-center">

      {/* HEADER */}
      <div className="text-center mb-12">
        <h2 className="text-3xl font-bold text-white mb-2 tracking-tight">NEURAL NETWORK</h2>
        <p className="text-zinc-500 font-mono text-xs tracking-widest">
          {role === 'client' ? 'GRANT READ PERMISSIONS' : 'CLIENT CASE FILES'}
        </p>
      </div>

      {/* --- VIEW FOR CLIENTS --- */}
      {role === 'client' && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="w-full max-w-md bg-zinc-900/50 border border-white/10 rounded-2xl p-8 backdrop-blur-xl shadow-2xl"
        >
          <div className="flex items-center gap-3 mb-6">
            <div className="p-3 bg-neon-blue/10 rounded-full text-neon-blue border border-neon-blue/20">
              <Shield className="w-6 h-6" />
            </div>
            <div>
              <h3 className="font-bold text-zinc-200">Grant Access</h3>
              <p className="text-xs text-zinc-500">Allow a professional to view your vault.</p>
            </div>
          </div>

          <form onSubmit={handleInvite} className="space-y-4">
            <div>
              <label className="text-[10px] font-mono text-zinc-500 ml-1 mb-1 block">PROFESSIONAL ID (EMAIL)</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="doctor@hospital.net"
                className="w-full bg-black/50 border border-zinc-800 rounded-xl p-3 text-white focus:outline-none focus:border-neon-blue transition-colors text-sm"
                required
              />
            </div>

            {status && (
              <div className={`p-3 rounded-lg text-xs font-mono flex items-center gap-2 ${status.includes('SUCCESS') ? 'bg-green-500/10 text-green-400' : 'bg-red-500/10 text-red-400'}`}>
                {status.includes('SUCCESS') ? <CheckCircle className="w-4 h-4" /> : <AlertCircle className="w-4 h-4" />}
                {status.replace('SUCCESS: ', '').replace('ERROR: ', '')}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-zinc-800 hover:bg-neon-blue text-zinc-300 hover:text-black font-bold py-3 rounded-xl transition-all flex items-center justify-center gap-2 mt-4"
            >
              {loading ? 'LINKING...' : 'ESTABLISH LINK'} <UserPlus className="w-4 h-4" />
            </button>
          </form>
        </motion.div>
      )}

      {/* --- VIEW FOR PROFESSIONALS --- */}
      {role === 'professional' && (
        <div className="w-full grid gap-4">
          {clients.length === 0 ? (
            <div className="text-center py-12 border border-dashed border-zinc-800 rounded-xl bg-zinc-900/20 text-zinc-500">
              NO CLIENTS LINKED YET
            </div>
          ) : (
            clients.map((client, idx) => (
              <motion.div
                key={client.id}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: idx * 0.1 }}
                onClick={() => onSelectClient(client.id)}
                className="group flex items-center justify-between p-4 bg-zinc-900/50 border border-white/5 hover:border-neon-blue/50 rounded-xl cursor-pointer transition-all hover:bg-zinc-800"
              >
                <div className="flex items-center gap-4">
                  <div className="w-10 h-10 rounded-full bg-zinc-800 flex items-center justify-center text-zinc-400 group-hover:text-white group-hover:bg-neon-blue/20 transition-colors">
                    <Users className="w-5 h-5" />
                  </div>
                  <div>
                    <h4 className="font-bold text-zinc-200 group-hover:text-neon-blue transition-colors">{client.email}</h4>
                    <p className="text-xs text-zinc-500 font-mono">ID: {client.id} • LINKED: {new Date(client.joined_at).toLocaleDateString()}</p>
                  </div>
                </div>
                <div className="flex items-center gap-2 text-xs font-bold text-zinc-600 group-hover:text-white transition-colors">
                  ACCESS VAULT <ChevronRight className="w-4 h-4" />
                </div>
              </motion.div>
            ))
          )}
        </div>
      )}

    </div>
  );
};

export default NetworkInterface;