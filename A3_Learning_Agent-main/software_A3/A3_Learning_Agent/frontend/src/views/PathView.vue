<template>
  <div class="page">
    <el-card class="panel">
      <template #header>
        <div class="header-line">
          <div>
            <strong>个性化学习路径</strong>
            <p>学习路径会跟随当前画像对话框自动切换。新建画像或重新开始后，这里会先保持空白。</p>
          </div>
          <el-button type="primary" :loading="loading" @click="generatePath">生成学习路径</el-button>
        </div>
      </template>

      <el-progress v-if="loading" :percentage="progress" striped striped-flow />

      <el-empty
        v-if="!loading && !paths.length"
        description="当前画像还没有学习路径。请先生成当前画像，再点击生成学习路径。"
      />

      <el-timeline v-else class="timeline">
        <el-timeline-item
          v-for="(item, index) in paths"
          :key="item.id || index"
          :timestamp="item.create_time || '刚刚生成'"
          placement="top"
        >
          <el-card>
            <template #header>
              <div class="header-line">
                <span>学习路径 #{{ item.id || index + 1 }}</span>
                <el-tag>{{ item.status || "active" }}</el-tag>
              </div>
            </template>
            <div class="markdown-body" v-html="renderMarkdown(item.path_content)"></div>
          </el-card>
        </el-timeline-item>
      </el-timeline>
    </el-card>
  </div>
</template>

<script setup>
import MarkdownIt from "markdown-it";
import { onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import { pathApi } from "../api";

const md = new MarkdownIt({ html: false, linkify: true, breaks: true });
const loading = ref(false);
const progress = ref(0);
const paths = ref([]);

function renderMarkdown(text) {
  return md.render(String(text || ""));
}

async function loadPaths() {
  const res = await pathApi.list();
  if (res.code === 200) {
    paths.value = res.data || [];
  }
}

async function generatePath() {
  loading.value = true;
  progress.value = 12;
  const timer = setInterval(() => {
    progress.value = Math.min(progress.value + 8, 95);
  }, 600);
  try {
    const res = await pathApi.generate();
    if (res.code === 200) {
      paths.value.unshift(res.data);
      ElMessage.success("学习路径生成成功");
    } else {
      ElMessage.error(res.msg || "学习路径生成失败");
    }
  } finally {
    clearInterval(timer);
    progress.value = 100;
    loading.value = false;
  }
}

onMounted(loadPaths);
</script>

<style scoped>
.header-line {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}
.header-line p {
  margin: 6px 0 0;
  color: #64748b;
  font-weight: 400;
}
.timeline {
  margin-top: 22px;
}
.markdown-body {
  line-height: 1.75;
}
.markdown-body :deep(pre) {
  overflow: auto;
  padding: 16px;
  border-radius: 12px;
  background: #0f172a;
  color: #e2e8f0;
}
</style>
