import NotificationsPage from "./pages/NotificationsPage";
import type { ReactNode } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { Layout, Loading } from "./components/ui";
import { useAuth } from "./lib/auth";
import AnalystApplication from "./pages/AnalystApplication";
import AnalystQueue from "./pages/AnalystQueue";
import ApplicationPage from "./pages/ApplicationPage";
import Dashboard from "./pages/Dashboard";
import LoginPage from "./pages/LoginPage";
import NewApplication from "./pages/NewApplication";

function Guard({ role, children }: { role: "CLIENT" | "ANALYST"; children: ReactNode }) {
  const { user, ready } = useAuth();
  if (!ready) return <div className="page"><Loading /></div>;
  if (!user) return <Navigate to="/login" replace />;
  if (user.role !== role) return <Navigate to={user.role === "ANALYST" ? "/analyst" : "/"} replace />;
  return <Layout>{children}</Layout>;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/" element={<Guard role="CLIENT"><Dashboard /></Guard>} />
      <Route path="/notifications" element={<Guard role="CLIENT"><NotificationsPage /></Guard>} />
      <Route path="/analyst/notifications" element={<Guard role="ANALYST"><NotificationsPage /></Guard>} />
      <Route path="/new" element={<Guard role="CLIENT"><NewApplication /></Guard>} />
      <Route path="/applications/:id" element={<Guard role="CLIENT"><ApplicationPage /></Guard>} />
      <Route path="/analyst" element={<Guard role="ANALYST"><AnalystQueue /></Guard>} />
      <Route path="/analyst/applications/:id" element={<Guard role="ANALYST"><AnalystApplication /></Guard>} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
