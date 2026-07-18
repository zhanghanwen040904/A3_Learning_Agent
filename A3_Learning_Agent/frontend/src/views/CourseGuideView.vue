<template>
  <div class="course-guide-page">
    <section class="guide-hero">
      <div class="guide-title-row">
        <span class="eyebrow">GUIDE · 软件工程全局课程导学</span>
        <h1>先看懂整门课，再开始每一步学习</h1>
        <p>本页依据课程教材目录自动整理知识体系、章节重点和前置关系，帮助你先回答“学什么、为什么这样学、重点在哪里”。</p>
      </div>
      <div class="guide-overview-card">
        <div class="hero-actions">
          <el-button type="primary" size="large" @click="router.push('/path')">进入个性化学习路径</el-button>
          <el-button size="large" :loading="loading" @click="loadCourseMap">刷新课程地图</el-button>
        </div>
        <div class="course-facts">
          <div><strong>{{ chapters.length }}</strong><span>课程章节</span></div>
          <div><strong>{{ totalPoints }}</strong><span>目录知识节点</span></div>
          <div><strong>4</strong><span>学习板块</span></div>
        </div>
      </div>
    </section>

    <el-alert v-if="error" :title="error" type="warning" :closable="false" show-icon />

    <section class="knowledge-map panel-card" v-loading="loading">
      <div class="section-heading">
        <div><span>LEARNING LANDSCAPE</span><h2>课程学习全景</h2><p>先看清整门课的知识结构与学习顺序，再从基础认知逐步进入分析、设计、实现与项目管理。</p></div>
        <div class="map-actions"><span>滚轮缩放 · 拖拽节点 · 双击进入教材</span><el-button size="small" plain @click="resetGraph">复位视图</el-button></div>
      </div>
      <div v-if="chapters.length" class="graph-shell">
        <div ref="graphRef" class="course-graph" aria-label="软件工程课程知识图谱"></div>
        <aside v-if="selectedChapter" class="graph-inspector">
          <button class="inspector-close" type="button" aria-label="关闭章节详情" @click="selectedChapter=null">×</button>
          <div><span>{{selectedChapter.group}}</span><h3>{{selectedChapter.title}}</h3><p>{{selectedChapter.points.slice(0,5).join(' · ')||'课程核心内容'}}</p></div>
          <div class="inspector-meta"><b>{{selectedChapter.count}}</b><span>知识节点</span></div>
          <div class="inspector-actions">
            <el-button @click="toggleChapterPoints(selectedChapter.chapterIndex)">{{isChapterExpanded(selectedChapter.chapterIndex)?'收起知识点':'展开全部知识点'}}</el-button>
            <el-button type="primary" @click="openChapter(selectedChapter)">查看教材原文</el-button>
          </div>
        </aside>
      </div>
      <el-empty v-else-if="!loading" description="课程知识库暂无教材目录，请先在知识库管理中导入教材。" />
    </section>

    <section class="learning-route panel-card">
      <div class="section-heading">
        <div><span>COURSE ROUTE</span><h2>课程学习航线</h2><p>沿四个板块循序推进，点击节点查看当前阶段的重点、难点与学习任务。</p></div>
      </div>
      <div class="route-workbench">
        <nav class="route-rail" aria-label="课程学习板块">
          <button v-for="(block,index) in courseBlocks" :key="block.title" type="button" :class="{active:activeCourseBlock===index}" @click="activeCourseBlock=index">
            <i>{{ block.index }}</i><span><b>{{ block.title }}</b><small>{{ block.points.length }} 个核心主题</small></span><em>→</em>
          </button>
        </nav>
        <article class="route-detail">
          <div class="route-detail-head"><span>第 {{ activeBlock.index }} 学习板块</span><h3>{{ activeBlock.title }}</h3><p>{{ activeBlock.desc }}</p></div>
          <div class="route-detail-grid">
            <section><small>KEY POINTS</small><h4>本阶段重点</h4><div class="route-tags"><span v-for="item in activeBlock.points" :key="item">{{ item }}</span></div></section>
            <section class="route-difficult"><small>DIFFICULT POINTS</small><h4>重点突破</h4><div class="route-tags"><span v-for="item in activeBlock.difficulties" :key="item">{{ item }}</span></div></section>
            <section class="route-task"><small>LEARNING TASK</small><h4>建议学习任务</h4><p>{{ activeBlock.plan }}</p><el-button type="primary" plain @click="router.push('/path')">进入个性化路径</el-button></section>
          </div>
          <div class="route-progress"><span>课程推进顺序</span><div><i v-for="(_,index) in courseBlocks" :key="index" :class="{active:index<=activeCourseBlock}"></i></div><b>{{ activeCourseBlock + 1 }} / {{ courseBlocks.length }}</b></div>
        </article>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import * as echarts from "echarts/core";
