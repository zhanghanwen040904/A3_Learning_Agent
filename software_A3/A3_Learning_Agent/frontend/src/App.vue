<template>
  <el-config-provider>
    <el-container class="layout">
      <el-aside v-if="$route.path !== '/auth'" width="220px" class="sidebar">
        <div class="brand">
          <span class="brand-mark">A3</span>
          <div>
            <strong>Learning Agent</strong>
            <small>个性化学习平台</small>
          </div>
        </div>
        <el-menu router :default-active="$route.path" class="menu">
          <el-menu-item index="/profile">对话式画像</el-menu-item>
          <el-menu-item index="/resources">学习资源</el-menu-item>
          <el-menu-item index="/path">学习路径</el-menu-item>
          <el-menu-item index="/chat">智能答疑</el-menu-item>
          <el-menu-item index="/evaluation">学习评估</el-menu-item>
        </el-menu>
        <div class="sidebar-footer">
          <div class="footer-section-title">系统管理</div>
          <el-menu router :default-active="$route.path" class="bottom-menu">
            <el-menu-item index="/architecture">智能体角色</el-menu-item>
            <el-menu-item index="/knowledge">知识库管理</el-menu-item>
            <el-menu-item index="/system">系统状态</el-menu-item>
          </el-menu>
          <div class="user-pill">
            <span>{{ usernameInitial }}</span>
            <div>
              <strong>{{ username }}</strong>
              <small>当前账号</small>
            </div>
          </div>
          <el-button class="logout-button" plain @click="logout">退出登录</el-button>
        </div>
      </el-aside>
      <el-container class="content-shell">
        <el-header v-if="$route.path !== '/auth'" class="topbar">
          <div>
            <h2>{{ $route.meta.title || "Learning Agent" }}</h2>
            <p>面向课程学习的智能画像、资源生成与学习评估平台</p>
          </div>
          <el-tag effect="plain" type="success">在线学习助手</el-tag>
        </el-header>
        <el-main :class="{ 'auth-main': $route.path === '/auth' }">
          <router-view />
        </el-main>
      </el-container>
    </el-container>
  </el-config-provider>
</template>

<script setup>
import { computed } from "vue";
import { useRouter } from "vue-router";
import { ElMessageBox } from "element-plus";

const router = useRouter();

const user = computed(() => JSON.parse(localStorage.getItem("user") || "{}"));
const username = computed(() => user.value.username || "学习者");
const usernameInitial = computed(() => username.value.slice(0, 1).toUpperCase());

async function logout() {
  try {
    await ElMessageBox.confirm("确定要退出当前账号吗？", "退出登录", {
      confirmButtonText: "退出",
      cancelButtonText: "取消",
      type: "warning",
    });
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    router.push("/auth");
  } catch (error) {
    // 用户取消退出时不需要提示
  }
}
</script>

<style scoped>
.layout {
  height: 100vh;
  overflow: hidden;
  background: #f5f7fb;
}

.sidebar {
  position: sticky;
  top: 0;
  display: flex;
  flex-direction: column;
  height: 100vh;
  overflow: hidden;
  padding: 20px 12px;
  border-right: 1px solid #e5eaf3;
  background: #ffffff;
  box-shadow: 8px 0 30px rgba(15, 23, 42, 0.035);
}

.brand {
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 2px 4px 20px;
}

.brand-mark {
  display: grid;
  width: 44px;
  height: 44px;
  place-items: center;
  border-radius: 14px;
  background: linear-gradient(135deg, #2563eb, #14b8a6);
  color: white;
  font-weight: 800;
  letter-spacing: 0.02em;
}

.brand strong,
.brand small {
  display: block;
}

.brand strong {
  color: #101828;
  font-size: 16px;
}

.brand small {
  color: #667085;
  margin-top: 3px;
}

.menu {
  flex: 1;
  border-right: none;
  background: transparent;
}

.menu :deep(.el-sub-menu__title),
.menu :deep(.el-menu-item) {
  height: 38px;
  margin: 3px 0;
  border-radius: 10px;
  color: #475467;
  font-weight: 500;
}

.menu :deep(.el-menu-item.is-active) {
  color: #155eef;
  background: #eff4ff;
}

.menu :deep(.el-sub-menu .el-menu) {
  background: transparent;
}

.menu :deep(.el-sub-menu .el-menu-item) {
  margin-left: 10px;
  color: #667085;
}

.sidebar-footer {
  display: grid;
  gap: 10px;
  margin-top: auto;
  padding: 14px 6px 0;
  border-top: 1px solid #eef2f6;
}

.footer-section-title {
  padding: 0 10px;
  color: #98a2b3;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.04em;
}

.bottom-menu {
  border-right: none;
  background: transparent;
}

.bottom-menu :deep(.el-menu-item) {
  height: 38px;
  margin: 2px 0;
  border-radius: 10px;
  color: #475467;
  font-weight: 500;
}

.bottom-menu :deep(.el-menu-item.is-active) {
  color: #155eef;
  background: #eff4ff;
}

.user-pill {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px;
  border: 1px solid #eef2f6;
  border-radius: 16px;
  background: #f8fafc;
}

.user-pill span {
  display: grid;
  width: 34px;
  height: 34px;
  place-items: center;
  border-radius: 12px;
  background: #155eef;
  color: #fff;
  font-weight: 800;
}

.user-pill strong,
.user-pill small {
  display: block;
}

.user-pill strong {
  color: #101828;
}

.user-pill small {
  color: #667085;
  margin-top: 2px;
}

.logout-button {
  width: 100%;
}

.content-shell {
  height: 100vh;
  min-width: 0;
  overflow: hidden;
}

.content-shell :deep(.el-main) {
  min-width: 0;
  height: calc(100vh - 76px);
  overflow: auto;
  padding: 0;
}

.topbar {
  height: 76px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 32px;
  border-bottom: 1px solid #e5eaf3;
  background: rgba(255, 255, 255, 0.88);
  backdrop-filter: blur(16px);
}

.topbar h2 {
  margin: 0;
  color: #101828;
  font-size: 21px;
  font-weight: 750;
}

.topbar p {
  margin: 5px 0 0;
  color: #667085;
}

.auth-main {
  height: 100vh !important;
  overflow: hidden !important;
  padding: 0 !important;
}
</style>
