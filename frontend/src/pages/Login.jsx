import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import client from "../api/client";
import styles from "./Login.module.css";

function Login() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const res = await client.post("/auth/login", { email, password });
      localStorage.setItem("access_token", res.data.access_token);
      navigate("/dashboard");
    } catch (err) {
      setError(err.response?.data?.detail || "Login failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className={styles.page}>
      <form onSubmit={handleSubmit} className={styles.card}>
        <div className={styles.header}>
          <div className={styles.iconBox}>🎓</div>
          <p className={styles.title}>Log in to EduMind</p>
        </div>

        {error && <p className={styles.error}>{error}</p>}

        <input
          type="email"
          placeholder="name@school.edu"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
          className={styles.input}
        />
        <input
          type="password"
          placeholder="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          className={styles.input}
        />

        <button type="submit" disabled={loading} className={styles.button}>
          {loading ? "Logging in..." : "Log in"}
        </button>

        <p className={styles.footerText}>
          No account? <Link to="/signup" className={styles.link}>Sign up</Link>
        </p>
      </form>
    </div>
  );
}

export default Login;