<template>
  <div class="page architecture-page">
    <el-card class="hero-card">
      <div class="hero">
        <div>
          <el-tag type="primary" effect="dark">A3 赛题对标</el-tag>
          <h1>多智能体协同学习系统</h1>
          <p>
            系统围绕《人工智能导论》课程知识库，将学生画像、RAG 检索、资源生成、学习路径、智能答疑、学习评估和安全复核组织为可解释的多智能体工作流。
          </p>
        </div>
        <div class="score-box">
          <strong>15</strong>
          <span>个协作智能体</span>
        </div>
      </div>
    </el-card>

    <el-row :gutter="18">
      <el-col v-for="item in scoreItems" :key="item.title" :span="6">
        <el-card class="metric-card" shadow="hover">
          <strong>{{ item.value }}</strong>
          <span>{{ item.title }}</span>
          <p>{{ item.desc }}</p>
        </el-card>
      </el-col>
    </el-row>

    <el-card class="panel">
      <template #header>多智能体协同流程</template>
      <el-steps :active="8" finish-status="success" align-center>
        <el-step title="画像构建" description="ProfileAgent" />
        <el-step title="课程检索" description="RetrieveAgent" />
        <el-step title="资源规划" description="PlannerAgent" />
        <el-step title="六类生成" description="6 Resource Agents" />
        <el-step title="质量返工" description="QualityAgent" />
        <el-step title="安全复核" description="SafetyAgent" />
        <el-step title="结果编排" description="PackagerAgent" />
        <el-step title="路径规划" description="PathAgent" />
        <el-step title="答疑辅导" description="TutorAgent" />
        <el-step title="评估反馈" description="EvaluatorAgent" />
      </el-steps>
    </el-card>

    <el-card class="panel">
      <template #header>智能体角色矩阵</template>
      <el-table :data="agents" border>
        <el-table-column prop="name" label="智能体" width="180" />
        <el-table-column prop="role" label="角色" width="210" />
        <el-table-column prop="input" label="输入" />
        <el-table-column prop="output" label="输出" />
        <el-table-column prop="value" label="赛题价值" />
      </el-table>
    </el-card>

    <el-card class="panel">
      <template #header>赛题要求对应关系</template>
      <el-timeline>
        <el-timeline-item v-for="item in requirements" :key="item.title" :type="item.done ? 'success' : 'primary'">
          <h3>{{ item.title }}</h3>
          <p>{{ item.desc }}</p>
          <el-tag v-for="tag in item.tags" :key="tag" class="tag" type="success">{{ tag }}</el-tag>
        </el-timeline-item>
      </el-timeline>
    </el-card>
  </div>
</template>

<script setup>
const scoreItems = [
  { title: "创新价值与实用性", value: "35%", desc: "多智能体 + RAG + 学习闭环，面向高校课程真实痛点。" },
  { title: "功能实现", value: "45%", desc: "画像、资源、路径、答疑、评估、内容安全全部落地。" },
  { title: "配套文档", value: "10%", desc: "需求、开发、测试、部署、开源协议、AI工具说明齐备。" },
  { title: "演示材料", value: "10%", desc: "PPT 大纲、演示脚本和固定演示输入可直接用于录制。" },
];

