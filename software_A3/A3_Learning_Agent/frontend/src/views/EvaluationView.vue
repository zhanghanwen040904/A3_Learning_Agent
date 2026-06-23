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

      <el-alert class="loop-alert" type="success" :closable="false" show-icon>
        <template #title><strong>学习闭环状态</strong></template>
        {{ loopSummary }}
      </el-alert>
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
        <el-button :loading="pathLoading" @click="regeneratePath">根据评估结果重规划路径</el-button>
      </el-form>
    </el-card>

    <el-card v-if="latestResult" class="panel result-panel">
      <template #header>
        <div class="header-line">
          <span>本次评估反馈</span>
          <el-tag :type="latestResult.score >= 80 ? 'success' : latestResult.score >= 60 ? 'warning' : 'danger'">{{ latestResult.score }} 分</el-tag>
        </div>
      </template>
      <div class="result-grid">
        <div class="result-score">
          <el-progress type="dashboard" :percentage="Number(latestResult.score || 0)" />
          <strong>{{ latestResult.score >= 80 ? "掌握较好" : latestResult.score >= 60 ? "需要巩固" : "优先补弱" }}</strong>
        </div>
        <div>
          <h3>EvaluatorAgent 反馈</h3>
          <p>{{ latestResult.feedback }}</p>
          <el-alert v-if="Object.keys(latestResult.profile_update || {}).length" type="warning" :closable="false" show-icon>
            <template #title><strong>画像已随学更新</strong></template>
            {{ profileUpdateText(latestResult.profile_update) }}
          </el-alert>
        </div>
      </div>
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
          <template #header>
            <div class="header-line">
              <span>下一步学习任务</span>
              <el-button link type="primary" :loading="pathLoading" @click="regeneratePath">更新路径</el-button>
            </div>
          </template>
          <el-timeline>
            <el-timeline-item v-for="(item, index) in summary.next_tasks || []" :key="index">{{ item }}</el-timeline-item>
          </el-timeline>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import { evaluationApi, pathApi } from "../api";

const summary = reactive({ mastery: [], weak_points: [], next_tasks: [] });
const loading = ref(false);
const submitting = ref(false);
const pathLoading = ref(false);
const latestResult = ref(null);
const form = reactive({
  knowledge_point: "需求分析",
  question: "需求分析和总体设计有什么区别？请结合在线学习系统举例说明。",
  answer: "需求分析关注用户目标、业务规则和系统边界，输出需求规格说明；总体设计把需求转化为系统架构和模块划分，例如把在线学习系统拆分为用户管理、课程资源、作业提交和学习评估等模块。",
});

const loopSummary = computed(() => {
  const weakCount = (summary.weak_points || []).length;
  if (!summary.quiz_count) return "尚未提交练习。提交答案后，系统会自动评分、更新掌握度、刷新画像薄弱点，并据此调整下一步学习任务。";
  if (weakCount) return `已根据 ${summary.quiz_count} 次练习记录识别出 ${weakCount} 个薄弱点，建议点击“根据评估结果重规划路径”生成新的学习安排。`;
  return `已完成 ${summary.quiz_count} 次练习，当前暂无明显薄弱点，可进入综合案例与项目实践阶段。`;
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
      latestResult.value = res.data;
      await loadSummary();
    } else {
      ElMessage.error(res.msg);
    }
  } finally {
    submitting.value = false;
  }
}

function profileUpdateText(update = {}) {
  return Object.entries(update).map(([key, value]) => `${fieldLabel(key)}：${value}`).join("；");
}

function fieldLabel(key) {
  return ({ weak_points: "薄弱点", course_progress: "课程进度", study_goal: "学习目标", study_style: "学习偏好" }[key] || key);
}

async function regeneratePath() {
  pathLoading.value = true;
  try {
    const res = await pathApi.generate();
    if (res.code === 200) {
      ElMessage.success("已根据最新画像和掌握度重新生成学习路径，请到学习路径页面查看");
      await loadSummary();
    } else {
      ElMessage.error(res.msg || "学习路径重规划失败，请先确认已生成学生画像");
    }
  } finally {
    pathLoading.value = false;
  }
}

onMounted(loadSummary);
</script>

<style scoped>
.evaluation-page {
  display: grid;
  gap: 18px;
}
.loop-alert {
  margin-top: 18px;
}
.result-panel {
  border-color: rgba(37, 99, 235, 0.18);
  background: linear-gradient(135deg, #ffffff, #f8fbff);
}
.result-grid {
  display: grid;
  grid-template-columns: 180px 1fr;
  gap: 22px;
  align-items: center;
}
.result-score {
  display: grid;
  justify-items: center;
  gap: 8px;
}
.result-grid h3 {
  margin: 0 0 10px;
}
.result-grid p {
  color: #475569;
  line-height: 1.8;
}
.header-line {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
</style>
