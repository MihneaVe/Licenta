import { Routes, Route, Navigate, useNavigate } from 'react-router-dom';
import { Auth0Provider, useAuth0 } from '@auth0/auth0-react';
import Layout from './components/Layout';
import LandingPage from './pages/LandingPage';
import Overview from './pages/Overview';
import Heatmap from './pages/Heatmap';
import Topics from './pages/Topics';
import LiveFeed from './pages/LiveFeed';
import Settings from './pages/Settings';
import EditProfile from './pages/EditProfile';

// A wrapper that connects Auth0's redirect logic to React Router's internal state
const Auth0ProviderWithNavigate = ({ children }) => {
  const navigate = useNavigate();

  const domain = import.meta.env.VITE_AUTH0_DOMAIN || '';
  const clientId = import.meta.env.VITE_AUTH0_CLIENT_ID || '';

  const onRedirectCallback = (appState) => {
    navigate(appState?.returnTo || '/dashboard', { replace: true });
  };

  return (
    <Auth0Provider
      domain={domain}
      clientId={clientId}
      authorizationParams={{
        redirect_uri: window.location.origin
      }}
      onRedirectCallback={onRedirectCallback}
    >
      {children}
    </Auth0Provider>
  );
};

// A wrapper to stall navigation until Auth0 consumes the callback URL
const AuthContainer = ({ children }) => {
  const { isLoading, error } = useAuth0();

  if (isLoading) {
    return (
      <div className="min-h-screen bg-slate-900 flex items-center justify-center">
        <div className="w-12 h-12 border-4 border-primary border-t-transparent rounded-full animate-spin"></div>
      </div>
    );
  }

  // If Auth0 throws an error during the code exchange, display it
  if (error) {
    return (
      <div className="min-h-screen bg-slate-900 flex items-center justify-center text-white p-8">
        <div className="bg-red-500/10 border border-red-500/50 p-6 rounded-xl max-w-lg">
          <h2 className="text-xl font-bold text-red-400 mb-2">Authentication Error</h2>
          <p className="text-slate-300 mb-4">{error.message}</p>
          <p className="text-sm text-slate-400">Please check your Auth0 Dashboard configuration (Allowed Callback URLs, Application Type, etc).</p>
        </div>
      </div>
    );
  }

  // Once loading is complete (and the token is secured), render the routes
  return children;
};

// A simple HOC to protect the dashboard routes
const ProtectedRoute = ({ children }) => {
  const { isAuthenticated } = useAuth0();

  // If not authenticated, bounce them back to the landing page
  if (!isAuthenticated) {
    return <Navigate to="/" replace />;
  }

  // Otherwise, render the dashboard
  return children;
};

function App() {
  return (
    <Auth0ProviderWithNavigate>
      <AuthContainer>
        <Routes>
          {/* Public Route */}
          <Route path="/" element={<LandingPage />} />

          {/* Protected Dashboard Routes */}
          <Route 
            path="/dashboard" 
            element={
              <ProtectedRoute>
                <Layout />
              </ProtectedRoute>
            }
          >
            {/* Default dashboard view */}
            <Route index element={<Overview />} />
            <Route path="heatmap" element={<Heatmap />} />
            <Route path="topics" element={<Topics />} />
            <Route path="live-feed" element={<LiveFeed />} />
            <Route path="settings" element={<Settings />} />
            <Route path="profile/edit" element={<EditProfile />} />
          </Route>

          {/* Catch-all redirect to public landing page */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthContainer>
    </Auth0ProviderWithNavigate>
  );
}

export default App;
