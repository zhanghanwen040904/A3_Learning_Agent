<template>
  <div class="page profile-page" :class="{ landing: isFreshSession, summaryOnly: isProfilePage }">
    <section v-if="isChatPage" class="panel conversation-panel">
      <template v-if="isFreshSession">
        <div class="landing-shell">
          <div class="landing-composer">
            <el-input
              ref="inputRef"
              v-model="draft"
              type="textarea"
              :autosize="{ minRows: 1, maxRows: 4 }"
              resize="none"
              :disabled="sending"
              placeholder="输入你的专业、当前课程、基础情况和目标"
              @keydown.enter.exact.prevent="sendMessage"
            />
            <div class="landing-actions">
              <el-button class="icon-button primary-icon" type="primary" :disabled="!draft.trim() || sending || loading" @click="sendMessage">发送</el-button>
            </div>
          </div>
        </div>
      </template>

      <template v-else>
        <div class="panel-head compact">
          <div>
            <strong>画像对话</strong>
            <p>通过多轮对话持续更新总画像，并在需要时拆出知识点画像。</p>
          </div>
          <div class="head-metrics">
            <el-tag :type="modelEnabled ? 'success' : 'info'">
              {{ modelEnabled ? '智能抽取中' : '本地辅助模式' }}
            </el-tag>
            <el-tag type="primary" effect="plain">{{ completedCount }}/{{ prompts.length }} 项已识别</el-tag>
          </div>
        </div>

        <div ref="messageBoxRef" class="messages">
          <div v-for="(item, index) in messages" :key="index" :class="['msg', item.role]">
            <div class="msg-role">
              <span>{{ item.role === 'assistant' ? '画像助手' : '我' }}</span>
              <small v-if="item.time">{{ item.time }}</small>
            </div>
            <div class="msg-content">{{ item.content }}</div>
          </div>

          <div v-if="sending" class="msg assistant typing-msg">
            <div class="msg-role">画像助手</div>
            <div class="typing-dots">
              <span></span>
              <span></span>
              <span></span>
              <em>{{ loading ? '正在整理画像' : '正在理解你的回答' }}</em>
            </div>
          </div>
        </div>

        <div class="prompt-card" :class="{ complete: isComplete }">
          <div class="prompt-title">{{ isComplete ? '当前画像已基本完整' : '下一轮建议追问' }}</div>
          <div class="prompt-text">{{ nextQuestion }}</div>
        </div>

        <div class="composer">
          <el-input
            ref="chatInputRef"
            v-model="draft"
            type="textarea"
            :autosize="{ minRows: 2, maxRows: 5 }"
            resize="none"
            :disabled="sending"
            placeholder="输入当前回答，按 Enter 发送"
            @keydown.enter.exact.prevent="sendMessage"
          />

          <div class="composer-bar">
            <div class="action-tip">
              <el-icon v-if="sending" class="is-loading"><Loading /></el-icon>
              <span>{{ statusText }}</span>
            </div>
            <div class="action-buttons">
              <el-button :disabled="sending" @click="resetConversation">重新开始</el-button>
              <el-button :loading="sending && !loading" :disabled="!draft.trim() || loading" @click="sendMessage">发送</el-button>
              <el-button type="primary" :loading="loading" :disabled="!canGenerate || sending" @click="createProfile">生成画像</el-button>
            </div>
          </div>

          <el-progress v-if="loading" :percentage="progress" striped striped-flow />
        </div>
      </template>
    </section>

    <aside v-if="isProfilePage" class="profile-side">
      <el-card class="panel summary-card">
        <template #header>
          <div class="summary-head">
            <span>学习画像</span>
            <div class="mode-switch">
              <button :class="{ active: profileMode === 'overall' }" @click="profileMode = 'overall'">总画像</button>
              <button :class="{ active: profileMode === 'knowledge' }" @click="profileMode = 'knowledge'">知识点画像</button>
            </div>
          </div>
        </template>

        <div v-if="profileMode === 'knowledge'" class="knowledge-point-picker">
          <el-tag
            v-for="point in knowledgePointProfiles"
            :key="point.key"
            class="point-tag"
            :effect="selectedKnowledgePoint === point.key ? 'dark' : 'plain'"
            @click="selectedKnowledgePoint = point.key"
          >
            {{ point.label }}
          </el-tag>
          <el-empty v-if="!knowledgePointProfiles.length" description="还没有可拆分的知识点画像" />
        </div>

        <el-alert :title="activeSummary" type="info" :closable="false" show-icon />

        <div class="summary-grid">
          <div v-for="card in summaryCards" :key="card.label" class="summary-item">
            <span>{{ card.label }}</span>
            <strong>{{ card.value }}</strong>
          </div>
        </div>
      </el-card>

      <el-card class="panel">
        <template #header>
          <div class="radar-head">
            <span>{{ profileMode === 'overall' ? '画像雷达图' : '知识点雷达图' }}</span>
            <small>六个维度用于衡量当前画像的信息清晰度。</small>
          </div>
        </template>

        <div ref="chartRef" class="radar"></div>

        <el-descriptions :column="1" border>
          <el-descriptions-item v-for="field in radarFields" :key="field.key" :label="field.label">
            {{ displayText(activeProfile[field.key]) }}
          </el-descriptions-item>
        </el-descriptions>
      </el-card>
    </aside>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue';
