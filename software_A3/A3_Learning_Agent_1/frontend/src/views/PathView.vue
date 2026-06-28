<template>
  <div class="page path-page">
    <el-card class="panel hero-card">
      <div class="header-line">
        <div>
          <strong>个性化学习路径</strong>
          <p>学习路径会跟随当前画像会话自动切换，新建画像或重新开始后这里会先保持空白。</p>
        </div>
        <el-button type="primary" :loading="loading" @click="generatePath">生成学习路径</el-button>
      </div>

      <el-progress v-if="loading" :percentage="progress" striped striped-flow />
    </el-card>

    <el-empty
      v-if="!loading && !paths.length"
      class="panel empty-panel"
      description="当前画像还没有学习路径，请先生成画像，再点击上方按钮。"
    />

    <div v-else class="path-list">
      <el-card v-for="(item, index) in paths" :key="item.id || index" class="panel path-card">
        <template #header>
          <div class="header-line">
            <div>
              <strong>学习路径 {{ item.id || index + 1 }}</strong>
              <p>{{ item.create_time || "刚刚生成" }}</p>
            </div>
            <el-tag>{{ item.status || "active" }}</el-tag>
          </div>
        </template>
        <div class="markdown-body path-content" v-html="renderMarkdown(item.path_content)"></div>
      </el-card>
    </div>
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

function normalizeMarkdown(text) {
  let source = String(text || "").trim();
  const fenced = source.match(/^```(?:markdown|md|text)?\s*([\s\S]*?)\s*```$/i);
  if (fenced) source = fenced[1].trim();
  source = source.replace(/^\s*```(?:markdown|md|text|json)?\s*$/gim, "").replace(/^\s*```\s*$/gm, "");
  return source.trim();
}

function renderMarkdown(text) {
  return md.render(normalizeMarkdown(text));
}

async function loadPaths() {
  const res = await pathApi.list();
  if (res.code === 200) paths.value = res.data || [];
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
.path-page {
  display: grid;
  gap: 18px;
}

.header-line {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.header-line p {
  margin: 6px 0 0;
  color: #64748b;
}

.empty-panel {
  padding: 34px;
}

.path-list {
  display: grid;
  gap: 16px;
}

.path-content {
  line-height: 1.8;
  color: #0f172a;
}

.path-content :deep(h1) {
  margin: 0 0 18px;
  padding: 16px 18px;
  border: 1px solid #bfdbfe;
  border-radius: 14px;
  background: linear-gradient(135deg, #eff6ff 0%, #ffffff 100%);
  color: #1d4ed8;
  font-size: 22px;
}

.path-content :deep(h2) {
  margin: 24px 0 12px;
  padding: 12px 16px;
  border-left: 4px solid #3b82f6;
  background: #f8fbff;
  color: #0f3a78;
  font-size: 18px;
}

.path-content :deep(h3) {
  margin: 16px 0 10px;
  color: #1e40af;
  font-size: 16px;
}

.path-content :deep(ul),
.path-content :deep(ol) {
  padding-left: 22px;
}

.path-content :deep(li) {
  margin: 6px 0;
}
</style>
