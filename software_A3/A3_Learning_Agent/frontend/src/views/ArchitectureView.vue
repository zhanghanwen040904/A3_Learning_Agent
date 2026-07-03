<template>
  <div class="page agent-market-page">
    <el-card class="hero-card">
      <div class="hero">
        <div>
          <el-tag type="primary" effect="dark">Agent-Native Learning OS</el-tag>
          <h1>智能体角色市场</h1>
          <p>以学习目标为入口，将画像、检索、资源、路径、答疑、评估和安全能力封装为可协同、可追踪、可解释的智能体角色。</p>
          <div class="hero-actions">
            <el-button type="primary" @click="activeCategory = '全部'">浏览全部智能体</el-button>
            <el-button @click="workflowRef?.$el?.scrollIntoView({ behavior: 'smooth' })">查看协同工作流</el-button>
          </div>
        </div>
        <div class="command-card">
          <strong>What would you like to learn?</strong>
          <p>告诉我你的学习目标，我会调度学习画像、课程检索、资源生成、路径规划和评估智能体协同完成。</p>
          <div class="chips"><el-tag v-for="tool in tools" :key="tool" effect="plain">{{ tool }}</el-tag></div>
        </div>
      </div>
    </el-card>

    <div class="metrics">
      <el-card v-for="item in metrics" :key="item.title" class="metric" shadow="hover">
        <strong>{{ item.value }}</strong><span>{{ item.title }}</span><p>{{ item.desc }}</p>
      </el-card>
    </div>

    <el-card class="panel">
      <template #header>
        <div class="section-head"><div><strong>Agent Marketplace</strong><p>从技术架构说明升级为可感知的智能体角色中心。</p></div><el-input v-model="keyword" clearable placeholder="搜索智能体、角色或工具" /></div>
      </template>
      <div class="tabs">
        <button v-for="item in categories" :key="item" :class="{ active: activeCategory === item }" @click="activeCategory = item">{{ item }}<span>{{ countByCategory(item) }}</span></button>
      </div>
      <div class="agent-grid">
        <el-card v-for="agent in filteredAgents" :key="agent.name" class="agent-card" shadow="hover">
          <div class="agent-head"><div class="avatar">{{ agent.short }}</div><div><strong>{{ agent.name }}</strong><span>{{ agent.role }}</span></div><el-tag :type="agent.type">{{ agent.status }}</el-tag></div>
          <p>{{ agent.desc }}</p>
          <div class="io"><div><small>输入</small>{{ agent.input }}</div><div><small>输出</small>{{ agent.output }}</div></div>
          <div class="chips"><el-tag v-for="tool in agent.tools" :key="tool" size="small" effect="plain">{{ tool }}</el-tag></div>
          <div class="agent-foot"><span>{{ agent.category }}</span><el-button link type="primary" @click="selectedAgent = agent">角色详情</el-button></div>
        </el-card>
      </div>
      <el-empty v-if="!filteredAgents.length" description="未找到匹配智能体" />
    </el-card>

    <el-card ref="workflowRef" class="panel">
      <template #header><div class="section-head"><div><strong>原生智能体协同工作流</strong><p>用户只表达目标，系统自动组织多个角色完成任务拆解、工具调用、质量审核和学习反馈。</p></div><el-tag type="success" effect="dark">可审计链路</el-tag></div></template>
      <div class="workflow-grid">
        <div v-for="flow in workflows" :key="flow.title" class="workflow-card"><b>{{ flow.index }}</b><h3>{{ flow.title }}</h3><p>{{ flow.desc }}</p><div class="chips"><el-tag v-for="tag in flow.tags" :key="tag" type="success" size="small">{{ tag }}</el-tag></div></div>
      </div>
    </el-card>

    <el-card class="panel">
      <template #header>赛题能力映射</template>
      <el-timeline>
        <el-timeline-item v-for="item in requirements" :key="item.title" type="success"><h3>{{ item.title }}</h3><p>{{ item.desc }}</p><el-tag v-for="tag in item.tags" :key="tag" class="tag" type="success" effect="plain">{{ tag }}</el-tag></el-timeline-item>
      </el-timeline>
    </el-card>

    <el-dialog v-model="showDialog" width="680px" destroy-on-close>
      <template #header><div v-if="selectedAgent" class="dialog-head"><div class="avatar large">{{ selectedAgent.short }}</div><div><strong>{{ selectedAgent.name }}</strong><span>{{ selectedAgent.role }}</span></div></div></template>
      <template v-if="selectedAgent"><p class="dialog-desc">{{ selectedAgent.desc }}</p><el-descriptions :column="1" border><el-descriptions-item label="分类">{{ selectedAgent.category }}</el-descriptions-item><el-descriptions-item label="输入">{{ selectedAgent.input }}</el-descriptions-item><el-descriptions-item label="输出">{{ selectedAgent.output }}</el-descriptions-item><el-descriptions-item label="工具">{{ selectedAgent.tools.join('、') }}</el-descriptions-item><el-descriptions-item label="价值">{{ selectedAgent.value }}</el-descriptions-item></el-descriptions></template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, ref } from "vue";