import { useRoute } from 'vue-router';
import { Loading } from '@element-plus/icons-vue';
import * as echarts from 'echarts';
import { ElMessage, ElMessageBox } from 'element-plus';
import { ACTIVE_PROFILE_SESSION_KEY, profileApi } from '../api';

const route = useRoute();

const DEFAULT_VALUE = '待进一步补充';
const STORAGE_PREFIX = 'a3_learning_agent_profile_conversation_v6';

const prompts = [
  { id: 'major', label: '专业背景' },
  { id: 'target_course', label: '目标课程' },
  { id: 'knowledge_level', label: '基础情况' },
  { id: 'weak_points', label: '知识短板' },
  { id: 'study_goal', label: '学习目标' },
  { id: 'study_style', label: '学习方式' },
  { id: 'study_time_prefer', label: '时间偏好' },
  { id: 'course_progress', label: '课程进度' },
];

const radarFields = [
  { key: 'knowledge_level', label: '知识基础' },
  { key: 'study_style', label: '学习风格' },
  { key: 'weak_points', label: '薄弱知识点' },
  { key: 'study_goal', label: '学习目标' },
  { key: 'study_time_prefer', label: '时间偏好' },
  { key: 'course_progress', label: '课程进度' },
];

const loading = ref(false);
const sending = ref(false);
const progress = ref(0);
const draft = ref('');
const chartRef = ref(null);
const messageBoxRef = ref(null);
const inputRef = ref(null);
const chatInputRef = ref(null);
const messages = ref([]);
const profile = reactive({});
const missingFields = ref([]);
const nextQuestion = ref('先告诉我你的专业、当前课程和最想解决的知识点。');
const confidence = ref(0);
const isComplete = ref(false);
const modelEnabled = ref(false);
const activeSessionId = ref('');
const profileMode = ref('overall');
const selectedKnowledgePoint = ref('');

let chartInstance = null;
let saveTimer = null;

const previewProfile = computed(() => {
  const merged = {};
  for (const prompt of prompts) merged[prompt.id] = profile[prompt.id] || DEFAULT_VALUE;
  merged.profile_summary = profile.profile_summary || '';
  return merged;
});

const completedCount = computed(() => prompts.filter((item) => previewProfile.value[item.id] !== DEFAULT_VALUE).length);
const hasUserMessages = computed(() => messages.value.some((item) => item.role === 'user'));
const canGenerate = computed(() => hasUserMessages.value || completedCount.value >= 3);
const isChatPage = computed(() => route.path === '/profile/chat');
const isProfilePage = computed(() => route.path === '/profile');
const isFreshSession = computed(() => isChatPage.value && !hasUserMessages.value && completedCount.value === 0 && !loading.value && !sending.value);

const knowledgePointProfiles = computed(() => {
  const points = splitKnowledgePoints(previewProfile.value.weak_points);
  return points.map((point) => ({
    key: point,
    label: point,
    profile: {
      ...previewProfile.value,
      target_course:
        previewProfile.value.target_course && previewProfile.value.target_course !== DEFAULT_VALUE
          ? `${previewProfile.value.target_course} / ${point}`
          : point,
      weak_points: point,
      profile_summary: buildKnowledgeSummary(previewProfile.value, point),
    },
  }));
});

