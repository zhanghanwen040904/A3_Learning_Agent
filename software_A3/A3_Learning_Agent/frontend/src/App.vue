<template>
  <el-config-provider>
    <el-container class="app-shell">
      <el-aside v-if="!isAuthPage" width="292px" class="sidebar">
        <div class="sidebar-topbar">
          <div class="brand-title">学习助手</div>
        </div>

        <el-button class="new-chat-button" :loading="creatingSession" @click="createNewChat">
          <el-icon><Plus /></el-icon>
          New chat
        </el-button>

        <div class="menu-group">
          <div class="menu-group-label">Workspace</div>
          <el-menu router :default-active="route.path" class="side-menu">
            <el-menu-item v-for="item in primaryNav" :key="item.path" :index="item.path">
              <el-icon><component :is="item.icon" /></el-icon>
              <span>{{ item.label }}</span>
            </el-menu-item>
          </el-menu>
        </div>

        <div class="menu-group menu-group-compact">
          <div class="menu-group-label">系统</div>
          <el-menu router :default-active="route.path" class="side-menu">
            <el-menu-item v-for="item in secondaryNav" :key="item.path" :index="item.path">
              <el-icon><component :is="item.icon" /></el-icon>
              <span>{{ item.label }}</span>
            </el-menu-item>
          </el-menu>
        </div>

        <div class="recent-section">
          <div class="recent-header">
            <div class="recent-heading">
              <span class="recent-title-main">Recents</span>
            </div>

            <el-button text circle class="refresh-button" @click="loadRecentSessions">
              <el-icon><RefreshRight /></el-icon>
            </el-button>
          </div>

          <div class="recent-list">
            <div
              v-for="item in recentSessions"
              :key="item.id"
              :class="['recent-item', { active: Number(item.id) === Number(activeSessionId) && route.path === '/profile' }]"
              role="button"
              tabindex="0"
              @click="openSession(item.id)"
              @keydown.enter.prevent="openSession(item.id)"
              @keydown.space.prevent="openSession(item.id)"
            >
              <span class="recent-title">{{ item.title || `会话 ${item.id}` }}</span>
              <el-dropdown
                trigger="click"
                placement="right-start"
                popper-class="recent-actions-popper"
                @command="(command) => handleSessionCommand(command, item)"
                @click.stop
              >
                <el-button text circle class="recent-more-button" title="更多操作" @click.stop>
                  <el-icon><MoreFilled /></el-icon>
                </el-button>
                <template #dropdown>
                  <el-dropdown-menu class="recent-actions-menu">
                    <el-dropdown-item command="rename" class="recent-action-item">
                      <el-icon><EditPen /></el-icon>
                      <span>重命名</span>
                    </el-dropdown-item>
                    <el-dropdown-item command="delete" class="recent-action-item danger">
                      <el-icon><Delete /></el-icon>
                      <span>删除</span>
                    </el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </div>

            <div v-if="!recentSessions.length" class="recent-empty">
              <span>No recent chats</span>
            </div>
          </div>
        </div>

        <div class="sidebar-footer">
          <div class="user-row">
            <div class="user-avatar">{{ usernameInitial }}</div>
            <div class="user-copy">
              <strong>{{ username }}</strong>
              <small>已登录</small>
            </div>
            <el-button class="logout-button" text @click="logout">退出登录</el-button>
          </div>
        </div>
      </el-aside>

      <el-container class="main-shell">
        <el-main :class="{ 'auth-main': isAuthPage, 'profile-main': route.path === '/profile' }">
          <router-view />
        </el-main>
      </el-container>
    </el-container>
  </el-config-provider>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import {
  Connection,
  Cpu,
  DataAnalysis,
  Delete,
  EditPen,
  FolderOpened,
  MoreFilled,
  Monitor,
  Plus,
  RefreshRight,
  User,
} from "@element-plus/icons-vue";
import { activeProfileSessionId, profileApi, setActiveProfileSessionId } from "./api";

