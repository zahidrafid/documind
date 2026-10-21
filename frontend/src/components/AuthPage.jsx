import { useState } from "react";
import { useAuth } from "../AuthContext.jsx";

export default function AuthPage() {
  const { login, register, loginAsDemo } = useAuth();
  const [mode, setMode] = useState("login");
  const [form, setForm] = useState({ username: "", email: "", password: "" });
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const isLogin = mode === "login";

  function update(event) {
    setForm({ ...form, [event.target.name]: event.target.value });
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      if (isLogin) {
        await login(form.username, form.password);
      } else {
        await register(form.username, form.email, form.password);
      }
    } catch (err) {
      setError(err.message);
      setSubmitting(false);
    }
  }

  async function handleDemo() {
    setError("");
    setSubmitting(true);
    try {
      await loginAsDemo();
    } catch (err) {
      setError(err.message);
      setSubmitting(false);
    }
  }

  function switchMode() {
    setMode(isLogin ? "register" : "login");
    setError("");
  }

  return (
    <div className="center-screen">
      <div className="auth-card">
        <h1 className="logo">DocuMind</h1>
        <p className="muted">Answers from your documents, with page-level citations.</p>

        <form onSubmit={handleSubmit} className="auth-form">
          <label>
            Username
            <input name="username" value={form.username} onChange={update} required autoFocus />
          </label>

          {!isLogin && (
            <label>
              Email
              <input name="email" type="email" value={form.email} onChange={update} />
            </label>
          )}

          <label>
            Password
            <input
              name="password"
              type="password"
              value={form.password}
              onChange={update}
              required
              minLength={isLogin ? undefined : 8}
            />
          </label>

          {error && <p className="error">{error}</p>}

          <button className="btn-primary" type="submit" disabled={submitting}>
            {submitting ? "Please wait…" : isLogin ? "Log in" : "Create account"}
          </button>
        </form>

        <div className="demo-box">
          <button className="btn-secondary demo-btn" onClick={handleDemo} disabled={submitting}>
            Try the demo account
          </button>
          <p className="muted small">No sign-up needed. Ask questions about sample documents.</p>
        </div>

        <p className="muted small">
          {isLogin ? "New here?" : "Already have an account?"}{" "}
          <button className="btn-link" onClick={switchMode}>
            {isLogin ? "Create an account" : "Log in"}
          </button>
        </p>
      </div>
    </div>
  );
}