import { GraphChart } from "echarts/charts";
import { LegendComponent, TooltipComponent } from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import { knowledgeApi } from "../api";

echarts.use([GraphChart, LegendComponent, TooltipComponent, CanvasRenderer]);

const router = useRouter();
const loading = ref(false);
const error = ref("");
const tree = ref([]);
const graphRef = ref(null);
const selectedChapter = ref(null);
const expandedChapters = ref(new Set());
const activeCourseBlock = ref(0);
let graphChart = null;

function unwrap(response) {
  return response?.data?.data ?? response?.data ?? response ?? [];
}

function compact(value) {
  return String(value || "").replace(/\s+/g, " ").trim();
}

function descendants(node) {
  return (node?.children || []).flatMap((child) => [child, ...descendants(child)]);
}

function findTextbook(nodes) {
  for (const node of nodes || []) {
    if (compact(node.title) === "教材") return node;
    const found = findTextbook(node.children || []);
    if (found) return found;
  }
  return null;
}

const chapters = computed(() => {
  const textbook = findTextbook(tree.value);
  const candidates = textbook?.children || [];
  return candidates
    .filter((node) => /^第\s*\d+\s*章|^附录/i.test(compact(node.title)))
    .map((node) => {
      const all = descendants(node);
      const points = all
        .filter((item) => !(item.children || []).length)
        .map((item) => compact(item.title).replace(/^\d+(?:\.\d+)*\s*/, ""))
        .filter((item, index, items) => item && items.indexOf(item) === index);
      return { ...node, title: compact(node.title), count: all.length, points };
    });
});

const totalPoints = computed(() => chapters.value.reduce((sum, chapter) => sum + chapter.count, 0));
const allPointNames = computed(() => chapters.value.flatMap((chapter) => chapter.points));
const keyPoints = computed(() => {
  const preferred = ["软件生命周期", "可行性研究", "需求分析", "总体设计", "详细设计", "软件测试", "软件维护", "面向对象"];
  return preferred.map((key) => allPointNames.value.find((item) => item.includes(key)) || key).slice(0, 8);
});
const difficultPoints = computed(() => {
  const preferred = ["数据流图", "模块独立", "Jackson", "等价划分", "对象模型", "动态模型", "软件规模", "进度计划"];
  return preferred.map((key) => allPointNames.value.find((item) => item.includes(key)) || key).slice(0, 8);
});

