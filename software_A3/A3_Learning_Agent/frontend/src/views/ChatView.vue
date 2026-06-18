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
          <video v-if="item.video" controls :src="item.video" class="video"></video>
        </div>
      </div>
      <el-progress v-if="loading" :percentage="progress" striped striped-flow />
      <div class="input-line">
        <el-input v-model="question" type="textarea" :rows="3" placeholder="请输入人工智能导论课程问题，例如：什么是监督学习？" />
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
const question = ref("监督学习和无监督学习有什么区别？");
const needVideo = ref(false);
const loading = ref(false);
const progress = ref(0);
const messages = ref([{ role: "assistant", content: "我是人工智能导论多模态答疑助手，会先检索课程知识库，再基于讯飞星火生成回答。" }]);

function renderMarkdown(text) {
  return md.render(String(text || ""));
}

async function ask() {
  if (!question.value.trim()) return;
  loading.value = true;
  progress.value = 10;
  messages.value.push({ role: "user", content: question.value });
  const timer = setInterval(() => { progress.value = Math.min(progress.value + 7, 94); }, 500);
  try {
    const res = await chatApi.answer({ question: question.value, need_video: needVideo.value });
    if (res.code === 200) {
      messages.value.push({ role: "assistant", content: res.data.answer, video: res.data.video_url });
      question.value = "";
    } else {
      ElMessage.error(res.msg);
    }
  } finally {
    clearInterval(timer);
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

.video {
  width: 100%;
  margin-top: 12px;
  border-radius: 12px;
}
</style>
