<template>
  <el-config-provider>
    <div class="app-shell" :class="{ 'auth-shell': !showShell }">
      <aside v-if="showShell" class="sidebar">
        <div class="brand-block">
          <div class="brand-mark">A3</div>
          <div class="brand-copy">
            <strong>Learning Agent</strong>
            <p>面向课程学习的个性化学习平台</p>
          </div>
        </div>

        <nav class="nav-group">
          <button
            v-for="item in mainNav"
            :key="item.path"
            class="nav-item"
            :class="{ active: isNavActive(item.path) }"
            @click="router.push(item.path)"
          >
            <span class="nav-title">{{ item.label }}</span>
          </button>
        </nav>

        <div class="sidebar-bottom">
          <div class="session-switcher">
            <div class="section-row">
              <strong>画像会话</strong>
              <el-button size="small" type="primary" @click="createSession">新建</el-button>
            </div>
            <div class="session-list">
              <button
                v-for="item in sessionItems"
                :key="item.id"
                class="session-chip"
                :class="{ active: Number(item.id) === Number(activeSessionId) }"
                @click="switchSession(item.id)"
              >
                <span class="session-title">
                  {{ sessionLabel(item, sessionItems.findIndex((entry) => entry.id === item.id) + 1) }}
                </span>
              </button>
            </div>
          </div>

          <div class="account-card">
            <div class="account-avatar">{{ usernameInitial }}</div>
            <div class="account-copy">
              <strong>{{ username }}</strong>
              <span>当前用户</span>
            </div>
            <el-button text class="settings-link" @click="router.push('/settings')">设置</el-button>
          </div>

          <el-button class="logout-button" @click="logout">退出登录</el-button>
        </div>
      </aside>

      <main class="main-shell">
        <header v-if="showShell" class="topbar">
          <h1>{{ pageTitle }}</h1>
          <div class="topbar-actions">
            <el-button type="primary">升级</el-button>
            <el-button text @click="router.push('/settings')">设置</el-button>
          </div>
        </header>

        <section class="view-shell" :class="{ auth: !showShell }">
          <router-view />
        </section>
      </main>
    </div>
  </el-config-provider>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { ElMessage, ElMessageBox } from 'element-plus';
import { activeProfileSessionId, profileApi, setActiveProfileSessionId } from './api';

const router = useRouter();
const route = useRoute();

const mainNav = [
  { path: '/profile', label: '学习画像' },
  { path: '/resources', label: '学习资源' },
  { path: '/path', label: '学习路径' },
  { path: '/chat', label: '智能答疑' },
  { path: '/evaluation', label: '学习评估' },
];

const pageTitles = {
  '/profile': '学习画像',
  '/profile/chat': '画像会话',
  '/resources': '学习资源',
  '/path': '学习路径',
  '/chat': '智能答疑',
  '/evaluation': '学习评估',
  '/settings': '设置',
};

const showShell = computed(() => route.path !== '/auth');
const user = computed(() => JSON.parse(localStorage.getItem('user') || '{}'));
const username = computed(() => user.value.username || '学习者');
const usernameInitial = computed(() => username.value.slice(0, 1).toUpperCase());
const pageTitle = computed(() => pageTitles[route.path] || 'Learning Agent');

const sessionItems = ref([]);
const activeSessionId = ref(activeProfileSessionId());

function isNavActive(path) {
  if (path === '/profile') {
    return route.path === '/profile' || route.path === '/profile/chat';
  }
  return route.path === path;
}

function sessionLabel(item, index) {
  const raw = String(item?.title || '').trim();
  if (!raw || raw === '空白画像') return `画像对话 ${index}`;
  return raw.replace(/\s+/g, ' ').slice(0, 28);
}

async function loadSessions() {
  if (!localStorage.getItem('token')) return;
  const res = await profileApi.sessions();
  if (res.code !== 200) return;
  sessionItems.value = res.data.sessions || [];
  const nextId = res.data.active_session_id || activeProfileSessionId() || sessionItems.value[0]?.id || '';
  activeSessionId.value = nextId ? String(nextId) : '';
  setActiveProfileSessionId(nextId);
}

async function switchSession(id) {
  if (!id || String(id) === String(activeSessionId.value)) return;
  const res = await profileApi.activateSession(id);
  if (res.code !== 200) {
    ElMessage.error(res.msg || '切换画像会话失败');
    return;
  }
  activeSessionId.value = String(id);
  setActiveProfileSessionId(id);
  window.dispatchEvent(new CustomEvent('profile-session-changed', { detail: { id: Number(id) } }));
  await loadSessions();
  if (route.path !== '/profile/chat') router.push('/profile/chat');
}

async function createSession() {
  const res = await profileApi.createSession();
  if (res.code !== 200) {
    ElMessage.error(res.msg || '新建画像会话失败');
    return;
  }
  const nextId = res.data.id;
  activeSessionId.value = String(nextId);
  setActiveProfileSessionId(nextId);
  window.dispatchEvent(new CustomEvent('profile-session-changed', { detail: { id: Number(nextId), reset: true } }));
  await loadSessions();
  if (route.path !== '/profile/chat') router.push('/profile/chat');
}

