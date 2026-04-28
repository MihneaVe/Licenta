import { useAuth0 } from '@auth0/auth0-react';

export default function LandingPage() {
  const { loginWithRedirect } = useAuth0();

  return (
    <div className="min-h-screen bg-slate-900 text-white font-display overflow-hidden relative">
      
      {/* Abstract Background Elements (Glassmorphism blobs) */}
      <div className="absolute top-[-20%] left-[-10%] w-[500px] h-[500px] bg-primary/20 rounded-full blur-[120px] pointer-events-none"></div>
      <div className="absolute bottom-[-20%] right-[-10%] w-[600px] h-[600px] bg-rose-500/10 rounded-full blur-[150px] pointer-events-none"></div>

      {/* Navigation Bar */}
      <nav className="relative z-10 max-w-7xl mx-auto px-6 py-6 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-primary/20 border border-primary/30 rounded-xl flex items-center justify-center">
            <span className="material-symbols-outlined text-primary text-xl">satellite_alt</span>
          </div>
          <span className="text-xl font-bold tracking-tight">UrbanPulse</span>
        </div>
        
        <div className="flex items-center gap-4">
          <button 
            onClick={() => loginWithRedirect()}
            className="text-slate-300 hover:text-white font-semibold text-sm transition-colors hidden sm:block"
          >
            Log In
          </button>
          <button 
            onClick={() => loginWithRedirect({ authorizationParams: { screen_hint: 'signup' } })}
            className="px-5 py-2.5 bg-primary hover:bg-blue-600 text-white font-bold text-sm rounded-xl transition-colors shadow-[0_0_20px_rgba(59,130,246,0.3)] hover:shadow-[0_0_30px_rgba(59,130,246,0.5)]"
          >
            Create Account
          </button>
        </div>
      </nav>

      {/* Hero Section */}
      <main className="relative z-10 max-w-7xl mx-auto px-6 pt-20 pb-32 flex flex-col lg:flex-row items-center gap-16 min-h-[calc(100vh-88px)]">
        
        {/* Left Text Content */}
        <div className="flex-1 text-center lg:text-left pt-10 lg:pt-0">
          
          <h1 className="text-5xl md:text-6xl lg:text-7xl font-extrabold tracking-tight leading-[1.1] mb-6 drop-shadow-sm text-balance">
            Decode your city's <span className="text-transparent bg-clip-text bg-gradient-to-r from-primary to-emerald-400">sentiment</span> in real-time.
          </h1>
          
          <p className="text-lg md:text-xl text-slate-400 mb-10 max-w-2xl mx-auto lg:mx-0 text-balance leading-relaxed">
            The next-generation intelligence platform for urban planners and city officials. Monitor public reaction, visualize infrastructure feedback, and manage your district's digital heartbeat.
          </p>
          
          <div className="flex flex-col sm:flex-row items-center gap-4 justify-center lg:justify-start">
            <button 
               onClick={() => loginWithRedirect({ authorizationParams: { screen_hint: 'signup' } })}
              className="w-full sm:w-auto px-8 py-4 bg-primary hover:bg-blue-600 text-white font-bold text-base rounded-2xl transition-all shadow-[0_4px_25px_rgba(59,130,246,0.4)] hover:shadow-[0_8px_35px_rgba(59,130,246,0.6)] hover:-translate-y-1 flex items-center justify-center gap-2"
            >
              Access Dashboard
              <span className="material-symbols-outlined text-[20px]">arrow_forward</span>
            </button>
          </div>
        </div>

        {/* Right Abstract Visuals */}
        <div className="flex-1 w-full max-w-2xl lg:max-w-none relative perspective-[1000px]">
          
          <div className="relative w-full aspect-square md:aspect-[4/3] rounded-3xl bg-slate-800/30 border border-slate-700/50 backdrop-blur-xl shadow-2xl p-6 overflow-hidden transform rotate-y-[-5deg] rotate-x-[5deg] hover:rotate-y-[0deg] hover:rotate-x-[0deg] transition-transform duration-700 ease-out group">
             {/* Mock App Chrome */}
             <div className="w-full h-10 border-b border-slate-700/50 flex items-center gap-2 px-4 absolute top-0 left-0 w-full bg-slate-900/50 backdrop-blur-md z-20">
               <div className="flex gap-1.5">
                 <div className="w-3 h-3 rounded-full bg-rose-500/80"></div>
                 <div className="w-3 h-3 rounded-full bg-amber-500/80"></div>
                 <div className="w-3 h-3 rounded-full bg-emerald-500/80"></div>
               </div>
               <div className="mx-auto w-1/3 h-4 bg-slate-800 rounded-md"></div>
             </div>
             
             {/* Grid Backdrop inside card */}
             <div className="absolute inset-x-0 bottom-0 top-10 flex">
                <div className="w-1/4 h-full border-r border-slate-700/30 bg-slate-800/10 hidden sm:block"></div>
                <div className="flex-1 h-full p-4 md:p-8 flex flex-col gap-4">
                  {/* Mock Heatmap */}
                  <div className="flex-1 rounded-2xl bg-gradient-to-tr from-slate-800 to-slate-700 overflow-hidden relative">
                    <div className="absolute w-32 h-32 bg-emerald-500/30 blur-2xl top-4 left-4 rounded-full"></div>
                    <div className="absolute w-40 h-40 bg-rose-500/20 blur-2xl bottom-10 right-10 rounded-full"></div>
                    <div className="absolute w-20 h-20 bg-amber-500/30 blur-xl top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 rounded-full"></div>
                  </div>
                  {/* Mock Stats Cards */}
                  <div className="h-24 flex gap-4">
                    <div className="flex-1 rounded-2xl bg-slate-800/60 border border-slate-700/50 p-4 flex flex-col justify-between group-hover:bg-slate-700/50 transition-colors">
                      <div className="w-6 h-6 rounded bg-primary/20 mb-2"></div>
                      <div className="w-1/2 h-3 bg-slate-600 rounded"></div>
                    </div>
                    <div className="flex-1 rounded-2xl bg-slate-800/60 border border-slate-700/50 p-4 flex flex-col justify-between hidden sm:flex group-hover:bg-slate-700/50 transition-colors">
                       <div className="w-6 h-6 rounded bg-emerald-500/20 mb-2"></div>
                       <div className="w-2/3 h-3 bg-slate-600 rounded"></div>
                    </div>
                  </div>
                </div>
             </div>
             
             {/* Decorative glow behind UI block */}
             <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[120%] h-[120%] bg-white/5 opacity-0 group-hover:opacity-100 transition-opacity duration-700 pointer-events-none mix-blend-overlay"></div>
          </div>
          
        </div>
      </main>
      
    </div>
  );
}
