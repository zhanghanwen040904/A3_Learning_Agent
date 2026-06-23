<template>
  <el-config-provider>
    <el-container class="layout">
      <el-aside v-if="$route.path !== '/auth'" width="248px" class="sidebar">
        <div class="brand">
          <span class="brand-mark">A3</span>
          <div>
            <strong>Learning Agent</strong>
            <small>多智能体学习系统</small>
          </div>
        </div>
        <el-menu router :default-active="$route.path" :default-openeds="['management']" class="menu">
          <el-menu-item index="/profile">对话式画像</el-menu-item>
          <el-menu-item index="/resources">学习资源</el-menu-item>
          <el-menu-item index="/path">学习路径</el-menu-item>
          <el-menu-item index="/chat">智能答疑</el-menu-item>
          <el-menu-item index="/evaluation">学习评估</el-menu-item>
          <el-sub-menu index="management">
            <template #title>系统与管理</template>
            <el-menu-item index="/architecture">智能体角色市场</el-menu-item>
            <el-menu-item index="/knowledge">知识库管理</el-menu-item>
            <el-menu-item index="/system">系统状态</el-menu-item>
          </el-sub-menu>
        </el-menu>
        <div class="sidebar-footer">
          <div class="user-pill">
            <span>{{ usernameInitial }}</span>
            <div>
              <strong>{{ username }}</strong>
              <small>已登录</small>
            </div>
          </div>
          <el-button class="logout-button" plain @click="logout">退出登录</el-button>
        </div>
      </el-aside>
      <el-container>
        <el-header v-if="$route.path !== '/auth'" class="topbar">
          <div>
            <h2>{{ $route.meta.title || "A3 Learning Agent" }}</h2>
            <p>基于讯飞星火 V3.5 + SeeDance + RAG 的个性化资源生成系统</p>
          </div>
          <el-tag effect="dark" type="primary">第十五届中国软件杯 A3</el-tag>
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
  min-height: 100vh;
  background: linear-gradient(135deg, #eef2ff 0%, #f8fafc 48%, #ecfeff 100%);
}

.sidebar {
  display: flex;
  flex-direction: column;
  padding: 20px 14px;
  border-right: 1px solid rgba(148, 163, 184, 0.25);
  background: rgba(255, 255, 255, 0.78);
  backdrop-filter: blur(18px);
}

.brand {
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 8px 8px 24px;
}

.brand-mark {
  display: grid;
  width: 46px;
  height: 46px;
  place-items: center;
  border-radius: 16px;
  background: #2563eb;
  color: white;
  font-weight: 800;
}

.brand strong,
.brand small {
  display: block;
}

.brand small {
  color: #64748b;
  margin-top: 4px;
}

.menu {
  flex: 1;
  border-right: none;
  background: transparent;
}

.menu :deep(.el-sub-menu__title),
.menu :deep(.el-menu-item) {
  border-radius: 12px;
}

.menu :deep(.el-sub-menu .el-menu) {
  background: transparent;
}

.menu :deep(.el-sub-menu .el-menu-item) {
  margin-left: 10px;
  color: #475569;
}

.sidebar-footer {
  display: grid;
  gap: 12px;
  margin-top: auto;
  padding: 12px 8px 4px;
}

.user-pill {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px;
  border-radius: 16px;
  background: rgba(37, 99, 235, 0.08);
}

.user-pill span {
  display: grid;
  width: 34px;
  height: 34px;
  place-items: center;
  border-radius: 12px;
  background: #2563eb;
  color: #fff;
  font-weight: 800;
}

.user-pill strong,
.user-pill small {
  display: block;
}

.user-pill small {
  color: #64748b;
  margin-top: 2px;
}

.logout-button {
  width: 100%;
}

.topbar {
  height: 72px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid rgba(148, 163, 184, 0.22);
  background: rgba(255, 255, 255, 0.52);
  backdrop-filter: blur(16px);
}

.topbar h2 {
  margin: 0;
  font-size: 20px;
}

.topbar p {
  margin: 4px 0 0;
  color: #64748b;
}

.auth-main {
  padding: 30px;
}
</style>
