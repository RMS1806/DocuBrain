/**
 * Shared API configuration.
 *
 * In production (Vercel):  Set VITE_API_URL in the Vercel dashboard.
 * In development:          Falls back to http://localhost:8000
 *
 * IMPORTANT — the value must NOT end with a trailing slash.
 *   ✅  https://docubrain-zifb.onrender.com
 *   ❌  https://docubrain-zifb.onrender.com/
 */
export const API_BASE = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/+$/, '');
