<template>
  <div class="page evaluation-page">
    <el-card class="panel">
      <template #header>
        <div class="header-line">
          <span>学习效果评估</span>
          <el-button :loading="loading" @click="loadSummary">刷新评估</el-button>
        </div>
      </template>

      <el-row :gutter="18">
        <el-col :span="8"><el-statistic title="平均得分" :value="summary.avg_score || 0" suffix="分" /></el-col>
        <el-col :span="8"><el-statistic title="练习次数" :value="summary.quiz_count || 0" /></el-col>
        <el-col :span="8"><el-statistic title="薄弱点数量" :value="(summary.weak_points || []).length" /></el-col>
      </el-row>
    </el-card>

    <el-card class="panel">
      <template #header>提交练习答案</template>
      <el-form label-position="top">
        <el-form-item label="知识点">
          <el-input v-model="form.knowledge_point" />
        </el-form-item>
        <el-form-item label="题目">
          <el-input v-model="form.question" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="我的答案">
          <el-input v-model="form.answer" type="textarea" :rows="4" />
        </el-form-item>
        <el-button type="primary" :loading="submitting" @click="submit">提交并评估</el-button>
      </el-form>
    </el-card>

    <el-row :gutter="18">
      <el-col :span="12">
        <el-card class="panel">
          <template #header>知识点掌握度</template>
          <el-table :data="summary.mastery || []" border>
            <el-table-column prop="knowledge_point" label="知识点" />
            <el-table-column prop="mastery_score" label="掌握度" width="120">
              <template #default="scope">
                <el-progress :percentage="Number(scope.row.mastery_score || 0)" />
              </template>
            </el-table-column>
            <el-table-column prop="weak_reason" label="建议" />
          </el-table>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card class="panel">
          <template #header>下一步学习任务</template>
          <el-timeline>
            <el-timeline-item v-for="(item, index) in summary.next_tasks || []" :key="index">{{ item }}</el-timeline-item>
          </el-timeline>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import { evaluationApi } from "../api";

const summary = reactive({ mastery: [], weak_points: [], next_tasks: [] });
const loading = ref(false);
const submitting = ref(false);
const form = reactive({
  knowledge_point: "监督学习",
  question: "监督学习和无监督学习有什么区别？",
  answer: "监督学习使用带标签数据，常见任务包括分类和回归；无监督学习处理无标签数据，常见任务包括聚类和降维。",
});

async function loadSummary() {
  loading.value = true;
  try {
    const res = await evaluationApi.summary();
    if (res.code === 200) Object.assign(summary, res.data);
  } finally {
    loading.value = false;
  }
}

async function submit() {
  submitting.value = true;
  try {
    const res = await evaluationApi.submit(form);
    if (res.code === 200) {
      ElMessage.success(`评估完成：${res.data.score}分`);
      await loadSummary();
    } else {
      ElMessage.error(res.msg);
    }
  } finally {
    submitting.value = false;
  }
}

onMounted(loadSummary);
</script>

<style scoped>
.evaluation-page {
  display: grid;
  gap: 18px;
}
.header-line {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
</style>
