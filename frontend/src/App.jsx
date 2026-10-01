import { Routes, Route, Navigate } from "react-router-dom";
import ParentChat from "./pages/ParentChat.jsx";
import OperatorDashboard from "./pages/OperatorDashboard.jsx";
import { USE_MOCKS } from "./api.js";

export default function App() {
  return (
    <>
      {USE_MOCKS && <div className="mock-banner">Mock API — dev only</div>}
      <Routes>
        <Route path="/" element={<ParentChat />} />
        <Route path="/operator" element={<OperatorDashboard />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </>
  );
}
