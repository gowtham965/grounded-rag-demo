// Demo host for the panel. In your app, the token and customer come from your login session,
// so the customer picker and token box below don't exist there.
import { useCallback, useState } from "react";
import { createRoot } from "react-dom/client";
import { AssistantPanel } from "./AssistantPanel.jsx";
import "./demo.css";

const stored = (k, d) => {
  try { return localStorage.getItem(k) ?? d; } catch { return d; }
};

function DemoApp() {
  const [customer, setCustomer] = useState("acme");
  const [token, setToken] = useState(() => stored("token", ""));
  const headers = useCallback(() => ({ Authorization: `Bearer ${token}` }), [token]);

  const saveToken = (v) => {
    setToken(v);
    try { localStorage.setItem("token", v); } catch {}
  };

  return (
    <div className="demo">
      <div className="demo-bar">
        <span className="demo-brand">YourApp</span>
        <span className="demo-note">demo login:</span>
        <select value={customer} onChange={(e) => setCustomer(e.target.value)} aria-label="Customer">
          <option value="acme">Acme Logistics</option>
          <option value="globex">Globex Corp</option>
        </select>
        <input value={token} onChange={(e) => saveToken(e.target.value)} placeholder="API token" aria-label="API token" />
      </div>
      {/* key: switching customer starts a fresh conversation */}
      <AssistantPanel key={customer} endpoint="/chat" headers={headers} customerId={customer} />
    </div>
  );
}

createRoot(document.getElementById("root")).render(<DemoApp />);
