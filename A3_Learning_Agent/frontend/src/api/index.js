import axios from "axios";
import router from "../router";

export const ACTIVE_PROFILE_SESSION_KEY = "a3_active_profile_session_id";

export function activeProfileSessionId() {
  return localStorage.getItem(ACTIVE_PROFILE_SESSION_KEY) || "";
}

export function setActiveProfileSessionId(id) {
  if (id) {
    localStorage.setItem(ACTIVE_PROFILE_SESSION_KEY, String(id));
  } else {
    localStorage.removeItem(ACTIVE_PROFILE_SESSION_KEY);
  }
}

function withProfileSession(data = {}) {
  const sessionId = activeProfileSessionId();
  return sessionId ? { ...data, profile_session_id: Number(sessionId) } : data;
}

function profileSessionParams(params = {}) {
  const sessionId = activeProfileSessionId();
  return sessionId ? { ...params, profile_session_id: sessionId } : params;
}

function withExplicitProfileSession(data = {}, explicitSessionId = "") {
  if (explicitSessionId) {
    return { ...data, profile_session_id: Number(explicitSessionId) };
  }
  return withProfileSession(data);
}

function explicitProfileSessionParams(params = {}, explicitSessionId = "") {
  if (explicitSessionId) {
    return { ...params, profile_session_id: String(explicitSessionId) };
  }
  return profileSessionParams(params);
}

const http = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "http://localhost:5000/api",
  timeout: 360000,
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
      localStorage.removeItem(ACTIVE_PROFILE_SESSION_KEY);
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
  userInfo: () => http.get("/profile/user-info"),
  saveUserInfo: (data) => http.post("/profile/user-info", data),
  sessions: () => http.get("/profile/sessions"),
  createSession: (data = {}) => http.post("/profile/sessions", data),
  activateSession: (id) => http.post(`/profile/sessions/${id}/activate`),
  renameSession: (id, title) => http.patch(`/profile/sessions/${id}`, { title }),
  resetSession: (id) => http.post(`/profile/sessions/${id}/reset`),
  deleteSession: (id) => http.delete(`/profile/sessions/${id}`),
  chat: (data) => http.post("/profile/chat", withProfileSession(data)),
  chatProfileSync: (data) => http.post("/profile/chat/profile-sync", withProfileSession(data)),
  chatEnhance: (data) => http.post("/profile/chat/enhance", withProfileSession(data)),
  create: (data) => http.post("/profile/create", withProfileSession(data)),
  update: (data) => http.post("/profile/update", withProfileSession(data)),
  get: (profileSessionId = "") => http.get("/profile/", { params: explicitProfileSessionParams({}, profileSessionId) }),
  getAggregate: () => http.get("/profile/aggregate", { params: profileSessionParams() }),
  getConversation: () => http.get("/profile/conversation", { params: profileSessionParams() }),
  saveConversation: (data) => http.post("/profile/conversation", withProfileSession(data)),
  clearConversation: () => http.delete("/profile/conversation", { params: profileSessionParams() }),
};

export const resourceApi = {
  generate: (data = {}, profileSessionId = "") => http.post("/resource/generate", withExplicitProfileSession(data, profileSessionId)),
  list: (profileSessionId = "") => http.get("/resource/", { params: explicitProfileSessionParams({}, profileSessionId) }),
};

export const pathApi = {
  generate: (data = {}, profileSessionId = "") => http.post("/path/generate", withExplicitProfileSession(data, profileSessionId)),
  list: (profileSessionId = "") => http.get("/path/", { params: explicitProfileSessionParams({}, profileSessionId) }),
  integrated: (profileSessionId = "") => http.get("/path/integrated", { params: explicitProfileSessionParams({}, profileSessionId) }),
  stageProgress: (profileSessionId = "") => http.get("/path/stage-progress", { params: explicitProfileSessionParams({}, profileSessionId) }),
  saveStageProgress: (data = {}, profileSessionId = "") => http.post("/path/stage-progress", withExplicitProfileSession(data, profileSessionId)),
};

export const chatApi = {
  answer: (data) => http.post("/chat/answer", withProfileSession(data)),
  history: () => http.get("/chat/history", { params: profileSessionParams() }),
  saveHistory: (data) => http.post("/chat/history", withProfileSession(data)),
  clearHistory: () => http.delete("/chat/history", { params: profileSessionParams() }),
};

export const knowledgeApi = {
  importBookJson: (data) => {
    if (typeof FormData !== "undefined" && data instanceof FormData) {
      return http.post("/knowledge/import-book-json", data, {
        headers: { "Content-Type": "multipart/form-data" },
      });
    }
    return http.post("/knowledge/import-book-json", data);
  },
  status: () => http.get("/knowledge/status"),
  documents: () => http.get("/knowledge/documents"),
  rebuild: (data = { force: true }) => http.post("/knowledge/rebuild", data),
  search: (data) => http.post("/knowledge/search", data),
  tree: () => http.get("/knowledge/tree"),
  section: (nodeId, params = { include_children: true }) =>
    http.get(`/knowledge/section/${encodeURIComponent(nodeId)}`, { params }),
  chapterIndex: () => http.get("/knowledge/chapter-index"),
  chapterBrowser: () => http.get("/knowledge/chapter-browser"),
  knowledgeTree: () => http.get("/knowledge/knowledge-tree"),
  knowledgeGraph: () => http.get("/knowledge/knowledge-graph"),
};

export const evaluationApi = {
  bankStatus: () => http.get("/evaluation/bank-status"),
  knowledgePoints: () => http.get("/evaluation/knowledge-points"),
  rebuildBank: (data = { force: true }) => http.post("/evaluation/rebuild-bank", data),
  questions: (data = {}) => http.post("/evaluation/questions", withProfileSession(data)),
  submit: (data) => http.post("/evaluation/submit", withProfileSession(data)),
  summary: () => http.get("/evaluation/summary"),
  wrongBook: () => http.get("/evaluation/wrong-book"),
  addWrongBook: (data) => http.post("/evaluation/wrong-book", withProfileSession(data)),
  submitWrongBook: (id, data) => http.post(`/evaluation/wrong-book/${id}/submit`, withProfileSession(data)),
  deleteWrongBook: (id) => http.delete(`/evaluation/wrong-book/${id}`),
  event: (data) => http.post("/evaluation/event", data),
};

export const systemApi = {
  status: () => http.get("/system/status"),
  testAi: (data = {}) => http.post("/system/test-ai", data),
};

export default http;
