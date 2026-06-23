<template>
  <div class="page chat-page">
    <el-card class="panel chat-card">
      <template #header>
        <div class="header-line">
          <span>多模态智能答疑</span>
          <el-switch v-model="needVideo" active-text="生成短视频" />
        </div>
      </template>
      <div class="chat-window">
        <div v-for="(item, index) in messages" :key="index" :class="['bubble', item.role]">
          <div class="markdown-body" v-html="renderMarkdown(item.content)"></div>
          <div v-if="item.sources?.length" class="source-list">
            <strong>参考来源</strong>
            <el-tag v-for="source in item.sources" :key="`${source.source}-${source.chunk_index}`" size="small">
              {{ source.source }} #{{ source.chunk_index }}
            </el-tag>
          </div>
          <video v-if="item.video && isPlayableVideo(item.video)" controls :src="item.video" class="video"></video>
        </div>
      </div>
      <el-progress v-if="loading" :percentage="progress" striped striped-flow />
      <el-steps v-if="loading" :active="activeStep" finish-status="success" simple>
        <el-step title="检索知识库" />
        <el-step title="生成回答" />
        <el-step title="安全复核" />
      </el-steps>
      <div class="input-line">
        <el-input v-model="question" type="textarea" :rows="3" placeholder="请输入软件工程课程问题，例如：需求分析和总体设计有什么区别？" />
        <el-button type="primary" :loading="loading" @click="ask">提问</el-button>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import MarkdownIt from "markdown-it";
import { ref } from "vue";
import { ElMessage } from "element-plus";
import { chatApi } from "../api";

const md = new MarkdownIt({ html: true, linkify: true, breaks: true });
const question = ref("需求分析和总体设计有什么区别？");
const needVideo = ref(false);
const loading = ref(false);
const progress = ref(0);
const activeStep = ref(0);
const messages = ref([{ role: "assistant", content: "我是软件工程课程多模态答疑助手，会先检索课程知识库，再基于讯飞星火生成回答，并进行防幻觉复核。" }]);

function renderMarkdown(text) {
  return md.render(String(text || ""));
}

function isPlayableVideo(text) {
  return /^https?:\/\//.test(String(text || "")) && !String(text).includes("example.com");
}

function typewriter(target, fullText) {
  target.content = "";
  let index = 0;
  const timer = setInterval(() => {
    target.content += fullText.slice(index, index + 6);
    index += 6;
    if (index >= fullText.length) clearInterval(timer);
  }, 18);
}

async function ask() {
  if (!question.value.trim()) return;
  loading.value = true;
  progress.value = 10;
  activeStep.value = 0;
  messages.value.push({ role: "user", content: question.value });
  const assistantMsg = { role: "assistant", content: "正在检索课程知识库并生成可信回答...", sources: [] };
  messages.value.push(assistantMsg);
  const timer = setInterval(() => {
    progress.value = Math.min(progress.value + 7, 94);
    activeStep.value = progress.value > 65 ? 2 : progress.value > 35 ? 1 : 0;
  }, 500);
  try {
    const res = await chatApi.answer({ question: question.value, need_video: needVideo.value });
    if (res.code === 200) {
      assistantMsg.sources = res.data.sources || [];
      assistantMsg.video = res.data.video_url;
      typewriter(assistantMsg, res.data.answer);
      question.value = "";
    } else {
      assistantMsg.content = res.msg || "答疑失败";
      ElMessage.error(res.msg);
    }
  } finally {
    clearInterval(timer);
    activeStep.value = 3;
    progress.value = 100;
    loading.value = false;
  }
}
</script>

<style scoped>
.chat-page {
  display: grid;
}

.chat-card :deep(.el-card__body) {
  display: flex;
  height: calc(100vh - 190px);
  flex-direction: column;
  gap: 14px;
}

.header-line,
.input-line {
  display: flex;
  align-items: center;
  gap: 14px;
  justify-content: space-between;
}

.chat-window {
  flex: 1;
  overflow: auto;
  padding: 18px;
  border-radius: 18px;
  background: #f8fafc;
}

.bubble {
  max-width: 78%;
  margin-bottom: 14px;
  padding: 14px 16px;
  border-radius: 16px;
}

.bubble.assistant {
  background: #fff;
  border: 1px solid #dbeafe;
}

.bubble.user {
  margin-left: auto;
  background: #dbeafe;
}

.source-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px dashed #cbd5e1;
}

.video {
  width: 100%;
  margin-top: 12px;
  border-radius: 12px;
}
</style>
