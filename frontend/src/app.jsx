import { Routes, Route, Navigate } from 'react-router-dom';
import Login from './Login';
import Dashboard from './Dashboard'; // Make sure you moved your old App.jsx code here!

// --- GUARD COMPONENT ---
// If no token exists in local storage, kick them back to Login
const ProtectedRoute = ({ children }) => {
  const token = localStorage.getItem('token');

  if (!token) {
    return <Navigate to="/login" replace />;
  }

  return children;
};

// --- MAIN APP ROUTER ---
function App() {
  return (
    <Routes>
      {/* 1. Login Route */}
      <Route path="/login" element={<Login />} />

      {/* 2. Protected Dashboard Route */}
      <Route
        path="/dashboard"
        element={
          <ProtectedRoute>
            <Dashboard />
          </ProtectedRoute>
        }
      />

      {/* 3. Default Redirect (Catch-all) */}
      {/* If they go to "/" or a broken link, try sending them to dashboard */}
      {/* The ProtectedRoute will then check if they need to login */}
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
}

export default App;