async function logout() {
  try {
    await ElMessageBox.confirm('确定退出当前账号吗？', '退出登录', {
      confirmButtonText: '退出',
      cancelButtonText: '取消',
      type: 'warning',
    });
  } catch {
    return;
  }
  localStorage.removeItem('token');
  localStorage.removeItem('user');
  setActiveProfileSessionId('');
  router.push('/auth');
}

function handleSessionRefresh() {
  loadSessions();
}

watch(
  () => route.path,
  () => {
    if (showShell.value) loadSessions();
  }
);

onMounted(() => {
  loadSessions();
  window.addEventListener('profile-session-refresh', handleSessionRefresh);
});

onBeforeUnmount(() => {
  window.removeEventListener('profile-session-refresh', handleSessionRefresh);
});
</script>

<style scoped>
.app-shell {
  display: grid;
  grid-template-columns: 280px minmax(0, 1fr);
  height: 100vh;
  overflow: hidden;
  background: #ffffff;
  color: #37352f;
}

.auth-shell {
  grid-template-columns: 1fr;
}

.sidebar {
  position: sticky;
  top: 0;
  display: flex;
  height: 100vh;
  flex-direction: column;
  gap: 14px;
  overflow-y: auto;
  padding: 16px 12px;
  border-right: 1px solid #ececf1;
  background: #f7f7f8;
}

.brand-block {
  display: flex;
  gap: 14px;
  align-items: center;
}

.brand-mark {
  display: grid;
  width: 40px;
  height: 40px;
  place-items: center;
  border-radius: 10px;
  background: #10a37f;
  color: #ffffff;
  font-weight: 800;
  font-size: 15px;
}

.brand-copy strong {
  display: block;
  color: #37352f;
  font-size: 14px;
}

.brand-copy p {
  margin: 4px 0 0;
  color: #6e6e73;
  font-size: 12px;
  line-height: 1.45;
}

.nav-group {
  display: grid;
  gap: 4px;
}

.nav-item {
  width: 100%;
  min-height: 40px;
  padding: 8px 12px;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: #6e6e80;
  text-align: left;
  cursor: pointer;
  transition: background-color 0.2s ease, color 0.2s ease;
}

.nav-item:hover {
  background: #f7f7f8;
  color: #000000;
}

.nav-item.active {
  background: #ececf1;
  color: #000000;
}

.nav-title {
  color: inherit;
  font-weight: 600;
  font-size: 14px;
}

.sidebar-bottom {
  display: grid;
  min-height: 0;
  gap: 12px;
  margin-top: auto;
}

.session-switcher {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  min-height: 210px;
  max-height: 360px;
  padding: 8px 0;
}

.section-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}

.section-row strong {
  color: #37352f;
  font-size: 14px;
}

.session-list {
  display: grid;
  gap: 6px;
  min-height: 0;
  overflow: auto;
  padding-right: 4px;
}

.session-chip {
  width: 100%;
  min-height: 44px;
  padding: 10px 12px;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: #6e6e80;
  text-align: left;
  cursor: pointer;
  transition: background-color 0.2s ease, color 0.2s ease;
}

.session-chip:hover {
  background: #f7f7f8;
  color: #000000;
}

.session-chip.active {
  background: #ececf1;
  color: #000000;
}

.session-title {
  display: -webkit-box;
  overflow: hidden;
  max-width: 100%;
  color: inherit;
  font-size: 13px;
  line-height: 1.5;
  white-space: normal;
  word-break: break-word;
  overflow-wrap: anywhere;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.account-card {
  display: grid;
  grid-template-columns: 36px minmax(0, 1fr) auto;
  gap: 10px;
  align-items: center;
  padding: 8px 0;
}

.account-avatar {
  display: grid;
  width: 36px;
  height: 36px;
  place-items: center;
  border-radius: 10px;
  background: #000000;
  color: #ffffff;
  font-weight: 800;
  font-size: 14px;
}

.account-copy strong {
  display: block;
  color: #37352f;
  font-size: 14px;
}

.account-copy span {
  display: block;
  margin-top: 2px;
  color: #6e6e73;
  font-size: 12px;
}

.settings-link {
  min-height: auto;
  padding: 6px 8px;
}

.logout-button {
  width: 100%;
}

.main-shell {
  display: flex;
  min-width: 0;
  height: 100vh;
  min-height: 0;
  flex-direction: column;
  overflow: hidden;
  background: #ffffff;
}

.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 56px;
  flex-shrink: 0;
  padding: 10px 24px;
  border-bottom: 1px solid #ececf1;
  background: #ffffff;
}

.topbar h1 {
  margin: 0;
  color: #37352f;
  font-size: 20px;
  line-height: 1.2;
}

.topbar-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.view-shell {
  min-width: 0;
  min-height: 0;
  flex: 1;
  overflow: auto;
}

.view-shell.auth {
  overflow: hidden;
}

@media (max-width: 980px) {
  .app-shell {
    grid-template-columns: 1fr;
  }

  .sidebar {
    position: relative;
    height: auto;
    border-right: none;
    border-bottom: 1px solid #ececf1;
  }

  .main-shell {
    height: auto;
  }
}
</style>




