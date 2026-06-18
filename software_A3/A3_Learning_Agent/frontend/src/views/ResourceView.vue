<template>
  <div class="page">
    <el-card class="panel">
      <template #header>
        <div class="header-line">
          <span>多智能体资源生成</span>
          <el-button type="primary" :loading="loading" @click="generate">生成6类学习资源</el-button>
        </div>
      </template>
      <el-progress v-if="loading" :percentage="progress" striped striped-flow />
      <div class="cards">
        <el-card
          v-for="item in resources"
          :key="`${item.resource_type}-${item.title}`"
          shadow="hover"
          :class="['resource-card', `resource-${item.resource_type}`]"
        >
          <template #header>
            <div class="header-line">
              <span>{{ item.title }}</span>
              <el-tag>{{ item.resource_type }}</el-tag>
            </div>
          </template>

          <template v-if="item.resource_type === 'video'">
            <div v-if="isPlayableVideo(item.content)" class="video-box">
              <video controls :src="item.content" class="video"></video>
            </div>
            <el-empty v-else description="MOCK模式下仅返回视频链接，真实SeeDance接入后可在线播放">
              <el-link v-if="isUrl(item.content)" :href="item.content" target="_blank" type="primary">查看视频链接</el-link>
              <p v-else class="muted">{{ item.content || "暂无视频地址" }}</p>
            </el-empty>
          </template>

          <template v-else-if="item.resource_type === 'code'">
            <div class="code-toolbar">
              <span>Python 实操案例</span>
              <el-button size="small" type="primary" plain @click="copyCode(item.content)">复制代码</el-button>
            </div>
            <pre class="code-block"><code>{{ item.content }}</code></pre>
          </template>

          <div v-else class="markdown-body" v-html="renderMarkdown(item.content)"></div>
        </el-card>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import MarkdownIt from "markdown-it";
import { onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import { resourceApi } from "../api";

const md = new MarkdownIt({ html: true, linkify: true, breaks: true });
const loading = ref(false);
const progress = ref(0);
const resources = ref([]);

function renderMarkdown(text) {
  return md.render(String(text || ""));
}

function isUrl(text) {
  return /^https?:\/\//.test(String(text || ""));
}

function isPlayableVideo(text) {
  return isUrl(text) && !String(text).includes("example.com");
}

async function copyCode(code) {
  try {
    await navigator.clipboard.writeText(String(code || ""));
    ElMessage.success("代码已复制");
  } catch (error) {
    ElMessage.warning("浏览器不支持自动复制，请手动选择代码复制");
  }
}

async function loadResources() {
  const res = await resourceApi.list();
  if (res.code === 200) resources.value = res.data || [];
}

async function generate() {
  loading.value = true;
  progress.value = 10;
  const timer = setInterval(() => { progress.value = Math.min(progress.value + 6, 95); }, 700);
  try {
    const res = await resourceApi.generate();
    if (res.code === 200) {
      resources.value = res.data.resource_list || [];
      ElMessage.success("资源生成完成");
    } else {
      ElMessage.error(res.msg);
    }
  } finally {
    clearInterval(timer);
    progress.value = 100;
    loading.value = false;
  }
}

onMounted(loadResources);
</script>

<style scoped>
.header-line {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.cards {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 18px;
  margin-top: 18px;
}

.resource-card {
  min-height: 260px;
}

.resource-code {
  grid-column: span 2;
}

.resource-video {
  display: flex;
  flex-direction: column;
}

.video-box {
  overflow: hidden;
  border-radius: 12px;
  background: #0f172a;
}

.video {
  width: 100%;
  border-radius: 12px;
}

.code-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
  color: #475569;
  font-size: 13px;
}

.code-block {
  max-height: 520px;
  overflow: auto;
  margin: 0;
  padding: 16px;
  border-radius: 14px;
  background: #0f172a;
  color: #e2e8f0;
  font-family: "JetBrains Mono", Consolas, monospace;
  font-size: 13px;
  line-height: 1.7;
  white-space: pre;
}

.muted {
  color: #64748b;
}
</style>