const activeKnowledgeProfile = computed(() => {
  if (!knowledgePointProfiles.value.length) return null;
  return knowledgePointProfiles.value.find((item) => item.key === selectedKnowledgePoint.value) || knowledgePointProfiles.value[0];
});

const activeProfile = computed(() => {
  if (profileMode.value === 'knowledge' && activeKnowledgeProfile.value) return activeKnowledgeProfile.value.profile;
  return previewProfile.value;
});

const activeSummary = computed(() => {
  if (profileMode.value === 'knowledge' && activeKnowledgeProfile.value) return activeKnowledgeProfile.value.profile.profile_summary;
  return buildOverallSummary(previewProfile.value);
});

const summaryCards = computed(() => [
  { label: '专业', value: displayText(activeProfile.value.major) },
  { label: profileMode.value === 'overall' ? '目标课程' : '聚焦知识点', value: displayText(activeProfile.value.target_course) },
  { label: '学习方式', value: displayText(activeProfile.value.study_style) },
  { label: '学习目标', value: displayText(activeProfile.value.study_goal) },
  { label: '知识短板', value: displayText(activeProfile.value.weak_points) },
  { label: '时间偏好', value: displayText(activeProfile.value.study_time_prefer) },
]);

const statusText = computed(() => {
  if (loading.value) return '正在整理结构化画像';
  if (sending.value) return '正在理解你的回答';
  if (isComplete.value) return '画像已基本完整';
  return `已识别 ${completedCount.value}/${prompts.length} 项信息`;
});

function displayText(value) {
  return value && String(value).trim() ? String(value).trim() : DEFAULT_VALUE;
}

function buildOverallSummary(source) {
  if (source.profile_summary) return source.profile_summary;
  const parts = [];
  if (source.major !== DEFAULT_VALUE) parts.push(`${source.major}方向学生`);
  if (source.target_course !== DEFAULT_VALUE) parts.push(`当前聚焦${source.target_course}`);
  if (source.weak_points !== DEFAULT_VALUE) parts.push(`短板集中在${source.weak_points}`);
  if (source.study_goal !== DEFAULT_VALUE) parts.push(`目标是${source.study_goal}`);
  return parts.length ? `${parts.join('，')}。` : '继续对话后，这里会自动生成画像摘要。';
}

function buildKnowledgeSummary(source, point) {
  const parts = [];
  if (source.major !== DEFAULT_VALUE) parts.push(`${source.major}学生`);
  parts.push(`当前重点突破“${point}”`);
  if (source.study_style !== DEFAULT_VALUE) parts.push(`更适合${source.study_style}`);
  if (source.study_goal !== DEFAULT_VALUE) parts.push(`目标是${source.study_goal}`);
  return `${parts.join('，')}。`;
}

function splitKnowledgePoints(value) {
  return [
    ...new Set(
      String(value || '')
        .replace(/[；、]/g, '，')
        .split(/[，\n]/)
        .map((item) => item.trim())
        .filter(Boolean)
        .filter((item) => item !== DEFAULT_VALUE)
    ),
  ].slice(0, 8);
}

function timeLabel() {
  return new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
}

function assistantMessage(content) {
  return { role: 'assistant', content, time: timeLabel() };
}

function userMessage(content) {
  return { role: 'user', content, time: timeLabel() };
}

function normalizeText(text) {
  return String(text || '').trim();
}

function sameMessage(a, b) {
  return a?.role === b?.role && normalizeText(a?.content) === normalizeText(b?.content);
}

function cleanMessages(list = []) {
  const cleaned = [];
  for (const item of list) {
    if (!item?.role || !normalizeText(item.content)) continue;
    const next = { ...item, content: normalizeText(item.content) };
    if (!sameMessage(cleaned[cleaned.length - 1], next)) cleaned.push(next);
  }
  return cleaned;
}

function pushAssistant(content) {
  const next = assistantMessage(normalizeText(content));
  if (!sameMessage(messages.value[messages.value.length - 1], next)) messages.value.push(next);
}

function initConversation() {
  messages.value = [];
}

function scrollToBottom() {
  nextTick(() => {
    const box = messageBoxRef.value;
    if (box) box.scrollTop = box.scrollHeight;
  });
}

function focusInput() {
  nextTick(() => {
    inputRef.value?.focus?.();
    chatInputRef.value?.focus?.();
  });
}