const activeCategory = ref("全部");
const keyword = ref("");
const selectedAgent = ref(null);
const workflowRef = ref(null);
const showDialog = computed({ get: () => Boolean(selectedAgent.value), set: (value) => { if (!value) selectedAgent.value = null; } });
const tools = ["RAG", "Memory", "Profile", "Tools", "Audit", "Trace"];
const metrics = [
  { value: "15", title: "专业智能体", desc: "覆盖画像、检索、规划、生成、评估、安全全流程。" },
  { value: "6", title: "核心工作流", desc: "围绕学习目标自动组织多智能体协同链路。" },
  { value: "6", title: "资源角色", desc: "文档、题库、阅读、导图、代码、视频分工生成。" },
  { value: "Trace", title: "可追踪闭环", desc: "执行轨迹、来源引用和质量评分可审计。" },
];
const agents = [
  ["ProfileAgent","PA","学习画像分析师","画像与理解","自然语言对话、学习历史","六维动态画像、追问问题",["Platform LLM","Content Audit","MySQL"],"通过多轮对话抽取专业、课程、基础、薄弱点、目标和偏好，形成学习记忆。","支撑对话式画像构建。"],
  ["RetrieveAgent","RA","课程知识检索员","画像与理解","学习目标、薄弱点","教材片段、引用来源",["RAG","Vector DB"],"从课程知识库召回可信教材片段，为生成、答疑和评估提供依据。","降低幻觉，形成可信引用。"],
  ["PlannerAgent","PL","资源总规划师","资源生产","结构化画像、RAG来源","主题、难度、六类计划",["RAG","Task Planning"],"在资源生成前统一确定主题、难度、风格和各类资源分工。","证明资源生成存在协同规划。"],
  ["DocumentAgent","DA","课程文档生成师","资源生产","画像、计划、教材片段","递进式课程讲解",["Platform LLM","RAG"],"生成学习目标、概念讲解、案例、易错点和自测问题。","生成可直接学习的课程文档。"],
  ["QuizAgent","QA","分层练习设计师","资源生产","画像、知识点","基础/提升/应用练习",["Platform LLM","Rubric"],"围绕薄弱点设计分层题目、参考答案和解析。","构建练习资源和评估入口。"],
  ["ReadingAgent","RD","拓展阅读策展师","资源生产","课程知识、专业目标","导读、问题链、探索方向",["Platform LLM","RAG"],"组织可信拓展阅读，连接课程知识、专业场景与前沿应用。","提升资源广度。"],
  ["MindMapAgent","MM","知识可视化设计师","资源生产","薄弱点、教材片段","Mermaid思维导图",["Mermaid","Platform LLM"],"把概念、原理、步骤、案例和易错点组织成可渲染知识结构图。","提供可视化支架。"],
  ["CodeAgent","CA","代码实操生成师","资源生产","课程知识点","Python实操案例",["Python Check","Platform LLM"],"将抽象原理转化为代码实验案例。","支撑实践型学习。"],
  ["VideoAgent","VA","视频脚本生成师","资源生产","知识点讲解","短视频脚本、分镜任务",["SeeDance","Script"],"组织短视频讲解脚本、画面建议和多模态生成任务。","支撑多模态资源。"],
  ["QualityAgent","QG","资源质量评估师","质量与安全","资源、画像、来源","评分、问题、返工意见",["Content Audit","Syntax Check"],"从准确性、个性化、完整性和来源支撑评估资源。","形成生成—评价—返工闭环。"],
  ["SafetyAgent","SA","安全复核员","质量与安全","内容、来源","风险提示、引用核验",["Content Audit","Source Check"],"对敏感内容、无依据结论和潜在幻觉进行复核。","增强可信与安全。"],
  ["PathAgent","PG","学习路径规划师","路径与评估","画像、掌握度、资源","阶段化学习路径",["Mastery","Ranking"],"生成学习步骤、节奏安排和资源推荐。","实现个性化路径。"],
  ["EvaluatorAgent","EA","学习效果评估师","路径与评估","答案、学习行为","得分、反馈、掌握度",["Rubric","Learning Event"],"评分反馈、记录事件并更新知识点掌握度。","完成评估闭环。"],
  ["TutorAgent","TA","智能辅导老师","答疑与反馈","学生问题、知识库","解释、图解、自测、来源",["RAG","Platform LLM"],"基于课程知识库即时答疑并给出进一步练习建议。","提供智能辅导。"],
  ["PackagerAgent","PK","资源结果编排师","答疑与反馈","合格资源、质量结果","统一资源包、协作证据",["Trace","Metadata"],"把多智能体结果组织为可展示、可追踪、可审计的资源集合。","便于展示协作链路。","概念组件","info"],
].map((item) => ({ name: item[0], short: item[1], role: item[2], category: item[3], input: item[4], output: item[5], tools: item[6], desc: item[7], value: item[8], status: item[9] || "已启用", type: item[10] || "success" }));
const categories = computed(() => ["全部", ...new Set(agents.map((agent) => agent.category))]);
const filteredAgents = computed(() => agents.filter((agent) => {
  const text = keyword.value.trim().toLowerCase();
  const hit = [agent.name, agent.role, agent.category, agent.desc, agent.tools.join(" ")].join(" ").toLowerCase().includes(text);
  return (activeCategory.value === "全部" || activeCategory.value === agent.category) && (!text || hit);
}));
const workflows = [
  { index: "01", title: "画像记忆构建", desc: "从自然语言对话抽取画像，沉淀为共享上下文。", tags: ["ProfileAgent", "Memory"] },
  { index: "02", title: "RAG可信检索", desc: "围绕目标和薄弱点召回教材片段。", tags: ["RetrieveAgent", "RAG"] },
  { index: "03", title: "多角色资源生产", desc: "规划、六类生成、质量评分与返工。", tags: ["PlannerAgent", "Resource Agents", "QualityAgent"] },
  { index: "04", title: "学习路径规划", desc: "结合画像、掌握度和资源生成学习路线。", tags: ["PathAgent", "Mastery"] },
  { index: "05", title: "智能导师答疑", desc: "基于知识库输出解释、自测和来源。", tags: ["TutorAgent", "RAG"] },
  { index: "06", title: "学习评估闭环", desc: "记录答案、行为和反馈并更新掌握度。", tags: ["EvaluatorAgent", "Learning Event"] },
];
const requirements = [
  { title: "对话式学习画像自主构建", desc: "通过自然语言对话抽取多维画像并持续更新。", tags: ["ProfileAgent", "Memory"] },
  { title: "多智能体协同资源生成", desc: "规划、六类资源生成、质量审核和返工形成闭环。", tags: ["PlannerAgent", "6 Resource Agents", "QualityAgent"] },
  { title: "个性化学习路径规划和资源推送", desc: "结合画像、掌握度和课程资源生成阶段化路径。", tags: ["PathAgent", "Mastery"] },
  { title: "智能辅导", desc: "基于课程知识库进行即时答疑并展示来源。", tags: ["TutorAgent", "RAG"] },
  { title: "学习效果评估", desc: "记录练习作答、评分反馈、掌握度和学习事件。", tags: ["EvaluatorAgent", "Learning Event"] },
  { title: "防幻觉与内容安全", desc: "通过来源核验、内容审核和安全复核提升可信度。", tags: ["SafetyAgent", "Content Audit"] },
];
function countByCategory(category) { return category === "全部" ? agents.length : agents.filter((agent) => agent.category === category).length; }
</script>