const router = useRouter();
const route = useRoute();

const primaryNav = [
  { path: "/student-portrait", label: "学生画像", icon: User },
  { path: "/path", label: "学习路径", icon: Connection },
  { path: "/evaluation", label: "学习评估", icon: DataAnalysis },
];

const secondaryNav = [
  { path: "/architecture", label: "智能体架构", icon: Cpu },
  { path: "/knowledge", label: "知识库管理", icon: FolderOpened },
  { path: "/system", label: "系统状态", icon: Monitor },
];

const user = computed(() => JSON.parse(localStorage.getItem("user") || "{}"));
const username = computed(() => user.value.username || "学习者");
const usernameInitial = computed(() => username.value.slice(0, 1).toUpperCase());
const isAuthPage = computed(() => route.path === "/auth");
const recentSessions = ref([]);
const creatingSession = ref(false);
const activeSessionId = ref(activeProfileSessionId());

function byCreateTime(a, b) {
  const aTime = a?.create_time ? new Date(a.create_time).getTime() : 0;
  const bTime = b?.create_time ? new Date(b.create_time).getTime() : 0;

  if (aTime && bTime && aTime !== bTime) {
    return aTime - bTime;
  }

  return Number(a?.id || 0) - Number(b?.id || 0);
}

async function loadRecentSessions() {
  if (isAuthPage.value) return;
  const res = await profileApi.sessions();
  if (res.code === 200) {
    recentSessions.value = [...(res.data.sessions || [])]
      .sort(byCreateTime)
      .slice(0, 7);
  }
}

async function createNewChat() {
  creatingSession.value = true;
  try {
    setActiveProfileSessionId("");
    activeSessionId.value = "";
    if (route.path !== "/profile") {
      await router.push("/profile");
    } else {
      window.dispatchEvent(new CustomEvent("a3-profile-session-created", { detail: { id: "" } }));
    }
  } finally {
    creatingSession.value = false;
  }
}

async function openSession(id) {
  if (Number(id) === Number(activeSessionId.value) && route.path === "/profile") {
    return;
  }
  const previousSessionId = activeSessionId.value;
  activeSessionId.value = String(id);
  setActiveProfileSessionId(id);
  const res = await profileApi.activateSession(id);
  if (res.code !== 200) {
    activeSessionId.value = previousSessionId;
    setActiveProfileSessionId(previousSessionId || "");
    ElMessage.error(res.msg || "切换会话失败");
    return;
  }
  if (route.path !== "/profile") {
    await router.push("/profile");
  } else {
    window.dispatchEvent(new CustomEvent("a3-profile-session-change", { detail: { id } }));
  }
}

function sessionTitle(item) {
  return item?.title || `会话 ${item?.id || ""}`;
}

async function handleSessionCommand(command, item) {
  if (command === "rename") {
    await renameSession(item);
    return;
  }
  if (command === "delete") {
    await deleteSession(item);
  }
}

async function renameSession(item) {
  const id = item?.id;
  if (!id) return;

  try {
    const { value } = await ElMessageBox.prompt("请输入新的对话名称", "重命名", {
      confirmButtonText: "保存",
      cancelButtonText: "取消",
      inputValue: sessionTitle(item),
      inputPattern: /\S/,
      inputErrorMessage: "对话名称不能为空",
    });
    const title = String(value || "").trim();
    if (!title || title === item.title) return;

    const res = await profileApi.renameSession(id, title);
    if (res.code !== 200) {
      ElMessage.error(res.msg || "重命名失败");
      return;
    }
    await loadRecentSessions();
    ElMessage.success(res.msg || "已重命名");
  } catch (error) {
    // 用户取消
  }
}