function storageKey(id = activeSessionId.value) {
  return `${STORAGE_PREFIX}_${id || 'none'}`;
}

function snapshotState() {
  return {
    profile_session_id: activeSessionId.value,
    messages: messages.value,
    draft: draft.value,
    profile: { ...profile },
    missingFields: missingFields.value,
    nextQuestion: nextQuestion.value,
    confidence: confidence.value,
    isComplete: isComplete.value,
    modelEnabled: modelEnabled.value,
    profileMode: profileMode.value,
    selectedKnowledgePoint: selectedKnowledgePoint.value,
  };
}

function persistState() {
  try {
    localStorage.setItem(storageKey(), JSON.stringify(snapshotState()));
  } catch {}
}

function schedulePersist() {
  window.clearTimeout(saveTimer);
  saveTimer = window.setTimeout(persistState, 120);
}

function applyState(saved = {}) {
  messages.value = Array.isArray(saved.messages) && saved.messages.length ? cleanMessages(saved.messages) : [];
  draft.value = saved.draft || '';
  Object.keys(profile).forEach((key) => delete profile[key]);
  Object.assign(profile, saved.profile || {});
  missingFields.value = Array.isArray(saved.missingFields) ? saved.missingFields : [];
  nextQuestion.value = saved.nextQuestion || nextQuestion.value;
  confidence.value = Number(saved.confidence || 0);
  isComplete.value = Boolean(saved.isComplete);
  modelEnabled.value = Boolean(saved.modelEnabled);
  profileMode.value = saved.profileMode || 'overall';
  selectedKnowledgePoint.value = saved.selectedKnowledgePoint || '';
}

function restoreState() {
  try {
    const raw = localStorage.getItem(storageKey());
    if (!raw) return false;
    applyState(JSON.parse(raw));
    return true;
  } catch {
    localStorage.removeItem(storageKey());
    return false;
  }
}

async function saveConversationRemote() {
  if (!activeSessionId.value) return;
  try {
    await profileApi.saveConversation(snapshotState());
  } catch {}
}

async function loadConversationRemote() {
  try {
    const res = await profileApi.getConversation();
    if (res.code === 200 && Array.isArray(res.data?.messages)) {
      const remoteMessages = cleanMessages(res.data.messages);
      if (remoteMessages.length >= messages.value.length) messages.value = remoteMessages;
    }
  } catch {}
}

function clearCurrentSessionState() {
  draft.value = '';
  missingFields.value = [];
  confidence.value = 0;
  isComplete.value = false;
  modelEnabled.value = false;
  profileMode.value = 'overall';
  selectedKnowledgePoint.value = '';
  Object.keys(profile).forEach((key) => delete profile[key]);
  nextQuestion.value = '先告诉我你的专业、当前课程和最想解决的知识点。';
  initConversation();
}

async function resetRemoteSession() {
  if (!activeSessionId.value) return;
  await profileApi.resetSession(activeSessionId.value);
  localStorage.removeItem(storageKey());
}

async function handleSessionChanged(event) {
  const id = event?.detail?.id || '';
  activeSessionId.value = id ? String(id) : '';
  clearCurrentSessionState();
  restoreState();
  await loadConversationRemote();
  await loadProfile();
  scrollToBottom();
  focusInput();
}

async function sendMessage() {
  const text = normalizeText(draft.value);
  if (!text || sending.value || loading.value) return;

  sending.value = true;
  messages.value.push(userMessage(text));
  draft.value = '';
  scrollToBottom();

  try {
    const payloadMessages = messages.value.map((item) => ({ role: item.role, content: item.content }));
    const res = await profileApi.chat({ messages: payloadMessages, current_profile: { ...profile } });
    if (res.code !== 200) {
      pushAssistant(res.msg || '画像分析失败，请稍后重试。');
      ElMessage.error(res.msg || '画像分析失败');
      return;
    }

    Object.assign(profile, res.data.profile || {});
    missingFields.value = res.data.missing_fields || [];
    nextQuestion.value = res.data.next_question || '画像已经基本完整，可以继续补充，或直接点击生成画像。';
    confidence.value = Number(res.data.confidence || 0);
    isComplete.value = Boolean(res.data.is_complete);
    modelEnabled.value = Boolean(res.data.model_enabled);
    if (nextQuestion.value) pushAssistant(nextQuestion.value);
    messages.value = cleanMessages(messages.value);
    schedulePersist();
    await saveConversationRemote();
    window.dispatchEvent(new CustomEvent('profile-session-refresh'));
  } catch (error) {
    pushAssistant('画像对话接口异常，请确认后端和模型配置正常。');
    ElMessage.error(error?.message || '发送失败');
  } finally {
    sending.value = false;
    scrollToBottom();
    focusInput();
  }
}