const courseBlocks = computed(() => [
  { index: "01", title: "基础与过程", desc: "认识软件工程要解决的问题，理解生命周期、过程模型与可行性判断。", points: keyPoints.value.slice(0, 2), difficulties: difficultPoints.value.slice(0, 2), plan: "先建立软件工程基本概念与生命周期的共同语言，再通过可行性案例理解项目是否值得启动。" },
  { index: "02", title: "分析与设计", desc: "从需求出发建立系统模型，并逐步完成总体设计和详细设计。", points: keyPoints.value.slice(2, 5), difficulties: difficultPoints.value.slice(2, 4), plan: "沿需求分析、总体设计和详细设计推进，用模型与阶段产物串联完整开发主线。" },
  { index: "03", title: "实现与保障", desc: "关注编码、测试和维护，建立贯穿开发过程的质量意识。", points: keyPoints.value.slice(5, 7), difficulties: difficultPoints.value.slice(4, 6), plan: "通过实现、测试与维护任务验证设计成果，重点掌握测试方法和质量保障思路。" },
  { index: "04", title: "面向对象与管理", desc: "用面向对象方法组织复杂系统，并掌握项目估算与进度管理。", points: [keyPoints.value[7] || "面向对象", "软件项目管理"], difficulties: difficultPoints.value.slice(6, 8), plan: "结合对象模型与项目管理完成综合迁移，把分析、设计、实现和管理能力整合到课程项目中。" },
]);
const activeBlock = computed(() => courseBlocks.value[activeCourseBlock.value] || courseBlocks.value[0]);

function chapterGroup(index) {
  if (index <= 1) return "基础与过程";
  if (index <= 5) return "分析与设计";
  if (index <= 7) return "实现与保障";
  return "面向对象与管理";
}

function graphOption() {
  const courseColor = "#2457A6";
  const blockColors = ["#6B9FF2", "#39B8B0", "#6CC59A", "#F0AD6D"];
  const blockLightColors = ["#EDF4FF", "#E9FAF8", "#EDF9F3", "#FFF4E9"];
  const blockNodes = courseBlocks.value.map((block, index) => ({
    id: `block-${index}`,
    name: block.title,
    kind: "block",
    symbolSize: 72,
    category: index + 1,
    itemStyle: { color: blockColors[index], shadowBlur: 16, shadowColor: `${blockColors[index]}55` },
    label: { fontSize: 13, fontWeight: 700, color: "#17324d" },
  }));
  const chapterNodes = chapters.value.map((chapter, index) => {
    const groupIndex = index <= 1 ? 0 : index <= 5 ? 1 : index <= 7 ? 2 : 3;
    return {
      id: `chapter-${index}`,
      name: chapter.title.replace(/^第\s*\d+\s*章\s*/, ""),
      fullTitle: chapter.title,
      kind: "chapter",
      chapterIndex: index,
      symbolSize: Math.max(40, Math.min(58, 38 + chapter.count / 3)),
      category: groupIndex + 1,
      value: chapter.count,
      itemStyle: { color: blockLightColors[groupIndex], borderColor: blockColors[groupIndex], borderWidth: 2.5, shadowBlur: 10, shadowColor: `${blockColors[groupIndex]}38` },
      label: { color: "#334155", fontSize: 11, width: 88, overflow: "truncate" },
    };
  });
  const pointNodes = [];
  const links = blockNodes.map((node) => ({ source: "course-root", target: node.id, lineStyle: { width: 2.4 } }));
  chapterNodes.forEach((node, index) => {
    links.push({ source: `block-${node.category - 1}`, target: node.id, lineStyle: { width: 1.6 } });
    if (index) links.push({ source: `chapter-${index - 1}`, target: node.id, dependency: true, lineStyle: { type: "dashed", width: 1.2, opacity: 0.42, curveness: 0.12 } });
    if (expandedChapters.value.has(index)) {
      chapters.value[index].points.forEach((point, pointIndex) => {
        const pointId = `point-${index}-${pointIndex}`;
        pointNodes.push({
          id: pointId,
          name: point,
          fullTitle: point,
          kind: "point",
          chapterIndex: index,
          symbolSize: 20,
          category: node.category,
          itemStyle: { color: blockLightColors[node.category - 1], borderColor: blockColors[node.category - 1], borderWidth: 1.5 },
          label: { color: "#52677c", fontSize: 9, width: 76, overflow: "truncate" },
        });
        links.push({ source: node.id, target: pointId, lineStyle: { width: 0.9, opacity: 0.42, curveness: 0.08 } });
      });
    }
  });
  return {
    color: [courseColor, ...blockColors],
    tooltip: {
      trigger: "item",
      backgroundColor: "rgba(15,23,42,.94)",
      borderWidth: 0,
      textStyle: { color: "#fff" },
      formatter(params) {
        if (params.dataType === "edge") return params.data?.dependency ? "章节前置学习关系" : "知识板块归属";
        if (params.data?.kind === "chapter") {
          const chapter = chapters.value[params.data.chapterIndex];
          return `<b>${chapter.title}</b><br/>${chapter.count} 个知识节点<br/><span style="color:#cbd5e1">${chapter.points.slice(0,3).join(" · ")}</span>`;
        }
        return `<b>${params.data?.fullTitle || params.name}</b>`;
      },
    },
    legend: [{ data: ["课程中心", ...courseBlocks.value.map((item) => item.title)], bottom: 8, icon: "circle" }],
    series: [{
      type: "graph",
      layout: "force",
      roam: true,
      draggable: true,
      animationDurationUpdate: 500,
      categories: [{ name: "课程中心" }, ...courseBlocks.value.map((item) => ({ name: item.title }))],
      data: [{
        id: "course-root",
        name: "软件工程",
        fullTitle: "软件工程课程",
        kind: "root",
        symbolSize: 100,
        category: 0,
        itemStyle: {
          color: courseColor,
          borderColor: "#DCEAFF",
          borderWidth: 4,
          shadowBlur: 26,
          shadowColor: "#2457A666",
        },
        label: {
          show: true,
          position: "inside",
          color: "#FFFFFF",
          fontSize: 17,
          fontWeight: 800,
          textBorderColor: "#17427F",
          textBorderWidth: 2,
        },
      }, ...blockNodes, ...chapterNodes, ...pointNodes],
      links,
      force: { repulsion: pointNodes.length ? 520 : 430, edgeLength: pointNodes.length ? [72, 155] : [95, 185], gravity: 0.1, friction: 0.58 },
      edgeSymbol: ["none", "arrow"],
      edgeSymbolSize: [0, 7],
      lineStyle: { color: "source", opacity: 0.62, curveness: 0.06 },
      emphasis: { focus: "adjacency", lineStyle: { width: 3, opacity: 1 }, scale: 1.12 },
      label: { show: true, position: "right" },
    }],
  };
}

