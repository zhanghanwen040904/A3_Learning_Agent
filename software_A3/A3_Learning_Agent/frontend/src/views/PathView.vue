<template>
  <div class="page">
    <el-card class="panel">
      <template #header>
        <div class="header-line">
          <span>个性化学习路径</span>
          <el-button type="primary" :loading="loading" @click="generatePath">生成学习路径</el-button>
        </div>
      </template>
      <el-progress v-if="loading" :percentage="progress" striped striped-flow />
      <el-timeline class="timeline">
        <el-timeline-item v-for="(item, index) in paths" :key="item.id || index" :timestamp="item.create_time || '刚刚生成'" placement="top">
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

const md = new MarkdownIt({ html: true, linkify: true, breaks: true });
const loading = ref(false);
const progress = ref(0);
const paths = ref([]);

function renderMarkdown(text) {
  return md.render(String(text || ""));
}

async function loadPaths() {
  const res = await pathApi.list();
  if (res.code === 200) paths.value = res.data || [];
}

async function generatePath() {
  loading.value = true;
  progress.value = 12;
  const timer = setInterval(() => { progress.value = Math.min(progress.value + 8, 95); }, 600);
  try {
    const res = await pathApi.generate();
    if (res.code === 200) {
      paths.value.unshift(res.data);
      ElMessage.success("学习路径生成成功");
    } else {
      ElMessage.error(res.msg);
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
}

.timeline {
  margin-top: 22px;
}
</style>