async function resetConversation() {
  try {
    await ElMessageBox.confirm(
      '重新开始会清空当前画像会话中的对话、画像、学习资源和学习路径。确定继续吗？',
      '确认重新开始',
      {
        confirmButtonText: '重新开始',
        cancelButtonText: '取消',
        type: 'warning',
      }
    );
  } catch {
    return;
  }

  await resetRemoteSession();
  clearCurrentSessionState();
  schedulePersist();
  window.dispatchEvent(new CustomEvent('profile-session-refresh'));
  scrollToBottom();
  focusInput();
}

function buildDialogue() {
  return messages.value
    .filter((item) => item.role === 'user')
    .map((item, index) => `学生第${index + 1}轮回答：${item.content}`)
    .join('\n');
}

function keywordCount(text, keywords) {
  return keywords.reduce((count, keyword) => count + (text.includes(keyword) ? 1 : 0), 0);
}

function scoreByContent(key, value) {
  const text = String(value || '').trim();
  if (!text || text === DEFAULT_VALUE) return 18;
  let score = Math.min(72, 28 + text.length * 1.1);
  if (key === 'knowledge_level') score += keywordCount(text, ['零基础', '基础一般', '较弱', '熟悉']) * 6;
  if (key === 'study_style') score += keywordCount(text, ['图文', '案例', '练习', '视频', '代码', '讲解']) * 5;
  if (key === 'weak_points') score += keywordCount(text, splitKnowledgePoints(text)) * 8;
  if (key === 'study_goal') score += keywordCount(text, ['考试', '作业', '掌握', '完成', '一周', '两周', '90分']) * 4;
  if (key === 'study_time_prefer') score += keywordCount(text, ['晚上', '白天', '周末', '小时', '分钟']) * 5;
  if (key === 'course_progress') score += keywordCount(text, ['第', '章', '正在', '刚学完', '考试']) * 4;
  return Math.max(18, Math.min(96, Math.round(score)));
}

function radarScores() {
  return radarFields.map((item) => scoreByContent(item.key, activeProfile.value[item.key]));
}

function drawRadar() {
  if (!chartRef.value || isFreshSession.value) return;
  if (!chartInstance) chartInstance = echarts.init(chartRef.value);
  chartInstance.setOption({
    tooltip: {},
    radar: {
      indicator: radarFields.map((item) => ({ name: item.label, max: 100 })),
      radius: '62%',
      splitArea: { areaStyle: { color: ['#f8fbff', '#f3f7fc', '#eef4fb', '#e8f0fb'] } },
      axisLine: { lineStyle: { color: '#cbd5e1' } },
      splitLine: { lineStyle: { color: '#dbeafe' } },
    },
    series: [
      {
        type: 'radar',
        data: [
          {
            value: radarScores(),
            name: profileMode.value === 'overall' ? '总画像' : '知识点画像',
            areaStyle: { color: 'rgba(16, 163, 127, 0.16)' },
            lineStyle: { color: '#10a37f', width: 2 },
            symbolSize: 6,
            itemStyle: { color: '#10a37f' },
          },
        ],
      },
    ],
  });
}

async function loadProfile() {
  try {
    const res = await profileApi.get();
    Object.keys(profile).forEach((key) => delete profile[key]);
    if (res.code === 200 && res.data && Object.keys(res.data).length > 0) Object.assign(profile, res.data);
  } catch {
    ElMessage.warning('历史画像读取失败，将继续使用当前会话上下文。');
  } finally {
    if (!selectedKnowledgePoint.value && knowledgePointProfiles.value.length) {
      selectedKnowledgePoint.value = knowledgePointProfiles.value[0].key;
    }
    await nextTick();
    drawRadar();
  }
}

