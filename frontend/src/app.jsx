import { useState, useEffect } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { motion, useMotionValue } from 'framer-motion';
import Login from './Login';
import Dashboard from './Dashboard';

const CustomCursor = () => {
  const x = useMotionValue(-100);
  const y = useMotionValue(-100);
  const [hover, setHover] = useState(false);

  useEffect(() => {
    const move = e => { x.set(e.clientX - 16); y.set(e.clientY - 16); };
    const over  = e => setHover(!!(e.target.closest('button,a,input,label,select,textarea')));
    window.addEventListener('mousemove', move);
    window.addEventListener('mouseover', over);
    return () => {
      window.removeEventListener('mousemove', move);
      window.removeEventListener('mouseover', over);
    };
  }, []);

  return (
    <motion.div className="fixed top-0 left-0 pointer-events-none z-[9999]" style={{ translateX: x, translateY: y }}>
      <motion.div
        animate={{ scale: hover ? 1.6 : 1 }}
        transition={{ type: 'spring', stiffness: 350, damping: 20 }}
        className="w-8 h-8 rounded-full border-2 border-terracotta-500"
      />
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-1.5 h-1.5 bg-terracotta-600 rounded-full" />
    </motion.div>
  );
};

const ProtectedRoute = ({ children }) => {
  const token = localStorage.getItem('token');
  if (!token) return <Navigate to="/login" replace />;
  return children;
};

function App() {
  return (
    <>
      <CustomCursor />
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/dashboard" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </>
  );
}

export default App;