async function deleteSession(item) {
  const id = item?.id;
  if (!id) return;

  try {
    await ElMessageBox.confirm(`确定要删除“${sessionTitle(item)}”吗？删除后相关画像、资源、路径和答疑记录也会一并移除。`, "删除对话", {
      confirmButtonText: "删除",
      cancelButtonText: "取消",
      type: "warning",
      confirmButtonClass: "el-button--danger",
    });

    const wasActive = Number(id) === Number(activeSessionId.value);
    const res = await profileApi.deleteSession(id);
    if (res.code !== 200) {
      ElMessage.error(res.msg || "删除对话失败");
      return;
    }

    const nextActiveId = res.data?.active_session_id || "";
    setActiveProfileSessionId(nextActiveId);
    activeSessionId.value = nextActiveId ? String(nextActiveId) : "";
    await loadRecentSessions();
    ElMessage.success(res.msg || "对话已删除");

    if (wasActive) {
      if (route.path !== "/profile") {
        await router.push("/profile");
      }
      window.dispatchEvent(new CustomEvent("a3-profile-session-change", { detail: { id: nextActiveId } }));
    }
  } catch (error) {
    // 用户取消
  }
}

async function logout() {
  try {
    await ElMessageBox.confirm("确定要退出当前账号吗？", "退出登录", {
      confirmButtonText: "退出",
      cancelButtonText: "取消",
      type: "warning",
    });
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    setActiveProfileSessionId("");
    activeSessionId.value = "";
    router.push("/auth");
  } catch (error) {
    // 用户取消
  }
}

watch(() => route.path, () => {
  loadRecentSessions();
});

onMounted(() => {
  activeSessionId.value = activeProfileSessionId();
  loadRecentSessions();
  window.addEventListener("a3-profile-session-refresh", loadRecentSessions);
  window.addEventListener("a3-profile-session-change", syncActiveSession);
  window.addEventListener("a3-profile-session-created", syncActiveSession);
});

onBeforeUnmount(() => {
  window.removeEventListener("a3-profile-session-refresh", loadRecentSessions);
  window.removeEventListener("a3-profile-session-change", syncActiveSession);
  window.removeEventListener("a3-profile-session-created", syncActiveSession);
});

function syncActiveSession() {
  activeSessionId.value = activeProfileSessionId();
}
</script>

<style scoped>
.app-shell {
  height: 100vh;
  overflow: hidden;
  background: #ffffff;
}

.sidebar {
  display: flex;
  flex-direction: column;
  gap: 10px;
  height: 100vh;
  padding: 12px 10px 10px;
  overflow: hidden;
  border-right: 1px solid #ececec;
  background: #f8f8fb;
}

.sidebar-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 4px 8px 2px;
}

.brand-title {
  color: #111827;
  font-size: 18px;
  font-weight: 700;
  letter-spacing: -0.01em;
}

.new-chat-button {
  justify-content: flex-start;
  height: 44px;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  background: #ffffff;
  color: #111827;
  font-weight: 500;
}

.menu-group {
  display: grid;
  gap: 4px;
}

.menu-group-compact {
  margin-top: 2px;
  padding-bottom: 4px;
  border-bottom: 1px solid #ececf2;
}

.menu-group-label {
  padding: 0 10px;
  color: #8f96a3;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.side-menu {
  border-right: none;
  background: transparent;
}

.side-menu :deep(.el-menu-item) {
  height: 40px;
  margin: 2px 0;
  padding-left: 12px !important;
  border-radius: 10px;
  color: #4b5563;
  font-weight: 450;
}

.side-menu :deep(.el-menu-item .el-icon) {
  margin-right: 10px;
  font-size: 17px;
}

.side-menu :deep(.el-menu-item.is-active) {
  color: #111827;
  background: #eceff3;
}

.side-menu :deep(.el-menu-item:hover) {
  background: #f1f2f5;
}

.recent-section {
  display: flex;
  flex: 1;
  min-height: 0;
  flex-direction: column;
  gap: 6px;
  padding-top: 4px;
}