<style scoped>
.agent-market-page { display: grid; gap: 20px; }
.hero-card { border: none; border-radius: 28px; background: radial-gradient(circle at 82% 18%, rgba(96,165,250,.24), transparent 28%), linear-gradient(135deg,#fff,#f8fbff 54%,#eef6ff); box-shadow: 0 22px 70px rgba(15,23,42,.1); }
.hero { display: grid; grid-template-columns: 1.2fr .8fr; gap: 34px; align-items: center; padding: 18px; }
.hero h1 { margin: 16px 0 12px; font-size: 42px; letter-spacing: -.04em; }
.hero p, .metric p, .section-head p, .agent-card p, .workflow-card p, .dialog-desc { color: #64748b; line-height: 1.75; }
.hero-actions { display: flex; gap: 12px; margin-top: 24px; }
.command-card { padding: 28px; border: 1px solid #e2e8f0; border-radius: 30px; background: rgba(255,255,255,.86); box-shadow: 0 24px 64px rgba(37,99,235,.12); }
.command-card strong { font-size: 25px; }
.chips { display: flex; flex-wrap: wrap; gap: 8px; }
.metrics { display: grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap: 18px; }
.metric { min-height: 150px; border-radius: 22px; }
.metric strong { display: block; color: #2563eb; font-size: 34px; }
.metric span { display: block; margin-top: 8px; font-weight: 800; }
.section-head { display: flex; align-items: center; justify-content: space-between; gap: 18px; }
.section-head .el-input { width: 320px; }
.tabs { display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 18px; }
.tabs button { display: inline-flex; gap: 8px; align-items: center; padding: 10px 14px; border: 1px solid #dbeafe; border-radius: 999px; color: #2563eb; background: #fff; cursor: pointer; }
.tabs button span { min-width: 24px; padding: 3px 7px; border-radius: 999px; background: #eff6ff; font-size: 12px; }
.tabs button.active { color: #fff; border-color: #2563eb; background: linear-gradient(135deg,#2563eb,#06b6d4); }
.tabs button.active span { color: #2563eb; background: #fff; }
.agent-grid, .workflow-grid { display: grid; grid-template-columns: repeat(3, minmax(0,1fr)); gap: 18px; }
.agent-card { border-radius: 22px; }
.agent-head, .agent-foot, .dialog-head { display: flex; align-items: center; gap: 12px; }
.agent-head { justify-content: space-between; }
.agent-head > div:nth-child(2), .dialog-head > div:nth-child(2) { flex: 1; min-width: 0; }
.agent-head strong, .agent-head span, .dialog-head strong, .dialog-head span { display: block; }
.agent-head span, .dialog-head span { margin-top: 4px; color: #64748b; font-size: 13px; }
.avatar { display: grid; width: 44px; height: 44px; flex: 0 0 auto; place-items: center; border-radius: 15px; color: #fff; background: linear-gradient(135deg,#2563eb,#06b6d4); font-weight: 800; }
.avatar.large { width: 58px; height: 58px; border-radius: 20px; }
.io { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin: 14px 0; }
.io div { min-height: 76px; padding: 12px; border: 1px solid #e2e8f0; border-radius: 14px; background: #f8fafc; color: #475569; line-height: 1.6; }
.io small { display: block; margin-bottom: 6px; color: #2563eb; font-weight: 800; }
.agent-foot { justify-content: space-between; margin-top: 16px; padding-top: 14px; border-top: 1px solid #e2e8f0; color: #64748b; font-size: 13px; }
.workflow-card { min-height: 188px; padding: 22px; border: 1px solid #dbeafe; border-radius: 22px; background: linear-gradient(180deg,#fff,#f8fbff); }
.workflow-card b { color: #2563eb; font-size: 28px; }
.tag { margin-right: 8px; margin-top: 8px; }
@media (max-width: 1200px) { .hero, .agent-grid, .workflow-grid { grid-template-columns: 1fr 1fr; } .metrics { grid-template-columns: repeat(2, minmax(0,1fr)); } }
@media (max-width: 760px) { .hero, .agent-grid, .workflow-grid, .metrics { grid-template-columns: 1fr; } .section-head { align-items: stretch; flex-direction: column; } .section-head .el-input { width: 100%; } }
</style>
