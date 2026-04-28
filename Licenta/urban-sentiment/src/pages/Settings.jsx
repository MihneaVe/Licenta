import { useState, useEffect } from 'react';
import { useAuth0 } from '@auth0/auth0-react';
import { useNavigate } from 'react-router-dom';

export default function Settings() {
  const { user, isAuthenticated, logout } = useAuth0();
  const navigate = useNavigate();
  // Theme state
  const [theme, setTheme] = useState(
    localStorage.getItem('theme') || 
    (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')
  );

  // Apply theme to document
  useEffect(() => {
    if (theme === 'dark') {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
    localStorage.setItem('theme', theme);
  }, [theme]);

  // Mock settings state
  const [settings, setSettings] = useState({
    pushNotifications: true,
    emailAlerts: false,
    weeklyDigest: true,
    publicProfile: false,
    autoRefresh: true
  });

  const handleToggle = (key) => {
    setSettings(prev => ({ ...prev, [key]: !prev[key] }));
  };

  return (
    <div className="flex flex-col gap-6 max-w-4xl mx-auto w-full pb-8">
      
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold text-slate-900 dark:text-white">Settings</h2>
        <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">Manage your dashboard preferences and account settings.</p>
      </div>

      {/* Account Section */}
      <div className="bg-white dark:bg-slate-900 rounded-xl p-6 shadow-sm border border-slate-100 dark:border-slate-800 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div className="flex items-center gap-4">
           <div className="w-16 h-16 rounded-full bg-slate-200 dark:bg-slate-700 bg-cover bg-center shrink-0 border border-slate-200 dark:border-slate-700" style={{ backgroundImage: `url('${user?.picture || 'https://via.placeholder.com/150'}')` }}></div>
           <div>
             <h3 className="font-bold text-lg text-slate-900 dark:text-white">{isAuthenticated ? user?.name : 'Alex Rivera'}</h3>
             <p className="text-sm text-slate-500 dark:text-slate-400">{isAuthenticated ? user?.email : 'alex.rivera@citygov.org'}</p>
             <p className="text-xs font-semibold text-primary mt-1 uppercase tracking-wider">
               {isAuthenticated 
                  ? (user?.['https://urban-sentiment.app/roles']?.[0] || 'USER') 
                  : 'SYSTEM ADMINISTRATOR'}
             </p>
           </div>
        </div>
        <button 
          onClick={() => navigate('/dashboard/profile/edit')}
          className="px-4 py-2 border border-slate-200 dark:border-slate-700 rounded-lg text-sm font-semibold text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors"
        >
          Edit Profile
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 relative">
        {/* Appearance Settings */}
        <div className="bg-white dark:bg-slate-900 rounded-xl shadow-sm border border-slate-100 dark:border-slate-800 overflow-hidden flex flex-col">
          <div className="p-4 border-b border-slate-100 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/30">
            <h3 className="font-bold text-slate-900 dark:text-white flex items-center gap-2">
              <span className="material-symbols-outlined text-primary">palette</span>
              Appearance
            </h3>
          </div>
          <div className="p-6 flex-1">
            <p className="text-sm text-slate-500 dark:text-slate-400 mb-4">Choose your preferred theme for the dashboard.</p>
            
            <div className="grid grid-cols-2 gap-4">
              {/* Light Mode Button */}
              <button 
                onClick={() => setTheme('light')}
                className={`flex flex-col items-center justify-center p-4 rounded-xl border-2 transition-all ${theme === 'light' ? 'border-primary bg-primary/5' : 'border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 hover:border-slate-300 dark:hover:border-slate-600'}`}
              >
                <div className="w-12 h-8 bg-white border border-slate-200 rounded-md shadow-sm mb-3 overflow-hidden flex">
                  <div className="w-1/3 h-full bg-slate-100 border-r border-slate-200"></div>
                  <div className="flex-1 h-full p-1 space-y-1">
                     <div className="w-full h-1.5 bg-slate-200 rounded-full"></div>
                     <div className="w-2/3 h-1.5 bg-slate-200 rounded-full"></div>
                  </div>
                </div>
                <span className={`text-sm font-semibold ${theme === 'light' ? 'text-primary' : 'text-slate-600 dark:text-slate-300'}`}>Light</span>
              </button>

              {/* Dark Mode Button */}
              <button 
                onClick={() => setTheme('dark')}
                className={`flex flex-col items-center justify-center p-4 rounded-xl border-2 transition-all ${theme === 'dark' ? 'border-primary bg-primary/5' : 'border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 hover:border-slate-300 dark:hover:border-slate-600'}`}
              >
                <div className="w-12 h-8 bg-slate-900 border border-slate-700 rounded-md shadow-sm mb-3 overflow-hidden flex">
                   <div className="w-1/3 h-full bg-slate-800 border-r border-slate-700"></div>
                   <div className="flex-1 h-full p-1 space-y-1">
                     <div className="w-full h-1.5 bg-slate-700 rounded-full"></div>
                     <div className="w-2/3 h-1.5 bg-slate-700 rounded-full"></div>
                  </div>
                </div>
                <span className={`text-sm font-semibold ${theme === 'dark' ? 'text-primary' : 'text-slate-600 dark:text-slate-300'}`}>Dark</span>
              </button>
            </div>
          </div>
        </div>

        {/* Notifications & Preferences */}
        <div className="bg-white dark:bg-slate-900 rounded-xl shadow-sm border border-slate-100 dark:border-slate-800 overflow-hidden flex flex-col">
          <div className="p-4 border-b border-slate-100 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/30">
            <h3 className="font-bold text-slate-900 dark:text-white flex items-center gap-2">
              <span className="material-symbols-outlined text-emerald-500">notifications_active</span>
              Notifications & Alerts
            </h3>
          </div>
          <div className="p-0 flex-1 divide-y divide-slate-100 dark:divide-slate-800">
            
            {/* Setting Item */}
            <div className="flex items-center justify-between p-4 px-6 hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors">
              <div>
                <p className="text-sm font-semibold text-slate-900 dark:text-white">Push Notifications</p>
                <p className="text-xs text-slate-500 dark:text-slate-400">Receive real-time alerts for critical sentiment drops.</p>
              </div>
              <button 
                onClick={() => handleToggle('pushNotifications')}
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 dark:focus:ring-offset-slate-900 ${settings.pushNotifications ? 'bg-primary' : 'bg-slate-300 dark:bg-slate-600'}`}
              >
                <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${settings.pushNotifications ? 'translate-x-6' : 'translate-x-1'}`} />
              </button>
            </div>

            {/* Setting Item */}
            <div className="flex items-center justify-between p-4 px-6 hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors">
              <div>
                <p className="text-sm font-semibold text-slate-900 dark:text-white">Email Alerts</p>
                <p className="text-xs text-slate-500 dark:text-slate-400">Get daily summaries delivered to your inbox.</p>
              </div>
              <button 
                 onClick={() => handleToggle('emailAlerts')}
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 dark:focus:ring-offset-slate-900 ${settings.emailAlerts ? 'bg-primary' : 'bg-slate-300 dark:bg-slate-600'}`}
              >
                <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${settings.emailAlerts ? 'translate-x-6' : 'translate-x-1'}`} />
              </button>
            </div>
            
            {/* Setting Item */}
            <div className="flex items-center justify-between p-4 px-6 hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors">
              <div>
                <p className="text-sm font-semibold text-slate-900 dark:text-white">Live Feed Auto-Refresh</p>
                <p className="text-xs text-slate-500 dark:text-slate-400">Automatically pull new incoming feedback.</p>
              </div>
              <button 
                 onClick={() => handleToggle('autoRefresh')}
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 dark:focus:ring-offset-slate-900 ${settings.autoRefresh ? 'bg-primary' : 'bg-slate-300 dark:bg-slate-600'}`}
              >
                <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${settings.autoRefresh ? 'translate-x-6' : 'translate-x-1'}`} />
              </button>
            </div>

          </div>
        </div>
      </div>

       {/* Danger Zone */}
       <div className="bg-white dark:bg-slate-900 rounded-xl p-6 shadow-sm border border-red-200 dark:border-red-900/50 mt-4">
        <h3 className="font-bold text-red-600 dark:text-red-400 mb-2">Danger Zone</h3>
        <p className="text-sm text-slate-500 dark:text-slate-400 mb-4">Permanent actions regarding your account and data.</p>
        <div className="flex gap-4">
          <button className="px-4 py-2 border border-red-200 dark:border-red-900/50 hover:bg-red-50 dark:hover:bg-red-900/20 text-red-600 dark:text-red-400 rounded-lg text-sm font-semibold transition-colors">
            Clear Local Cache
          </button>
          <button 
             onClick={() => {
               if(isAuthenticated) {
                 logout({ logoutParams: { returnTo: window.location.origin } });
               } else {
                 alert("You are not logged in.");
               }
             }}
             className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg text-sm font-semibold transition-colors"
          >
            Sign Out
          </button>
        </div>
      </div>

    </div>
  );
}