async function renderGraph() {
  if (!chapters.value.length) return;
  await nextTick();
  if (!graphRef.value) return;
  if (!graphChart) {
    graphChart = echarts.init(graphRef.value);
    graphChart.on("click", (params) => {
      if (params.data?.kind === "chapter") {
        if (selectedChapter.value?.chapterIndex === params.data.chapterIndex) {
          selectedChapter.value = null;
          return;
        }
        selectedChapter.value = { ...chapters.value[params.data.chapterIndex], group: chapterGroup(params.data.chapterIndex), chapterIndex: params.data.chapterIndex };
        toggleChapterPoints(params.data.chapterIndex);
      }
    });
    graphChart.on("dblclick", (params) => {
      if (params.data?.kind === "chapter") openChapter(chapters.value[params.data.chapterIndex]);
    });
  }
  graphChart.setOption(graphOption(), true);
  graphChart.resize();
}

function resetGraph() {
  graphChart?.setOption(graphOption(), true);
}

function isChapterExpanded(index) {
  return expandedChapters.value.has(Number(index));
}

function toggleChapterPoints(index) {
  const chapterIndex = Number(index);
  const next = new Set(expandedChapters.value);
  if (next.has(chapterIndex)) next.delete(chapterIndex);
  else next.add(chapterIndex);
  expandedChapters.value = next;
  renderGraph();
}

function resizeGraph() {
  graphChart?.resize();
}