async function createProfile() {
  const dialogue = buildDialogue();
  if (!dialogue || loading.value || sending.value) return;

  loading.value = true;
  sending.value = true;
  progress.value = 15;
  const timer = window.setInterval(() => {
    progress.value = Math.min(progress.value + 10, 92);
  }, 450);

  try {
    const res = await profileApi.create({ dialogue, profile: { ...profile }, conversation: snapshotState() });
    if (res.code !== 200) {
      pushAssistant(res.msg || '画像生成失败，请稍后重试。');
      ElMessage.error(res.msg || '画像生成失败');
      return;
    }
    Object.assign(profile, res.data || {});
    if (!selectedKnowledgePoint.value && knowledgePointProfiles.value.length) {
      selectedKnowledgePoint.value = knowledgePointProfiles.value[0].key;
    }
    pushAssistant(`画像已生成：${buildOverallSummary(profile)}`);
    schedulePersist();
    await saveConversationRemote();
    window.dispatchEvent(new CustomEvent('profile-session-refresh'));
    drawRadar();
    ElMessage.success('画像生成成功');
  } catch (error) {
    pushAssistant('画像生成时出现网络或服务异常，请稍后再试。');
    ElMessage.error(error?.message || '画像生成异常');
  } finally {
    window.clearInterval(timer);
    progress.value = 100;
    loading.value = false;
    sending.value = false;
  }
}

watch(
  activeProfile,
  async () => {
    await nextTick();
    drawRadar();
  },
  { deep: true }
);

watch([messages, draft, missingFields, confidence, isComplete, modelEnabled, profileMode, selectedKnowledgePoint], schedulePersist, {
  deep: true,
});
watch(profile, schedulePersist, { deep: true });
watch(
  knowledgePointProfiles,
  (list) => {
    if (profileMode.value === 'knowledge' && list.length && !list.find((item) => item.key === selectedKnowledgePoint.value)) {
      selectedKnowledgePoint.value = list[0].key;
    }
  },
  { deep: true }
);

onMounted(async () => {
  const saved = localStorage.getItem(ACTIVE_PROFILE_SESSION_KEY);
  if (saved) activeSessionId.value = String(saved);
  if (!restoreState()) initConversation();
  await loadConversationRemote();
  await loadProfile();
  window.addEventListener('resize', drawRadar);
  window.addEventListener('profile-session-changed', handleSessionChanged);
  scrollToBottom();
  focusInput();
});

onBeforeUnmount(() => {
  schedulePersist();
  window.clearTimeout(saveTimer);
  window.removeEventListener('resize', drawRadar);
  window.removeEventListener('profile-session-changed', handleSessionChanged);
  chartInstance?.dispose?.();
  chartInstance = null;
});
</script>

<style scoped>
.profile-page {
  display: grid;
  grid-template-columns: minmax(0, 1.45fr) minmax(340px, 0.9fr);
  gap: 24px;
  min-height: calc(100vh - 104px);
}

.profile-page.landing {
  grid-template-columns: 1fr;
}

.profile-page.summaryOnly {
  grid-template-columns: 1fr;
  justify-content: stretch;
}

.conversation-panel {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr) auto auto;
  min-height: calc(100vh - 140px);
  gap: 14px;
}

.profile-page.landing .conversation-panel {
  grid-template-rows: 1fr;
}

.landing-shell {
  display: grid;
  place-items: center;
  min-height: calc(100vh - 180px);
  padding: 0;
}

.landing-composer {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: 12px;
  width: min(980px, 100%);
  padding: 10px 12px 10px 18px;
  border: 1px solid #ececf1;
  border-radius: 28px;
  background: #ffffff;
}

.landing-composer :deep(.el-textarea__inner) {
  min-height: 28px !important;
  padding: 10px 0 !important;
  border-radius: 0 !important;
  box-shadow: none !important;
  background: transparent !important;
  resize: none;
}

.landing-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.icon-button {
  min-width: 48px;
  min-height: 48px;
  padding: 0 18px;
  border-radius: 999px;
}

.primary-icon {
  min-width: 72px;
  padding: 0 20px;
}

