import { useAuth } from "./AuthContext.jsx";
import AuthPage from "./components/AuthPage.jsx";
import Workspace from "./components/Workspace.jsx";

export default function App() {
  const { user, checking } = useAuth();

  if (checking) return <div className="center-screen muted">Loading…</div>;
  return user ? <Workspace /> : <AuthPage />;
}
