import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { api } from "../api";

const inputClass =
  "w-full bg-white/[0.02] border border-white/[0.08] rounded-control px-3.5 py-3 text-[14px] text-mist placeholder:text-ash focus:outline-none focus:border-mist transition-colors";

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [role, setRole] = useState("OPERATOR");
  const [mode, setMode] = useState("login"); // "login" | "signup"
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      if (mode === "signup") {
        await api.signup(email, password, name, role);
      }
      await login(email, password);
      navigate("/");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-void">
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-sm bg-carbon rounded-card p-8"
        style={{ boxShadow: "rgb(35, 37, 42) 0px 0px 0px 1px inset" }}
      >
        <h1 className="text-[20px] font-[510] text-paper mb-1 tracking-[-0.012em]">
          Lathe Inspector
        </h1>
        <p className="text-[13px] text-fog mb-6">
          {mode === "login" ? "Sign in to view inspections" : "Create an account"}
        </p>

        {mode === "signup" && (
          <div className="mb-3">
            <label className="block text-[13px] text-fog mb-1.5">Name</label>
            <input className={inputClass} value={name} onChange={(e) => setName(e.target.value)} required />
          </div>
        )}

        <div className="mb-3">
          <label className="block text-[13px] text-fog mb-1.5">Email</label>
          <input
            type="email"
            className={inputClass}
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </div>

        <div className="mb-3">
          <label className="block text-[13px] text-fog mb-1.5">Password</label>
          <input
            type="password"
            className={inputClass}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </div>

        {mode === "signup" && (
          <div className="mb-4">
            <label className="block text-[13px] text-fog mb-1.5">Role</label>
            <select className={inputClass} value={role} onChange={(e) => setRole(e.target.value)}>
              <option value="OPERATOR">Operator</option>
              <option value="MANAGER">Manager</option>
            </select>
          </div>
        )}

        {error && <p className="text-[13px] text-coral-red mb-4">{error}</p>}

        <button
          type="submit"
          disabled={loading}
          className="w-full bg-acid text-void rounded-control py-2.5 text-[14px] font-[510] tracking-[-0.011em] hover:brightness-95 disabled:opacity-50 transition-[filter] mt-2"
        >
          {loading ? "Please wait..." : mode === "login" ? "Sign in" : "Sign up"}
        </button>

        <button
          type="button"
          onClick={() => setMode(mode === "login" ? "signup" : "login")}
          className="w-full text-[13px] text-fog hover:text-mist mt-3 transition-colors"
        >
          {mode === "login" ? "Need an account? Sign up" : "Already have an account? Sign in"}
        </button>
      </form>
    </div>
  );
}
