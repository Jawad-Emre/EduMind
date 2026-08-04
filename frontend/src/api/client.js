import axios from "axios";

const client = axios.create({
  // This tells Vite to use the Railway URL in production, but keep localhost for your own computer!
  baseURL: import.meta.env.VITE_API_URL || "http://127.0.0.1:8000",
});

client.interceptors.request.use((config) => {
  const token = localStorage.getItem("access_token");

  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }

  return config;
});

export default client;
