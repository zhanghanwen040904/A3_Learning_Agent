<template>
  <div class="page profile-grid">
    <el-card class="panel chat-panel">
      <template #header>对话式免表单画像构建</template>
      <div class="messages">
        <div v-for="(item, index) in messages" :key="index" :class="['msg', item.role]">
          {{ item.content }}
        </div>
      </div>
      <el-input v-model="dialogue" type="textarea" :rows="5" placeholder="请用自然语言描述你的专业、学习目标、薄弱点、时间偏好等" />
      <el-button type="primary" :loading="loading" @click="createProfile">生成6维画像</el-button>
      <el-progress v-if="loading" :percentage="progress" striped striped-flow />
    </el-card>

    <el-card class="panel">
      <template #header>6维学生画像雷达图</template>
      <div ref="chartRef" class="radar"></div>
      <el-descriptions :column="1" border>
        <el-descriptions-item v-for="field in fields" :key="field.key" :label="field.label">
          {{ profile[field.key] || "待生成" }}
        </el-descriptions-item>
      </el-descriptions>
    </el-card>
  </div>
</template>

<script setup>
import { nextTick, onMounted, reactive, ref } from "vue";
import * as echarts from "echarts";
import { ElMessage } from "element-plus";
import { profileApi } from "../api";

const loading = ref(false);
const progress = ref(0);
const dialogue = ref("我是人工智能专业学生，目前机器学习基础一般，容易混淆监督学习和无监督学习，希望两周内补齐核心概念，喜欢案例和代码，晚上学习效率更高。");
const chartRef = ref(null);
const profile = reactive({});
const messages = ref([{ role: "assistant", content: "请直接描述你的学习情况，我会自动抽取6维动态画像。" }]);
const fields = [
  { key: "knowledge_level", label: "知识基础" },
  { key: "study_style", label: "学习风格" },
  { key: "weak_points", label: "薄弱知识点" },
  { key: "study_goal", label: "学习目标" },
  { key: "study_time_prefer", label: "时间偏好" },
  { key: "course_progress", label: "课程进度" },
];

function drawRadar() {
  if (!chartRef.value) return;
  const chart = echarts.init(chartRef.value);
  chart.setOption({
    tooltip: {},
    radar: { indicator: fields.map((item) => ({ name: item.label, max: 100 })) },
    series: [{ type: "radar", data: [{ value: fields.map((item) => (profile[item.key] ? 78 : 20)), name: "画像完整度" }] }],
  });
}

async function createProfile() {
  loading.value = true;
  progress.value = 15;
  messages.value.push({ role: "user", content: dialogue.value });
  const timer = setInterval(() => { progress.value = Math.min(progress.value + 8, 92); }, 500);
  try {
    const res = await profileApi.create({ dialogue: dialogue.value });
    if (res.code === 200) {
      Object.assign(profile, res.data);
      messages.value.push({ role: "assistant", content: "画像已生成并持久化到数据库。" });
      await nextTick();
      drawRadar();
      ElMessage.success("画像生成成功");
    } else {
      ElMessage.error(res.msg);
    }
  } finally {
    clearInterval(timer);
    progress.value = 100;
    loading.value = false;
  }
}

onMounted(drawRadar);
</script>

<style scoped>
.profile-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 24px;
}

.chat-panel :deep(.el-card__body) {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.messages {
  height: 300px;
  overflow: auto;
  padding: 16px;
  border-radius: 16px;
  background: #f8fafc;
}

.msg {
  margin-bottom: 12px;
  padding: 12px 14px;
  border-radius: 14px;
}

.msg.assistant { background: #e0f2fe; }
.msg.user { background: #eef2ff; }
.radar { height: 320px; }
</style>