.recent-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
  padding: 0 10px;
}

.recent-heading {
  display: grid;
}

.recent-title-main {
  color: #111827;
  font-size: 13px;
  font-weight: 700;
}

.refresh-button {
  color: #a1a1aa;
}

.recent-list {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
  display: grid;
  align-content: start;
  gap: 1px;
  padding: 0 4px 6px;
}

.recent-list::-webkit-scrollbar {
  width: 6px;
}

.recent-list::-webkit-scrollbar-thumb {
  border-radius: 999px;
  background: #d9dce3;
}

.recent-item {
  width: 100%;
  display: grid;
  grid-template-columns: minmax(0, 1fr) 30px;
  align-items: center;
  gap: 6px;
  min-height: 38px;
  padding: 4px 4px 4px 10px;
  text-align: left;
  border: none;
  border-radius: 10px;
  background: transparent;
  color: #202123;
  cursor: pointer;
  transition: 0.16s ease;
}

.recent-item:hover {
  background: #f3f4f6;
}

.recent-item.active {
  background: #e8eaee;
  color: #111827;
}

.recent-title {
  display: block;
  min-width: 0;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
  font-size: 14px;
  font-weight: 400;
}

.recent-more-button {
  width: 28px;
  height: 28px;
  color: #6b7280;
  opacity: 0.72;
}

.recent-item:hover .recent-more-button,
.recent-item.active .recent-more-button,
.recent-more-button:focus-visible {
  opacity: 1;
}

.recent-more-button:hover {
  background: #e5e7eb;
  color: #111827;
}

:global(.recent-actions-popper) {
  border-radius: 18px !important;
  box-shadow: 0 18px 45px rgba(15, 23, 42, 0.16) !important;
}

:global(.recent-actions-menu) {
  min-width: 168px;
  padding: 10px !important;
}

:global(.recent-action-item) {
  display: flex !important;
  align-items: center;
  gap: 10px;
  height: 42px;
  border-radius: 10px;
  color: #111827 !important;
  font-size: 15px;
}

:global(.recent-action-item .el-icon) {
  margin-right: 0;
  font-size: 18px;
}

:global(.recent-action-item.danger) {
  color: #dc2626 !important;
}

:global(.recent-action-item.danger:hover) {
  background: #fee2e2 !important;
}

.recent-empty {
  padding: 10px;
  color: #9ca3af;
  font-size: 13px;
  line-height: 1.5;
}

.sidebar-footer {
  display: block;
  flex: 0 0 auto;
  padding-top: 8px;
  border-top: 1px solid #ececf2;
}

.user-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 8px;
}

.user-avatar {
  display: grid;
  width: 34px;
  height: 34px;
  place-items: center;
  border-radius: 999px;
  background: #ef4444;
  color: #ffffff;
  font-size: 12px;
  font-weight: 700;
}

.user-copy {
  min-width: 0;
  flex: 1;
}

.user-copy strong,
.user-copy small {
  display: block;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.user-copy strong {
  color: #111827;
  font-size: 14px;
}

.user-copy small {
  margin-top: 2px;
  color: #8b919b;
}

.logout-button {
  flex: 0 0 auto;
  height: 30px;
  padding: 0 8px;
  color: #6b7280;
  font-weight: 600;
}

.logout-button:hover {
  color: #ef4444;
  background: #fee2e2;
}

.main-shell {
  min-width: 0;
  height: 100vh;
  background: #ffffff;
}

.main-shell :deep(.el-main) {
  min-width: 0;
  height: 100vh;
  overflow: auto;
  padding: 0;
}

.main-shell :deep(.el-main.profile-main) {
  overflow: hidden;
}

.auth-main {
  height: 100vh !important;
  overflow: hidden !important;
  padding: 0 !important;
}

@media (max-width: 1024px) {
  .sidebar {
    display: none;
  }
}
</style>
