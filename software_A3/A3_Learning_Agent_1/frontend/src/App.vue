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

        <div class="recent-section">
          <button class="new-chat-button" type="button" @click="createSession">新聊天</button>
          <div class="section-row">
            <strong>最近</strong>
            <button
              v-if="activeSessionId"
              class="delete-current-session"
              type="button"
              @click="deleteActiveSession"
            >
              删除当前
            </button>
          </div>
          <div class="session-list">
            <div
              v-for="item in sessionItems"
              :key="item.id"
              class="session-row"
              :class="{ active: Number(item.id) === Number(activeSessionId) }"
            >
              <button class="session-chip" type="button" @click="switchSession(item.id)">
                <span class="session-title">
                  {{ sessionLabel(item, sessionItems.findIndex((entry) => entry.id === item.id) + 1) }}
                </span>
              </button>
              <button class="session-delete" type="button" title="删除对话" @click.stop="deleteSession(item)">×</button>
            </div>
          </div>
        </div>

        <div class="sidebar-bottom">
          <div class="account-card">
            <div class="account-avatar">{{ usernameInitial }}</div>
            <div class="account-copy">
              <strong>{{ username }}</strong>
              <span>已登录</span>
            </div>
          </div>

          <el-button class="logout-button" text @click="logout">退出登录</el-button>
        </div>
      </aside>

      <main class="main-shell">
        <header v-if="showShell" class="topbar" :class="{ minimal: route.path === '/profile/chat' }">
          <h1 v-if="route.path !== '/profile/chat'">{{ pageTitle }}</h1>
          <div v-else></div>
          <div class="topbar-actions">
            <button class="refresh-link" type="button" @click="router.go(0)">↻</button>
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

async function deleteSession(item) {
  const id = item?.id;
  if (!id) return;
  const label = sessionLabel(item, sessionItems.value.findIndex((entry) => entry.id === id) + 1);
  try {
    await ElMessageBox.confirm(`确定删除“${label}”吗？关联画像、资源、路径和答疑记录也会同步清理。`, '删除画像会话', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
    });
  } catch {
    return;
  }
  const res = await profileApi.deleteSession(id);
  if (res.code !== 200) {
    ElMessage.error(res.msg || '删除画像会话失败');
    return;
  }
  ElMessage.success('画像会话已删除');
  await loadSessions();
  window.dispatchEvent(new CustomEvent('profile-session-changed', { detail: { id: activeSessionId.value ? Number(activeSessionId.value) : 0, reset: true } }));
  if (route.path !== '/profile/chat') router.push('/profile/chat');
}

async function deleteActiveSession() {
  const item = sessionItems.value.find((entry) => String(entry.id) === String(activeSessionId.value));
  if (item) {
    await deleteSession(item);
  }
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
  grid-template-columns: 220px minmax(0, 1fr);
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
  background: #0d0d0d;
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

.upgrade-link,
.refresh-link,
.new-chat-button,
.upgrade-mini {
  border: none;
  font: inherit;
  cursor: pointer;
}

.topbar.minimal {
  min-height: 48px;
  border-bottom: none;
  background: #ffffff;
}

.upgrade-link {
  padding: 6px 8px;
  background: transparent;
  color: #37352f;
  font-size: 14px;
}

.refresh-link {
  display: grid;
  width: 34px;
  height: 34px;
  place-items: center;
  border-radius: 999px;
  background: transparent;
  color: #37352f;
  font-size: 18px;
}

.refresh-link:hover {
  background: #f7f7f8;
}

.recent-section {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  min-height: 0;
  flex: 1;
  margin-top: 18px;
}

.new-chat-button {
  height: 30px;
  padding: 0 10px;
  border-radius: 8px;
  background: #ececf1;
  color: #37352f;
  font-size: 12px;
}

.upgrade-mini {
  min-height: 28px;
  padding: 0 10px;
  border: 1px solid #e5e5e5;
  border-radius: 999px;
  background: #ffffff;
  color: #0d0d0d;
  font-size: 12px;
}

.sidebar-bottom {
  display: grid;
  gap: 8px;
  margin-top: 10px;
}

.logout-button {
  width: 100%;
  color: #37352f;
}

.settings-link {
  display: none;
}

.app-shell {
  grid-template-columns: 220px minmax(0, 1fr);
}

.sidebar {
  gap: 10px;
  padding: 12px 8px;
  background: #f7f7f8;
}

.brand-block {
  gap: 10px;
}

.brand-mark {
  width: 34px;
  height: 34px;
  border-radius: 9px;
  background: #0d0d0d;
  font-size: 13px;
}

.brand-copy strong {
  font-weight: 400;
  font-size: 13px;
}

.brand-copy p {
  font-size: 11px;
}

.nav-item {
  min-height: 34px;
  padding: 6px 10px;
}

.nav-title {
  font-weight: 400;
  font-size: 13px;
}

.section-row strong {
  font-weight: 400;
  font-size: 13px;
}

.new-chat-button {
  height: 30px;
  padding: 0 10px;
  background: #ececf1;
  font-size: 12px;
}

.session-list {
  gap: 4px;
}

.session-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  height: 38px;
  min-height: 38px;
  max-height: 38px;
  border-radius: 8px;
  background: transparent;
  overflow: hidden;
}

