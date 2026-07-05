import { createRouter, createWebHistory } from "vue-router";
import ArchitectureView from "./views/ArchitectureView.vue";
import AuthView from "./views/AuthView.vue";
import ChatView from "./views/ChatView.vue";
import EvaluationView from "./views/EvaluationView.vue";
import KnowledgeView from "./views/KnowledgeView.vue";
import PathView from "./views/PathView.vue";
import ProfileView from "./views/ProfileView.vue";
import ResourceView from "./views/ResourceView.vue";
import SystemStatusView from "./views/SystemStatusView.vue";

const routes = [
  { path: "/", redirect: "/architecture" },
  { path: "/auth", component: AuthView, meta: { title: "登录注册", requiresAuth: false } },
  { path: "/architecture", component: ArchitectureView, meta: { title: "多智能体架构", requiresAuth: true } },
  { path: "/profile", component: ProfileView, meta: { title: "对话式画像", requiresAuth: true } },
  { path: "/resources", component: ResourceView, meta: { title: "学习资源", requiresAuth: true } },
  { path: "/path", component: PathView, meta: { title: "学习路径", requiresAuth: true } },
  { path: "/chat", component: ChatView, meta: { title: "智能答疑", requiresAuth: true } },
  { path: "/evaluation", component: EvaluationView, meta: { title: "学习评估", requiresAuth: true } },
  { path: "/knowledge", component: KnowledgeView, meta: { title: "知识库管理", requiresAuth: true } },
  { path: "/system", component: SystemStatusView, meta: { title: "系统状态", requiresAuth: true } },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

router.beforeEach((to) => {
  const token = localStorage.getItem("token");
  if (to.meta.requiresAuth && !token) {
    return { path: "/auth", query: { redirect: to.fullPath } };
  }
  if (to.path === "/auth" && token) {
    return "/profile";
  }
  return true;
});

export default router;