.panel-head,
.summary-head,
.radar-head,
.composer-bar {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.panel-head strong,
.summary-head span,
.radar-head span {
  color: #37352f;
  font-size: 16px;
}

.panel-head.compact p {
  max-width: 520px;
  margin: 6px 0 0;
  color: #6e6e73;
  line-height: 1.6;
}

.head-metrics {
  display: flex;
  gap: 8px;
}

.messages {
  min-height: 0;
  overflow: auto;
  padding: 12px 0 0;
  background: #ffffff;
}

.msg {
  max-width: 84%;
  margin-bottom: 16px;
  padding: 14px 16px;
  border-radius: 18px;
  background: #f7f7f8;
}

.msg.assistant {
  border-top-left-radius: 10px;
}

.msg.user {
  margin-left: auto;
  border: 1px solid #ececf1;
  background: #ffffff;
  border-top-right-radius: 10px;
}

.msg-role {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 8px;
  color: #6e6e73;
  font-size: 12px;
}

.msg-content {
  color: #37352f;
  line-height: 1.75;
  white-space: pre-wrap;
  word-break: break-word;
}

.typing-dots {
  display: flex;
  align-items: center;
  gap: 7px;
  color: #6e6e73;
}

.typing-dots span {
  width: 7px;
  height: 7px;
  border-radius: 999px;
  background: #10a37f;
  animation: blink 1.2s infinite ease-in-out;
}

.typing-dots span:nth-child(2) {
  animation-delay: 0.15s;
}

.typing-dots span:nth-child(3) {
  animation-delay: 0.3s;
}

.typing-dots em {
  margin-left: 4px;
  font-style: normal;
  font-size: 13px;
}

@keyframes blink {
  0%,
  80%,
  100% {
    opacity: 0.25;
    transform: translateY(0);
  }
  40% {
    opacity: 1;
    transform: translateY(-3px);
  }
}

.prompt-card {
  padding: 14px 16px;
  border: 1px solid #ececf1;
  border-radius: 18px;
  background: #f7f7f8;
}

.prompt-card.complete {
  background: #f0fdf4;
  border-color: #bbf7d0;
}

.prompt-title {
  margin-bottom: 6px;
  color: #10a37f;
  font-size: 12px;
  font-weight: 700;
}

.prompt-text {
  color: #37352f;
  line-height: 1.7;
}

.composer {
  position: sticky;
  bottom: 0;
  display: grid;
  gap: 10px;
  padding-top: 4px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0) 0%, rgba(255, 255, 255, 0.92) 24%, rgba(255, 255, 255, 1) 100%);
}

.action-tip {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #6e6e73;
  font-size: 13px;
}

.action-buttons {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 10px;
}

.profile-side {
  display: grid;
  align-content: start;
  gap: 18px;
}

.mode-switch {
  display: inline-flex;
  padding: 4px;
  border: 1px solid #ececf1;
  border-radius: 999px;
  background: #f7f7f8;
}

.mode-switch button {
  padding: 8px 14px;
  border: none;
  border-radius: 999px;
  background: transparent;
  color: #6e6e73;
  cursor: pointer;
}

.mode-switch button.active {
  background: #10a37f;
  color: #ffffff;
}

.knowledge-point-picker {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 16px;
}

.point-tag {
  cursor: pointer;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
  margin-top: 18px;
}

.summary-item {
  min-height: 96px;
  padding: 16px;
  border: 1px solid #ececf1;
  border-radius: 18px;
  background: #ffffff;
}

.summary-item span {
  display: block;
  margin-bottom: 8px;
  color: #6e6e73;
  font-size: 12px;
}

.summary-item strong {
  display: block;
  overflow-wrap: anywhere;
  color: #37352f;
  line-height: 1.55;
  font-size: 18px;
}

.radar-head small {
  color: #6e6e73;
  font-size: 12px;
  line-height: 1.6;
}

.radar {
  height: 280px;
}

@media (max-width: 1180px) {
  .profile-page,
  .profile-page.landing {
  grid-template-columns: 1fr;
}

.profile-page.summaryOnly {
  grid-template-columns: 1fr;
  justify-content: stretch;
}
}

@media (max-width: 760px) {
  .landing-composer {
    grid-template-columns: 1fr;
    border-radius: 20px;
  }

  .landing-actions {
    justify-content: flex-end;
  }

  .summary-grid {
    grid-template-columns: 1fr;
  }

  .composer-bar {
    flex-direction: column;
    align-items: stretch;
  }

  .action-buttons {
    justify-content: flex-start;
  }
}
</style>