.session-row:hover,
.session-row.active {
  background: #ececf1;
}

.session-chip {
  display: block;
  height: 38px;
  min-height: 38px;
  max-height: 38px;
  padding: 0 9px;
  background: transparent !important;
  overflow: hidden;
}

.session-title {
  display: block;
  overflow: hidden;
  width: 100%;
  font-size: 12px;
  font-weight: 400;
  line-height: 38px;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.session-delete {
  display: grid;
  width: 22px;
  height: 22px;
  place-items: center;
  flex: 0 0 auto;
  margin-right: 5px;
  padding: 0;
  border: none;
  border-radius: 999px;
  background: #fee2e2;
  color: #d92d20;
  font-size: 16px;
  line-height: 1;
  cursor: pointer;
  opacity: 1;
}

.session-delete:hover {
  background: #fecaca;
  color: #b42318;
}

.delete-current-session {
  flex: 0 0 auto;
  padding: 2px 6px;
  border: none;
  border-radius: 6px;
  background: #fee2e2;
  color: #d92d20;
  font-size: 11px;
  cursor: pointer;
}

.delete-current-session:hover {
  background: #fecaca;
  color: #b42318;
}

.account-card {
  grid-template-columns: 32px minmax(0, 1fr);
  padding: 6px 0;
}

.account-avatar {
  width: 32px;
  height: 32px;
  border-radius: 9px;
  font-size: 12px;
}

.account-copy strong {
  font-weight: 400;
  font-size: 13px;
}

.logout-button {
  min-height: 34px;
  font-weight: 400;
}

.app-shell {
  grid-template-columns: 260px minmax(0, 1fr);
}

.sidebar {
  padding: 12px;
}

.nav-group,
.session-list {
  gap: 4px;
}

.nav-item {
  height: 36px;
  min-height: 36px;
  padding: 0 12px;
  border-radius: 8px;
}

.nav-title {
  font-size: 14px;
  font-weight: 400;
}

.recent-section {
  gap: 10px;
  margin-top: 16px;
}

.new-chat-button {
  width: 100%;
  height: 36px;
  padding: 0 12px;
  border-radius: 8px;
  background: #ececf1;
  color: #37352f;
  font-size: 14px;
  text-align: left;
}

.section-row {
  height: 28px;
  margin-bottom: 0;
  padding: 0 12px;
}

.section-row strong {
  font-size: 14px;
  font-weight: 400;
}

.session-list {
  align-content: start;
  grid-auto-rows: 32px;
}

.session-row {
  height: 32px;
  min-height: 32px;
  max-height: 32px;
  border-radius: 6px;
}

.session-chip {
  height: 32px;
  min-height: 32px;
  max-height: 32px;
  padding: 0 12px;
}

.session-title {
  font-size: 14px;
  line-height: 32px;
}

.session-delete {
  height: 24px;
  margin-right: 8px;
  font-size: 12px;
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

.sidebar-bottom .account-card {
  display: grid;
  grid-template-columns: 32px minmax(0, 1fr) auto;
  align-items: center;
  gap: 8px;
  padding: 6px 0;
}

.sidebar-bottom .account-copy {
  min-width: 0;
}

.sidebar-bottom .account-copy strong,
.sidebar-bottom .account-copy span {
  display: block;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.sidebar-bottom .logout-button {
  width: auto;
  min-height: 28px;
  padding: 0 4px;
  color: #6e6e80;
  font-size: 12px;
}

.sidebar-bottom .logout-button:hover {
  color: #d92d20;
  background: #fee2e2;
}
</style>