const agents = [
  { name: "ProfileAgent", role: "学习画像分析师", input: "自然语言对话、学习历史", output: "六维动态画像", value: "满足对话式学习画像构建" },
  { name: "RetrieveAgent", role: "课程知识检索员", input: "学生目标、薄弱点", output: "教材片段与引用来源", value: "支撑 RAG 防幻觉" },
  { name: "PlannerAgent", role: "个性化资源总规划师", input: "结构化画像 + RAG来源", output: "主题、难度、六类任务计划", value: "证明资源生成前存在协同规划" },
  { name: "DocumentAgent", role: "课程讲解文档生成师", input: "统一上下文 + 独立任务", output: "递进式课程讲解", value: "生成专业课程文档" },
  { name: "QuizAgent", role: "分层练习设计师", input: "画像 + 知识点", output: "基础/提升/应用练习", value: "生成题库资源" },
  { name: "ReadingAgent", role: "前沿拓展阅读策展师", input: "课程知识 + 专业目标", output: "导读、问题链、探索方向", value: "生成可信拓展阅读" },
  { name: "MindMapAgent", role: "知识可视化设计师", input: "薄弱点 + 教材片段", output: "可渲染Mermaid思维导图", value: "生成真实可视化资源" },
  { name: "CodeAgent", role: "代码实操案例生成师", input: "课程知识点", output: "Python 实操案例", value: "生成实践项目材料" },
  { name: "VideoAgent", role: "多模态视频脚本生成师", input: "知识点讲解", output: "短视频/动画生成任务", value: "支撑多模态资源" },
  { name: "QualityAgent", role: "学习资源质量评估师", input: "资源 + 画像 + 来源", output: "四维评分与返工意见", value: "建立生成—评价—返工闭环" },
  { name: "PackagerAgent", role: "资源结果编排师", input: "六类合格资源", output: "统一可审计结果包", value: "形成协作链路证据" },
  { name: "PathAgent", role: "学习路径规划师", input: "画像 + 掌握度 + 资源", output: "动态学习路径", value: "实现精准资源推送" },
  { name: "TutorAgent", role: "智能辅导老师", input: "学生问题", output: "文字答疑、图解、自测题", value: "实现智能辅导加分项" },
  { name: "EvaluatorAgent", role: "学习效果评估师", input: "练习答案、学习行为", output: "得分、反馈、掌握度", value: "实现评估闭环加分项" },
  { name: "SafetyAgent", role: "安全与防幻觉复核员", input: "生成内容 + 来源", output: "风险提示、引用核验", value: "满足内容安全要求" },
];

const requirements = [
  { title: "对话式学习画像自主构建", desc: "通过自然语言对话抽取知识基础、认知风格、薄弱点、学习目标、时间偏好、课程进度等不少于 6 个维度，并在评估后更新画像。", tags: ["ProfileAgent", "动态画像"], done: true },
  { title: "多智能体协同资源生成", desc: "PlannerAgent先规划，六个独立专业智能体并行生成六类资源，QualityAgent评分并触发返工，最终形成可审计资源包。", tags: ["PlannerAgent", "6 Resource Agents", "QualityAgent", "PackagerAgent"], done: true },
  { title: "个性化学习路径规划和资源推送", desc: "结合画像、知识短板、掌握度和课程资源，生成阶段化学习步骤与资源推荐。", tags: ["PathAgent", "Mastery"], done: true },
  { title: "智能辅导", desc: "基于课程知识库进行即时答疑，输出文字解释、图解说明、自测题和来源引用。", tags: ["TutorAgent", "RAG"], done: true },
  { title: "学习效果评估", desc: "记录练习作答、评分反馈、掌握度和学习事件，并动态调整画像与学习建议。", tags: ["EvaluatorAgent", "Learning Event"], done: true },
  { title: "防幻觉与内容安全", desc: "RAG 课程依据、来源展示、关键词降级检索、讯飞内容审核和 SafetyAgent 复核。", tags: ["SafetyAgent", "Content Audit"], done: true },
];
</script>

<style scoped>
.architecture-page {
  display: grid;
  gap: 18px;
}
.hero-card {
  overflow: hidden;
}
.hero {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  padding: 10px;
}
.hero h1 {
  margin: 12px 0;
  font-size: 34px;
}
.hero p {
  max-width: 860px;
  color: #475569;
  line-height: 1.8;
}
.score-box {
  display: grid;
  min-width: 160px;
  height: 160px;
  place-items: center;
  border-radius: 36px;
  color: white;
  background: linear-gradient(135deg, #2563eb, #06b6d4);
}
.score-box strong {
  font-size: 54px;
  line-height: 1;
}
.score-box span {
  margin-top: -30px;
}
.metric-card {
  min-height: 150px;
}
.metric-card strong {
  display: block;
  font-size: 34px;
  color: #2563eb;
}
.metric-card span {
  display: block;
  margin-top: 6px;
  font-weight: 700;
}
.metric-card p {
  color: #64748b;
  line-height: 1.7;
}
.tag {
  margin-right: 8px;
  margin-top: 8px;
}
</style>