async function loadCourseMap() {
  loading.value = true;
  error.value = "";
  try {
    tree.value = unwrap(await knowledgeApi.tree());
  } catch (exception) {
    error.value = exception?.message || "课程知识地图加载失败";
    tree.value = [];
  } finally {
    loading.value = false;
    renderGraph();
  }
}

function openChapter(chapter) {
  router.push({ path: "/knowledge", query: { nodeId: chapter.node_id, evidence: chapter.title, section: chapter.title } });
}

watch(chapters, renderGraph);
onMounted(() => { loadCourseMap(); window.addEventListener("resize", resizeGraph); });
onBeforeUnmount(() => { window.removeEventListener("resize", resizeGraph); graphChart?.dispose(); graphChart = null; });
</script>

<style scoped>
.course-guide-page{display:grid;min-width:0;max-width:100%;gap:22px;padding:2px;overflow-x:hidden;background:#f7f9fc;color:#0f172a}.course-guide-page>*{min-width:0;max-width:100%;box-sizing:border-box}.guide-hero{display:grid;grid-template-columns:minmax(0,1fr) minmax(300px,420px);gap:28px;align-items:end;padding:38px;border:1px solid #dbeafe;border-radius:30px;background:radial-gradient(circle at 82% 18%,rgba(67,198,184,.16),transparent 28%),linear-gradient(135deg,#fff 0%,#f1f8ff 58%,#effcf8 100%);box-shadow:0 20px 50px rgba(15,23,42,.07)}.eyebrow,.section-heading span{color:#4386d8;font-size:12px;font-weight:800;letter-spacing:.1em}.guide-hero h1{max-width:760px;margin:14px 0 12px;font-size:38px;line-height:1.25;letter-spacing:-.04em}.guide-hero p{max-width:760px;margin:0;color:#475569;font-size:16px;line-height:1.9}.hero-actions{display:flex;gap:12px;margin-top:24px}.course-facts{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}.course-facts div{min-width:0;padding:20px 14px;border:1px solid rgba(191,219,254,.9);border-radius:20px;background:rgba(255,255,255,.8)}.course-facts strong,.course-facts span{display:block}.course-facts strong{font-size:27px}.course-facts span{margin-top:5px;color:#64748b;font-size:12px}.panel-card{min-width:0;padding:26px;border:1px solid #e2e8f0;border-radius:26px;background:#fff;box-shadow:0 14px 34px rgba(15,23,42,.045)}.section-heading{display:flex;justify-content:space-between;gap:16px;align-items:flex-start;margin-bottom:18px}.section-heading h2{margin:5px 0 0;font-size:23px}.section-heading p{margin:6px 0 0;color:#64748b}.summary-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.summary-grid article{min-width:0;padding:18px;border:1px solid #dbeafe;border-radius:19px;background:#f8fbff}.summary-grid small{color:#4386d8;font-weight:800}.summary-grid h3{margin:8px 0}.summary-grid p{margin:0;color:#475569;line-height:1.7}.summary-grid article div{display:flex;flex-wrap:wrap;gap:6px;margin-top:12px}.summary-grid article span{padding:5px 8px;border-radius:999px;background:#fff;color:#3977bf;font-size:11px}.map-actions{display:flex;align-items:center;gap:12px;color:#64748b;font-size:12px}.graph-shell{position:relative;min-width:0;overflow:hidden;border:1px solid #d8e9ea;border-radius:22px;background:radial-gradient(circle at 50% 45%,#edfafa 0,#f6fbfb 38%,#fff 75%)}.course-graph{width:100%;height:690px}.graph-inspector{position:absolute;right:18px;top:18px;display:grid;width:min(350px,calc(100% - 36px));gap:13px;padding:17px;border:1px solid rgba(201,231,228,.95);border-radius:18px;background:rgba(255,255,255,.95);box-shadow:0 16px 34px rgba(49,94,104,.13);backdrop-filter:blur(12px)}.graph-inspector span{color:#4386d8;font-size:11px;font-weight:800}.graph-inspector h3{margin:5px 0;color:#0f172a}.graph-inspector p{margin:0;color:#64748b;font-size:12px;line-height:1.65}.inspector-meta{display:flex;align-items:baseline;gap:6px}.inspector-meta b{color:#4386d8;font-size:24px}.inspector-meta span{color:#64748b}.inspector-actions{display:grid;grid-template-columns:1fr 1fr;gap:8px}.inspector-actions .el-button{margin:0}.focus-layout{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}.focus-card,.arrangement-card{min-width:0;min-height:300px}.focus-list{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.focus-list div{display:flex;min-width:0;align-items:center;gap:9px;padding:11px;border-radius:13px;background:#eef7ff;color:#334155}.focus-list i{width:7px;height:7px;border-radius:50%;background:#6ea8fe}.difficult .focus-list div{background:#fff6eb}.difficult .focus-list i{background:#f2b880}.arrangement-card ol{display:grid;gap:11px;margin:0;padding:0;list-style:none}.arrangement-card li{display:flex;gap:11px;align-items:flex-start;color:#475569;line-height:1.65}.arrangement-card li b{display:grid;flex:0 0 28px;height:28px;place-items:center;border-radius:9px;background:#e7f6f3;color:#287f75}@media(max-width:1200px){.guide-hero{grid-template-columns:1fr}.focus-layout{grid-template-columns:repeat(2,minmax(0,1fr))}.arrangement-card{grid-column:1/-1}}@media(max-width:760px){.guide-hero{padding:24px}.guide-hero h1{font-size:30px}.course-facts,.summary-grid,.focus-layout{grid-template-columns:1fr}.arrangement-card{grid-column:auto}.hero-actions{flex-wrap:wrap}.panel-card{padding:20px}.section-heading{flex-direction:column}.map-actions{width:100%;justify-content:space-between}.course-graph{height:620px}.graph-inspector{position:relative;inset:auto;width:auto;margin:0 12px 12px}.inspector-actions{grid-template-columns:1fr}}
.route-workbench{display:grid;grid-template-columns:minmax(280px,.32fr) minmax(0,.68fr);gap:22px;align-items:stretch}.route-rail{position:relative;display:grid;grid-template-rows:repeat(4,minmax(74px,1fr));gap:9px;padding:0}.route-rail:before{position:absolute;top:38px;bottom:38px;left:29px;width:1px;background:linear-gradient(#b9d7f5,#dce9f5);content:""}.route-rail button{position:relative;display:grid;grid-template-columns:42px minmax(0,1fr) 20px;align-items:center;gap:11px;width:100%;min-height:74px;padding:13px 14px;border:1px solid #e8eef5;border-radius:17px;background:#fbfcfe;color:#64748b;text-align:left;cursor:pointer;transition:.2s ease}.route-rail button:hover{border-color:#cfe1f4;background:#f6faff}.route-rail button.active{border-color:#8fc1f5;background:linear-gradient(135deg,#edf6ff,#f5fbff);box-shadow:0 10px 24px rgba(67,134,216,.12)}.route-rail button>i{z-index:1;display:grid;width:36px;height:36px;place-items:center;border:4px solid #fff;border-radius:50%;background:#dce8f5;color:#64809f;font-size:11px;font-style:normal;font-weight:800;box-shadow:0 0 0 1px #cbdced}.route-rail button.active>i{background:#4386d8;color:#fff;box-shadow:0 0 0 2px #8fc1f5}.route-rail button span{display:grid;gap:4px}.route-rail button b{color:#25364a;font-size:13px}.route-rail button small{color:#94a3b8;font-size:10px}.route-rail button em{color:#b1bfd0;font-style:normal}.route-rail button.active em{color:#4386d8}.route-detail{display:grid;grid-template-rows:auto 1fr auto;gap:17px;padding:24px;border:1px solid #d4e5f3;border-radius:22px;background:radial-gradient(circle at 92% 5%,rgba(67,198,184,.1),transparent 30%),linear-gradient(145deg,#fff,#f8fbff)}.route-detail-head>span{color:#4386d8;font-size:11px;font-weight:800;letter-spacing:.08em}.route-detail-head h3{margin:6px 0 5px;font-size:25px}.route-detail-head p{margin:0;color:#64748b;line-height:1.65}.route-detail-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}.route-detail-grid section{display:flex;min-width:0;min-height:150px;flex-direction:column;padding:16px;border:1px solid #e2eaf3;border-radius:16px;background:rgba(255,255,255,.9)}.route-detail-grid small{color:#4386d8;font-size:9px;font-weight:800;letter-spacing:.09em}.route-detail-grid h4{margin:6px 0 11px;color:#25364a}.route-tags{display:flex;align-content:flex-start;flex-wrap:wrap;gap:6px}.route-tags span{padding:6px 9px;border-radius:999px;background:#edf6ff;color:#3977bf;font-size:11px}.route-difficult .route-tags span{background:#fff3e6;color:#b87535}.route-task p{flex:1;margin:0 0 12px;color:#64748b;font-size:12px;line-height:1.7}.route-task .el-button{align-self:flex-start;margin:0}.route-progress{display:grid;grid-template-columns:auto minmax(0,1fr) auto;align-items:center;gap:12px;color:#8493a6;font-size:11px}.route-progress>div{display:grid;grid-template-columns:repeat(4,1fr);gap:5px}.route-progress i{height:5px;border-radius:999px;background:#e4ebf3}.route-progress i.active{background:linear-gradient(90deg,#4386d8,#43c6b8)}.route-progress b{color:#4386d8}@media(max-width:980px){.route-workbench{grid-template-columns:1fr}.route-rail{grid-template-columns:repeat(4,minmax(0,1fr));grid-template-rows:auto;overflow:hidden}.route-rail:before{display:none}.route-rail button{grid-template-columns:34px minmax(0,1fr)}.route-rail button em{display:none}.route-detail-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.route-task{grid-column:1/-1}}@media(max-width:680px){.route-rail{grid-template-columns:1fr 1fr}.route-detail{padding:17px}.route-detail-grid{grid-template-columns:1fr}.route-detail-grid section{min-height:auto}.route-task{grid-column:auto}.route-progress{grid-template-columns:1fr}.route-progress>b{text-align:right}}
.graph-inspector{right:14px;top:14px;width:min(285px,calc(100% - 28px));gap:9px;padding:14px 15px;border-color:rgba(174,218,214,.72);border-radius:16px;background:rgba(255,255,255,.76);box-shadow:0 12px 28px rgba(49,94,104,.1);backdrop-filter:blur(16px) saturate(1.12)}.graph-inspector>div:first-of-type{padding-right:22px}.graph-inspector h3{margin:3px 0;font-size:16px;line-height:1.4}.graph-inspector p{display:-webkit-box;overflow:hidden;font-size:11px;line-height:1.55;-webkit-box-orient:vertical;-webkit-line-clamp:3}.graph-inspector .inspector-meta b{font-size:19px}.graph-inspector .inspector-actions{gap:6px}.graph-inspector .inspector-actions .el-button{height:30px;padding:6px 9px;font-size:11px}.inspector-close{position:absolute;z-index:2;top:9px;right:9px;display:grid;width:24px;height:24px;padding:0;place-items:center;border:1px solid rgba(203,213,225,.8);border-radius:8px;background:rgba(255,255,255,.65);color:#64748b;font-size:17px;line-height:1;cursor:pointer;transition:.16s}.inspector-close:hover{border-color:#8dbbe9;background:rgba(239,247,255,.92);color:#2f72dc}@media(max-width:760px){.graph-inspector{width:auto;margin:0 10px 10px;background:rgba(255,255,255,.86)}}

.course-guide-page{
  width:100%;
  min-height:100vh;
  padding:18px 16px 28px;
  gap:18px;
  box-sizing:border-box;
  background:linear-gradient(180deg,#f4f7fb 0%,#f7f9fc 100%);
}
.panel-card{
  border:1px solid #e7ecf3;
  border-radius:20px;
  background:#fff;
  box-shadow:0 1px 2px rgba(20,34,55,.02),0 8px 28px rgba(31,47,70,.035);
}
.guide-hero{
  display:grid;
  grid-template-columns:1fr;
  gap:14px;
  align-items:start;
  padding:0 0 4px;
  border:0;
  border-radius:0;
  background:transparent;
  box-shadow:none;
}
.guide-title-row{
  min-width:0;
  padding:0 22px;
  box-sizing:border-box;
}
.guide-title-row p{
  max-width:50em;
}
.guide-overview-card{
  display:grid;
  grid-template-columns:minmax(0,1fr) minmax(300px,480px);
  gap:26px;
  align-items:center;
  min-height:132px;
  padding:20px 24px;
  border:1px solid #dbe7f5;
  border-radius:24px;
  background:linear-gradient(135deg,#ffffff 0%,#f8fbff 100%);
  box-shadow:0 14px 32px rgba(15,23,42,.055);
  box-sizing:border-box;
}
.guide-overview-card .hero-actions{
  margin-top:0;
  align-self:center;
  display:flex;
  align-items:center;
  min-height:92px;
  gap:14px;
}
.course-facts div,
.summary-grid article,
.graph-shell,
.route-detail,
.route-detail-grid section{
  border:1px solid #e5ebf4;
  background:#f8fafc;
}
.course-facts div,
.summary-grid article{
  border-radius:16px;
}
.graph-shell{
  border-radius:16px;
}
.route-detail{
  border-radius:16px;
  box-shadow:none;
}
.route-detail-grid section{
  border-radius:14px;
}
.route-rail button{
  border-color:#e5ebf4;
  background:#fff;
}
.route-rail button.active{
  border-color:#bfdbfe;
  background:#f8fafc;
  box-shadow:none;
}
@media(max-width:760px){
  .course-guide-page{
    padding:14px 12px 24px;
  }
  .guide-overview-card,
  .panel-card{
    border-radius:18px;
  }
  .guide-overview-card{
    grid-template-columns:1fr;
    padding:16px;
  }
}

/* Keep the course guide actions close to the title area on wide and narrow screens. */
.guide-overview-card{
  align-items:center;
  padding:20px 24px;
}

.guide-overview-card .hero-actions{
  align-self:center;
  align-items:center;
  flex-wrap:wrap;
  gap:14px;
}

.guide-overview-card .hero-actions :deep(.el-button){
  height:46px;
  min-width:164px;
  padding:0 22px;
  border-radius:14px;
  font-size:15px;
  font-weight:800;
  box-shadow:none;
}

.guide-overview-card .hero-actions :deep(.el-button--primary){
  box-shadow:0 12px 22px rgba(64,158,255,.2);
}

.course-facts div{
  display:grid;
  align-content:center;
  min-height:92px;
  padding:18px 20px;
  border-color:#dce8f6;
  border-radius:18px;
  background:linear-gradient(145deg,#ffffff,#f7faff);
  box-shadow:0 8px 20px rgba(15,23,42,.04);
}

.course-facts strong{
  color:#0b1324;
  font-size:31px;
  line-height:1;
}

.course-facts span{
  margin-top:7px;
  color:#52657c;
  font-size:13px;
  font-weight:700;
}

@media(max-width:980px){
  .guide-overview-card{
    grid-template-columns:1fr;
    gap:14px;
  }
  .guide-overview-card .hero-actions{
    width:100%;
    min-height:auto;
  }
}

@media(max-width:560px){
  .guide-overview-card .hero-actions :deep(.el-button){
    width:100%;
    margin-left:0;
  }
}
</style>
