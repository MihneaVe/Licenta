import { Link, useLocation } from "react-router-dom";
import { useAuth0 } from '@auth0/auth0-react';

// Django serves the manual paste / ingestion form. The React app and
// Django are deployed at different ports, so we open the form in a new
// tab to keep the dashboard SPA mounted in the background.
const DJANGO_URL = import.meta.env.VITE_DJANGO_URL || 'http://localhost:8000';
const INGEST_URL = `${DJANGO_URL}/ingest/`;

export default function Sidebar() {
  const location = useLocation();
  const { isAuthenticated, loginWithRedirect, logout, user, isLoading } = useAuth0();

  // Helper function to determine if a link is active
  const isActive = (path) => location.pathname === path;

  return (
    <aside className="fixed inset-y-0 left-0 w-64 border-r border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 z-50">
      <div className="h-full flex flex-col p-4">
        
        {/* Logo Area */}
        <Link to="/dashboard" className="flex items-center gap-3 px-2 mb-8">
          <div className="w-8 h-8 bg-primary/20 border border-primary/30 rounded-lg flex items-center justify-center">
            <span className="material-symbols-outlined text-primary text-[18px]">satellite_alt</span>
          </div>
          <span className="font-bold text-lg text-slate-900 dark:text-white tracking-tight">UrbanPulse</span>
        </Link>

        {/* Navigation Links */}
        <nav className="flex-1 space-y-1">
          <Link 
            to="/dashboard" 
            className={`flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-semibold transition-colors ${
              isActive('/dashboard') || isActive('/') 
                ? 'bg-primary/10 text-primary dark:bg-primary/20 dark:text-blue-400' 
                : 'text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800/50 hover:text-slate-900 dark:hover:text-white'
            }`}
          >
            <span className="material-symbols-outlined text-[20px]">dashboard</span>
            Overview
          </Link>
          <Link 
            to="/dashboard/heatmap" 
            className={`flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-semibold transition-colors ${
              isActive('/dashboard/heatmap') 
                ? 'bg-primary/10 text-primary dark:bg-primary/20 dark:text-blue-400' 
                : 'text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800/50 hover:text-slate-900 dark:hover:text-white'
            }`}
          >
            <span className="material-symbols-outlined text-[20px]">map</span>
            City Heatmap
          </Link>
          <Link 
            to="/dashboard/topics" 
            className={`flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-semibold transition-colors ${
              isActive('/dashboard/topics') 
                ? 'bg-primary/10 text-primary dark:bg-primary/20 dark:text-blue-400' 
                : 'text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800/50 hover:text-slate-900 dark:hover:text-white'
            }`}
          >
            <span className="material-symbols-outlined text-[20px]">tag</span>
            Trending Topics
          </Link>
          <Link
            to="/dashboard/live-feed"
            className={`flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-semibold transition-colors ${
              isActive('/dashboard/live-feed')
                ? 'bg-primary/10 text-primary dark:bg-primary/20 dark:text-blue-400'
                : 'text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800/50 hover:text-slate-900 dark:hover:text-white'
            }`}
          >
            <span className="material-symbols-outlined text-[20px]">feed</span>
            Live Feedback
          </Link>

          {/* Add Post — opens Django's manual paste form in a new tab.
              The React app stays mounted and picks up the new row on
              the next data refresh / page reload. */}
          <a
            href={INGEST_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="mt-3 flex items-center justify-center gap-2 px-3 py-2.5 rounded-xl text-sm font-semibold bg-primary text-white shadow-sm hover:bg-blue-600 transition-colors"
          >
            <span className="material-symbols-outlined text-[20px]">add_circle</span>
            Add Post
          </a>
        </nav>
        <div className="pt-4 mt-4 border-t border-slate-200 dark:border-slate-800">
          <Link 
            to="/dashboard/settings" 
            className={`flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-semibold transition-colors mt-8 ${
              isActive('/dashboard/settings') 
                ? 'bg-primary/10 text-primary dark:bg-primary/20 dark:text-blue-400' 
                : 'text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800/50 hover:text-slate-900 dark:hover:text-white'
            }`}
          >
            <span className="material-symbols-outlined text-[20px]">settings</span>
            Settings
          </Link>
          <div className="flex items-center gap-3 p-2 mt-4">
            <div className="w-10 h-10 rounded-full bg-slate-200 dark:bg-slate-700 bg-cover bg-center" style={{ backgroundImage: `url('${user?.picture || 'https://via.placeholder.com/150'}')` }}></div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-semibold truncate">{isAuthenticated ? user?.name : 'Alex Rivera'}</p>
              <p className="text-xs text-slate-500 truncate capitalize">
                {isAuthenticated 
                  ? (user?.['https://urban-sentiment.app/roles']?.[0] || 'User') 
                  : 'Admin Access'}
              </p>
            </div>
          </div>
        </div>
      </div>
    </aside>
  );
}
