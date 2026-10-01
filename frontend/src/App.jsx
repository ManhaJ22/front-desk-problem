import { Routes, Route, Navigate, NavLink } from "react-router-dom";
import ParentChat from "./pages/ParentChat.jsx";
import OperatorDashboard from "./pages/OperatorDashboard.jsx";
import { USE_MOCKS } from "./api.js";

export default function App() {
  return (
    <>
      {USE_MOCKS && <div className="mock-banner">Mock API — dev only</div>}
      {/* Demo navigation between the two perspectives of the same app (decision log #26). */}
      <nav className="view-switch" aria-label="Switch view">
        <NavLink to="/" end>
          Parent chat
        </NavLink>
        <NavLink to="/operator">Staff dashboard</NavLink>
      </nav>
      <Routes>
        <Route path="/" element={<ParentChat />} />
        <Route path="/operator" element={<OperatorDashboard />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </>
  );
}
