import { useState } from 'react';
import { useAuth0 } from '@auth0/auth0-react';
import { useNavigate } from 'react-router-dom';

export default function EditProfile() {
  const { user, isAuthenticated } = useAuth0();
  const navigate = useNavigate();

  // Initialize state with Auth0 user data or fallbacks
  const [formData, setFormData] = useState({
    name: user?.name || 'Alex Rivera',
    description: 'System Administrator managing the UrbanPulse dashboard for the central district.',
    publicProfile: true
  });

  const [isSaving, setIsSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value
    }));
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    setIsSaving(true);
    
    // Simulate an API call to save profile data
    setTimeout(() => {
      setIsSaving(false);
      setSaveSuccess(true);
      
      // Auto dismiss success message
      setTimeout(() => setSaveSuccess(false), 3000);
    }, 1000);
  };

  const userRole = isAuthenticated 
    ? (user?.['https://urban-sentiment.app/roles']?.[0] || 'USER') 
    : 'SYSTEM ADMINISTRATOR';

  return (
    <div className="flex flex-col gap-6 max-w-2xl mx-auto w-full pb-8">
      
      {/* Header */}
      <div className="flex items-center gap-4">
        <button 
          onClick={() => navigate('/dashboard/settings')}
          className="w-10 h-10 rounded-full bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 flex items-center justify-center text-slate-500 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors shadow-sm"
        >
          <span className="material-symbols-outlined ml-[-2px]">arrow_back_ios_new</span>
        </button>
        <div>
          <h2 className="text-2xl font-bold text-slate-900 dark:text-white">Edit Profile</h2>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">Update your personal information and bio.</p>
        </div>
      </div>

      <div className="bg-white dark:bg-slate-900 rounded-xl shadow-sm border border-slate-100 dark:border-slate-800 overflow-hidden">
        
        {/* Profile Picture Banner Area */}
        <div className="h-32 bg-primary/10 border-b border-primary/20 relative">
          <div className="absolute -bottom-12 left-8 w-24 h-24 rounded-full bg-slate-200 dark:bg-slate-700 bg-cover bg-center border-4 border-white dark:border-slate-900 shadow-md flex items-center justify-center group cursor-pointer overflow-hidden" style={{ backgroundImage: `url('${user?.picture || 'https://via.placeholder.com/150'}')` }}>
            <div className="absolute inset-0 bg-black/40 hidden group-hover:flex items-center justify-center transition-all">
              <span className="material-symbols-outlined text-white">photo_camera</span>
            </div>
          </div>
        </div>
        
        <form onSubmit={handleSubmit} className="p-8 pt-16 flex flex-col gap-6">
          
          {/* Display Name */}
          <div className="flex flex-col gap-2">
            <label htmlFor="name" className="text-sm font-semibold text-slate-900 dark:text-white">Display Name</label>
            <input 
              type="text" 
              id="name"
              name="name"
              value={formData.name}
              onChange={handleChange}
              className="px-4 py-2.5 bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all"
              placeholder="Your full name"
              required
            />
          </div>

          {/* Email (Read Only - Managed by Auth0) */}
          <div className="flex flex-col gap-2">
            <label className="text-sm font-semibold text-slate-900 dark:text-white flex items-center gap-2">
              Email Address 
              <span className="material-symbols-outlined text-[16px] text-slate-400 cursor-help" title="Email is managed by your authentication provider">lock</span>
            </label>
            <input 
              type="email" 
              value={user?.email || 'alex.rivera@citygov.org'}
              disabled
              className="px-4 py-2.5 bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700/50 rounded-lg text-slate-500 dark:text-slate-400 cursor-not-allowed opacity-70"
            />
          </div>
          
          {/* Role (Read Only - Managed by Auth0) */}
          <div className="flex flex-col gap-2">
            <label className="text-sm font-semibold text-slate-900 dark:text-white flex items-center gap-2">
              Assigned Role 
              <span className="material-symbols-outlined text-[16px] text-slate-400 cursor-help" title="Roles are managed by the System Administrator">lock</span>
            </label>
            <div className="px-4 py-2.5 bg-primary/5 border border-primary/20 rounded-lg text-primary font-semibold text-sm uppercase tracking-wider">
               {userRole}
            </div>
          </div>

          {/* Bio / Description */}
          <div className="flex flex-col gap-2">
            <label htmlFor="description" className="text-sm font-semibold text-slate-900 dark:text-white">Bio & Description</label>
            <textarea 
              id="description"
              name="description"
              value={formData.description}
              onChange={handleChange}
              rows="4"
              className="px-4 py-3 bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all resize-none"
              placeholder="Tell us about your role in the city..."
            ></textarea>
            <p className="text-xs text-slate-500 text-right">Brief description for your dashboard profile.</p>
          </div>
          
          {/* Public Profile Toggle */}
           <div className="flex items-center justify-between py-2 border-t border-slate-100 dark:border-slate-800 mt-2">
            <div>
              <p className="text-sm font-semibold text-slate-900 dark:text-white">Public Profile</p>
              <p className="text-xs text-slate-500 dark:text-slate-400">Allow other agents to see your bio.</p>
            </div>
            <button 
              type="button"
              onClick={() => setFormData(prev => ({ ...prev, publicProfile: !prev.publicProfile }))}
              className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 dark:focus:ring-offset-slate-900 ${formData.publicProfile ? 'bg-primary' : 'bg-slate-300 dark:bg-slate-600'}`}
            >
              <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${formData.publicProfile ? 'translate-x-6' : 'translate-x-1'}`} />
            </button>
          </div>

          {/* Action Buttons */}
          <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-100 dark:border-slate-800">
            <button 
              type="button"
              onClick={() => navigate('/dashboard/settings')}
              className="px-5 py-2.5 rounded-lg text-sm font-semibold text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
            >
              Cancel
            </button>
            <button 
              type="submit"
              disabled={isSaving}
              className="px-6 py-2.5 bg-primary hover:bg-blue-600 text-white rounded-lg text-sm font-bold shadow-sm transition-all flex items-center justify-center min-w-[120px]"
            >
              {isSaving ? (
                <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
              ) : (
                'Save Changes'
              )}
            </button>
          </div>
          
          {/* Success Toast (Simple implementation for demo) */}
          {saveSuccess && (
            <div className="absolute top-4 right-4 bg-emerald-500 text-white px-4 py-2 rounded-lg shadow-lg flex items-center gap-2 animate-fade-in-down z-50">
              <span className="material-symbols-outlined text-[20px]">check_circle</span>
              <span className="text-sm font-bold">Profile updated successfully!</span>
            </div>
          )}

        </form>
      </div>
    </div>
  );
}
