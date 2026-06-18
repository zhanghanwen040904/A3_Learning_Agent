import axios from "axios";
import router from "../router";

const http = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "http://localhost:5000/api",
  timeout: 120000,
});

http.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

http.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const data = error.response?.data || error;
    if (error.response?.status === 401 || data?.code === 401) {
      localStorage.removeItem("token");
      localStorage.removeItem("user");
      if (router.currentRoute.value.path !== "/auth") {
        router.push("/auth");
      }
    }
    return Promise.resolve(data);
  }
);

export const authApi = {
  register: (data) => http.post("/auth/register", data),
  login: (data) => http.post("/auth/login", data),
};

export const profileApi = {
  create: (data) => http.post("/profile/create", data),
  update: (data) => http.post("/profile/update", data),
  get: () => http.get("/profile/"),
};

export const resourceApi = {
  generate: (data = {}) => http.post("/resource/generate", data),
  list: () => http.get("/resource/"),
};

export const pathApi = {
  generate: (data = {}) => http.post("/path/generate", data),
  list: () => http.get("/path/"),
};

export const chatApi = {
  answer: (data) => http.post("/chat/answer", data),
};

export default http;
