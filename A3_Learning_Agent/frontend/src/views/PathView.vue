<template>
  <div class="page path-page">
    <section class="plan-hero-card">
      <div class="plan-title-row">
        <div class="plan-hero-main overview-main">
          <span class="page-eyebrow">LEARNING PLAN</span>
          <h2 class="plan-hero-title">{{ planTitle }}</h2>
          <p class="plan-hero-description">根据你的学习目标和当前掌握情况，整理了 3 个循序渐进的学习阶段。你可以按阶段学习、完成测评，并根据结果调整后续节奏。</p>
        </div>
      </div>
      <div class="plan-overview-card">
        <div class="plan-overview-main">
          <div class="plan-status-tags">
            <el-tooltip :disabled="profileTipDisabled" :content="basis" placement="bottom-start" @show="markProfileTipShown"><el-tag class="plan-status-tag plan-status-tag--base" type="primary" effect="light">基础：{{profile.knowledge_base||profile.knowledge_level||'待观察'}}</el-tag></el-tooltip>
            <el-tooltip :disabled="profileTipDisabled" :content="basis" placement="bottom-start" @show="markProfileTipShown"><el-tag class="plan-status-tag plan-status-tag--weak" type="danger" effect="light">需加强：{{profile.error_prone_points||profile.weak_points||'待观察'}}</el-tag></el-tooltip>
            <el-tooltip :disabled="profileTipDisabled" :content="basis" placement="bottom-start" @show="markProfileTipShown"><el-tag class="plan-status-tag plan-status-tag--goal" type="success" effect="light">目标：{{profile.study_goal||'待观察'}}</el-tag></el-tooltip>
          </div>
          <div v-if="integrated.adaptive_focus" class="plan-feedback-panel adaptive-focus-bar">
            <el-tag class="plan-feedback-label" type="warning" effect="light">反馈驱动重点</el-tag>
            <span class="plan-feedback-content">{{ integrated.adaptive_focus }}</span>
          </div>
          <p v-if="integrated.adaptive_explanation" class="plan-resource-note adaptive-explanation">
            {{ integrated.adaptive_explanation }}
          </p>
        </div>
        <aside class="plan-hero-side">
          <div class="plan-metrics-grid">
            <div class="plan-metric-card"><div class="plan-metric-value">{{ totalDays }}</div><div class="plan-metric-label">预计时长</div></div>
            <div class="plan-metric-card"><div class="plan-metric-value">{{ stages.length }}</div><div class="plan-metric-label">学习阶段</div></div>
            <div class="plan-metric-card"><div class="plan-metric-value">{{ resources.length }}</div><div class="plan-metric-label">学习材料</div></div>
          </div>
          <div class="plan-hero-actions"><el-button text :loading="loading" @click="generateAll('',true)">更新计划</el-button><el-dropdown @command="pace"><el-button plain>调整学习节奏</el-button><template #dropdown><el-dropdown-menu><el-dropdown-item command="fast">节奏加快</el-dropdown-item><el-dropdown-item command="slow">节奏放慢</el-dropdown-item><el-dropdown-item command="practice">增加实操练习</el-dropdown-item></el-dropdown-menu></template></el-dropdown></div>
        </aside>
      </div>
    </section>

    <el-card v-if="loading" class="panel run-panel"><template #header><div class="line"><span>多智能体协同生成中</span><el-tag type="primary">{{ progress }}%</el-tag></div></template><el-progress :percentage="progress" striped striped-flow /><div class="run-grid"><div class="agent-flow"><div v-for="step in agentSteps" :key="step.name" :class="['run-step',step.status]"><b>{{step.short}}</b><div><strong>{{step.name}}</strong><span>{{step.desc}}</span></div><em>{{step.statusText}}</em></div></div><div class="live-preview"><b>当前系统正在做什么</b><p>{{agentSteps.find(s=>s.status==='running')?.desc||'正在整理学习路径与资源结果。'}}</p><small>你可以先查看已生成内容，系统会在完成后自动刷新路径与资源。</small></div></div></el-card>

    <el-empty v-if="!loading&&!stages.length" class="panel" description="当前画像还没有路径学习方案。请先生成画像，再点击生成路径与资源。"><el-button type="primary" @click="generateAll()">立即生成路径与资源</el-button></el-empty>

    <div v-if="!loading&&stages.length" class="stage-workspace">
      <nav class="stage-map-nav" aria-label="学习阶段导航">
        <div class="stage-map-status"><span>学习阶段</span><b>{{percent}}% 已完成</b></div>
        <div class="stage-map-items">
          <button v-for="(s,i) in stages" :key="`map-${s.key}`" type="button" :class="[state(i),{active:i===activeStageIndex}]" @click="selectStage(i)">
            <span>{{done(i)?'✓':i+1}}</span><b>{{s.title}}</b>
          </button>
        </div>
        <el-progress :percentage="percent" :stroke-width="5" :show-text="false" />
      </nav>
      <div class="timeline compact-timeline">
      <div v-for="(s,i) in stages" v-show="i===activeStageIndex" :key="s.key" :class="['stage',state(i)]">
        <el-card class="stage-card" shadow="never">
          <template #header><div class="stage-head compact-stage-head"><div class="stage-title-block"><el-tag :type="tag(i)" effect="dark">{{ label(i) }}</el-tag><h3>第{{i+1}}阶段：{{s.title}}</h3></div><div class="stage-head-actions"><el-tag v-for="p in (s.points||[]).slice(0,3)" :key="p" size="small" type="info" effect="plain">{{p}}</el-tag><el-button size="small" plain @click="toggle(i)">{{done(i)?'取消完成':'标记完成'}}</el-button></div></div></template>
          <div class="body">
            <section class="stage-guide-panel">
              <div class="stage-guide-title"><span>阶段导学</span><b>{{stagePosition(i)}}</b></div>
              <div class="stage-guide-summary">
                <div><small>前置知识</small><strong>{{stagePrerequisites(i)}}</strong></div>
                <i></i>
                <div><small>能力目标</small><strong>{{stageOutcome(s)}}</strong></div>
              </div>
              <div class="stage-jar-row">
                <div><b>知识收藏瓶</b><span>点亮想沉淀的知识点，完成本阶段后将自动全部收集。</span></div>
                <div class="stage-jar-points"><button v-for="point in s.points||[]" :key="point" :class="{collected:isJarCollected(point)}" :disabled="jarBusy===point" @click="toggleJarPoint(point,s,i)"><span>{{isJarCollected(point)?'✓':'＋'}}</span>{{point}}</button></div>
              </div>
            </section>
            <div class="section"><b>本阶段配套资源</b><span>保留个性化说明与质量审核报告</span></div><el-tabs v-if="s.resources.length" v-model="activeResourceTabs[i]" class="resource-tabs" stretch @tab-change="onResourceTabChange">
                <el-tab-pane v-for="r in s.resources" :key="rid(r)" :name="rid(r)">
                  <template #label><span class="resource-tab-label"><span>{{resourceIcon(r.resource_type)}}</span>{{typeName(r.resource_type)}}</span></template>
                  <div :class="['res',resourceClass(r),{'res-static-toggle':usesButtonToggleOnly(r)}]" @click="resourceCardClick(r)">
                  <div class="res-head">
                    <div class="res-title">
                      <span class="res-icon">{{resourceIcon(r.resource_type)}}</span>
                      <el-tag size="small" effect="dark">{{typeName(r.resource_type)}}</el-tag>
                      <strong>{{r.title}}</strong>
                      <el-tag :type="qPass(r)?'success':'warning'" size="small" plain>{{qScore(r)}}分</el-tag>
                    </div>
                    <el-button v-if="!isFixedResource(r)" size="small" text @click.stop="toggleResource(r)">{{resourceOpen(r)?'收起正文':'查看正文'}}</el-button>
                  </div>
                  <template v-if="isMindmap(r)">
                    <div class="markmap-panel">
                      <div
                        :ref="el=>setMarkmapViewportRef(r,el)"
                        class="markmap-viewport"
                        :class="{dragging:isMindmapDragging(r)}"
                        @wheel.prevent="handleMindmapWheel($event,r)"
                        @mousedown="startMindmapDrag($event,r)"
                        @dblclick.stop.prevent="fitMindmapToViewport(r)"
                      >
                        <div class="markmap-zoom-layer" :style="mindmapZoomStyle(r)">
                          <svg :ref="el=>setMarkmapRef(r,el)" class="markmap-container"></svg>
                        </div>
                      </div>
                    </div>
                  </template>
                  <template v-else-if="isReading(r)">
                    <div class="doc-reading-content" :class="{collapsed:!resourceOpen(r)}" v-html="renderReading(r,s)"></div>
                  </template>
                  <template v-else-if="isDoc(r)">
                    <div class="doc-reading-content" :class="{collapsed:!resourceOpen(r)}" v-html="renderDoc(r,s)"></div>
                  </template>
                  <template v-else-if="isVideo(r)">
                    <div class="video-resource-panel">
                      <video v-if="playableVideo(r)" class="video-player" :src="videoUrl(r)" controls preload="metadata"></video>
                      <div v-else class="video-placeholder">
                        <b>{{r.title}}</b>
                        <p>当前视频资源尚未关联可播放的视频文件，请在资源详情中补充视频地址后播放。</p>
                      </div>
                    </div>
                  </template>
                  <div v-else class="res-content" :class="{collapsed:!resourceOpen(r)}">{{resourceText(r)}}</div>
                  <div v-if="isDoc(r)&&resourceOpen(r)&&resourceImages(r).length" class="image-gallery doc-image-gallery">
                    <div v-for="img in resourceImages(r)" :key="img.image_id||img.path||img" class="kb-image">
                      <img :src="imageUrl(img.path||img)" :alt="img.caption||'知识库配图'" loading="lazy" />
                      <p>{{img.figure_label||img.caption||img.image_summary||'与当前知识点相关的教材配图'}}</p>
                    </div>
                  </div>




                  <div class="res-meta">
                    <span>知识点：{{kps(r).join('、')||'课程核心知识'}}</span>
                    <span>{{sourceText(r)}}</span>
                  </div>
                  <div class="res-actions" @click.stop>
                    <el-button text size="small" @click="openResourceDetail(r,'basis')">生成依据</el-button>
                    <el-divider direction="vertical" />
                    <el-button text size="small" @click="openResourceDetail(r,'audit')">质量审核</el-button>
                  </div>
                </div>
                </el-tab-pane>
              </el-tabs><el-empty v-else description="本阶段暂未匹配到资源，重新生成后会自动挂载。" />
              <div class="stage-eval stage-eval-standalone">
                <div><b>{{stageRecord(i)?.completed?'基础练习与阶段评估已完成':'基础练习与阶段评估'}}</b><p>{{stageQuizResource(s)?.title||'系统将根据本阶段知识点生成基础练习与阶段测评题。'}}</p><span v-if="stageRecord(i)?.completed">最近得分：{{stageRecord(i).avgScore}}分 · {{stageRecord(i).completedAt}}</span><span v-else>测评范围：{{(s.points||[]).join('、')||'本阶段核心知识点'}}</span></div>
                <el-button type="primary" @click="goStageEvaluation(s,i)">{{stageRecord(i)?.completed?'查看/重测':'开始练习测评'}}</el-button>
              </div>
              <div class="stage-nav-actions">
                <el-button :disabled="i===0" @click="prevStage">上一阶段</el-button>
                <el-button plain @click="toggle(i)">{{done(i)?'取消完成':'标记完成'}}</el-button>
                <el-button type="primary" :disabled="i===stages.length-1" @click="nextStage">{{done(i)?'下一阶段':'完成并进入下一阶段'}}</el-button>
              </div>
            </div>
        </el-card>
      </div>
    </div>
    </div>

    <el-card class="panel feedback feedback-card"><div><el-tag type="primary" effect="light">学习反馈与动态调整</el-tag><b>让后续学习方案随掌握情况变化</b><p>提交学习反馈后，EvaluatorAgent 将分析你的掌握情况，由 PlannerAgent 动态调整后续阶段的难度与资源侧重。</p></div><div><el-button plain @click="fb('easy')">觉得太简单</el-button><el-button plain @click="fb('hard')">觉得太难</el-button><el-button type="primary" @click="fb('quiz')">根据练习结果调整</el-button></div></el-card>

    <el-dialog v-model="detailDialog.visible" :title="detailDialog.type==='basis'?'生成依据':'质量审核报告'" width="min(720px, 92vw)" destroy-on-close>
      <div v-if="detailDialog.resource" class="detail-dialog-body">
        <template v-if="detailDialog.type==='basis'">
          <h3>{{detailDialog.resource.title}}</h3>
          <p>{{detailDialog.resource.personalization||'依据学生画像、阶段目标、知识短板和课程知识库内容生成。'}}</p>
          <div class="detail-kv"><span>资源类型</span><b>{{typeName(detailDialog.resource.resource_type)}}</b></div>
          <div class="detail-kv"><span>关联知识点</span><b>{{kps(detailDialog.resource).join('、')||'课程核心知识'}}</b></div>
          <div class="detail-kv"><span>知识库来源</span><b>{{sourceText(detailDialog.resource)}}</b></div>
          <div v-if="evidenceSources(detailDialog.resource).length" class="evidence-source-list">
            <button
              v-for="(source,index) in evidenceSources(detailDialog.resource)"
              :key="`${source.title}-${source.chunk_index}-${index}`"
              type="button"
              class="evidence-source-card"
              @click="openEvidenceSource(source)"
            >
              <span class="evidence-index">{{index+1}}</span>
              <span class="evidence-main">
                <strong>{{source.title}}</strong>
                <small>{{source.section_path||source.source_file||'课程知识库'}}</small>
                <em v-if="source.content_preview">{{source.content_preview}}</em>
              </span>
              <span class="evidence-meta">
                <small v-if="source.pages">第 {{source.pages}} 页</small>
                <small v-if="source.chunk_index!==''">片段 {{source.chunk_index}}</small>
                <b>查看原文 →</b>
              </span>
            </button>
          </div>
          <el-alert v-else type="warning" :closable="false" title="该资源暂未保存可定位的知识库证据" />
        </template>
        <template v-else>
          <h3>{{detailDialog.resource.title}}</h3>
          <el-progress :percentage="qScore(detailDialog.resource)" :status="qPass(detailDialog.resource)?'success':'warning'" />
          <div class="detail-kv"><span>审核结论</span><b>{{qPass(detailDialog.resource)?'审核通过':'建议复核'}}</b></div>
          <div class="detail-kv"><span>质量评分</span><b>{{qScore(detailDialog.resource)}}分</b></div>
          <p>系统从内容完整性、知识点相关性、个性化匹配和课程依据可追溯性等维度进行质量检查。若评分偏低，建议重新生成或人工复核。</p>
        </template>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed,nextTick,onBeforeUnmount,onMounted,ref,watch } from 'vue';
import { useRoute,useRouter } from 'vue-router';
import { Transformer } from 'markmap-lib';
import { Markmap } from 'markmap-view';
import MarkdownIt from 'markdown-it';
import { ElMessage } from 'element-plus';
import { activeProfileSessionId,knowledgeJarApi,pathApi,profileApi,resourceApi } from '../api';
const router=useRouter();
const route=useRoute();
const autoGenerating=ref(false);
const paths=ref([]),resources=ref([]),profile=ref({}),integrated=ref({}),loading=ref(false),progress=ref(0),completed=ref([]),hint=ref(''),openStages=ref({}),openResources=ref({}),assessmentRecords=ref([]),agentSteps=ref([]),activeStageIndex=ref(0),activeResourceTabs=ref({});
const profileTipDisabled=ref(localStorage.getItem('a3_path_profile_tip_seen')==='1');
const detailDialog=ref({visible:false,type:'basis',resource:null});
const jarPoints=ref(new Set()),jarBusy=ref('');
let pathLoadToken=0;
let trackedResource=null;
let trackedSince=0;
let usageHeartbeat=null;
const agents=[{name:'PlannerAgent',short:'PL',desc:'读取画像并规划阶段目标',p:18},{name:'RetrieverAgent',short:'RG',desc:'检索课程知识库和章节依据',p:34},{name:'ResourceAgents',short:'RA',desc:'生成讲解、练习、思维导图等资源',p:64},{name:'AuditAgent',short:'AU',desc:'校验事实准确性和格式质量',p:82},{name:'PackagerAgent',short:'PK',desc:'按阶段挂载资源并刷新页面',p:100}];
const markmapTransformer=new Transformer();
const markdownRenderer=new MarkdownIt({html:false,linkify:true,breaks:true});
const markmapEls=new Map();
const markmapInstances=new Map();
const markmapViews=ref({});
const markmapViewports=new Map();
const mindmapDragState=ref({id:'',active:false,startX:0,startY:0,originX:0,originY:0});
function resetAgentSteps(){agentSteps.value=agents.map(item=>({...item,status:'waiting',statusText:'等待'}))}
function setAgentStep(name,status,statusText){agentSteps.value=agentSteps.value.map(item=>item.name===name?{...item,status,statusText}:item)}
function markProfileTipShown(){localStorage.setItem('a3_path_profile_tip_seen','1');profileTipDisabled.value=true}
const latest=computed(()=>paths.value[0]||{}),rawStages=computed(()=>parseStages(latest.value.path_content||''));
const serverStages=computed(()=>Array.isArray(integrated.value.stages)?integrated.value.stages:[]);
const baseStages=computed(()=>serverStages.value.length?serverStages.value:(rawStages.value.length?rawStages.value:fallback()));
const title=computed(()=>integrated.value.topic||profile.value.target_course||profile.value.study_goal||baseStages.value[0]?.title||'个性化学习路径');
const planKnowledgeTitle=computed(()=>{
  const points=[...new Set(baseStages.value.flatMap(stage=>Array.isArray(stage.points)?stage.points:[]).filter(point=>point&&point!=='课程核心知识'))];
  if(points.length)return points.slice(0,2).join('与');
  const firstStageTitle=clean(baseStages.value[0]?.title||'');
  if(firstStageTitle&&!['基础概念澄清','方法关系建构','练习与实操巩固','学习阶段1'].includes(firstStageTitle))return firstStageTitle;
  return integrated.value.topic||profile.value.target_course||profile.value.study_goal||'个性化学习路径';
});
const planTitle=computed(()=>`${planKnowledgeTitle.value}学习计划`);
const basis=computed(()=>integrated.value.profile_basis?.summary||[profile.value.knowledge_base||profile.value.knowledge_level,profile.value.error_prone_points||profile.value.weak_points,profile.value.study_goal].filter(v=>v&&v!=='待进一步观察').join('；')||'可在学生画像中继续完善');
const current=computed(()=>Math.max(baseStages.value.findIndex((_,i)=>!completed.value.includes(i)),0));
const stages=computed(()=>baseStages.value.map((s,i)=>{const rawResources=Array.isArray(s.resources)?s.resources:matchRes(s,i,baseStages.value.length);return {...s,key:`${i}-${s.title}`,open:openStages.value[i]??i===current.value,allResources:rawResources,resources:displayResources(rawResources,s)}}));
const percent=computed(()=>Math.round(completed.value.length/Math.max(stages.value.length,1)*100));
const activeStage=computed(()=>stages.value[activeStageIndex.value]||stages.value[current.value]||stages.value[0]||null);
const totalDays=computed(()=>integrated.value.total_duration||`${stages.value.reduce((n,s)=>n+Number(String(s.duration).match(/\d+/)?.[0]||0),0)||stages.value.length}天`);
function clean(t){return String(t||'').replace(/[#*_`>\-]/g,'').trim()}
function stagePosition(i){return i===0?'课程起点：建立基础认知':i===stages.value.length-1?'课程收束：综合迁移与验证':`课程中段：第 ${i+1} 个关键学习环节`}
function stagePositionDetail(i){const previous=stages.value[i-1]?.title;const next=stages.value[i+1]?.title;if(!previous)return `为后续“${next||'综合应用'}”建立共同基础。`;if(!next)return `整合“${previous}”并完成课程能力验证。`;return `承接“${previous}”，为“${next}”做好准备。`}
function stagePrerequisites(i){if(i===0)return '无需专门前置，从软件工程课程基础开始';const previous=stages.value[i-1];return (previous?.points||[]).slice(0,3).join('、')||previous?.title||'上一阶段核心内容'}
function stageOutcome(stage){const goal=clean(stage?.goal||'掌握本阶段核心知识并完成应用');return /^能够|^掌握|^理解|^建立|^完成/.test(goal)?goal:`能够${goal}`}
const stagePointKeywords=['问题定义','可行性研究','需求分析','需求规格','总体设计','详细设计','软件设计','编码实现','调试','软件测试','软件维护','软件生命周期','瀑布模型','用例图','类图','时序图','数据流图','模块划分','阶段衔接','阶段边界','阶段产物','输入输出','流程建构','产物驱动','质量闭环','案例应用','迁移应用'];
function parseStages(md){return String(md||'').split(/\n(?=##\s*阶段[一二三四五六七八九十\d]+)/).filter(b=>/^##\s*阶段/.test(b.trim())).map((b,i)=>({title:clean((b.split('\n')[0]||'').replace(/^##\s*阶段[一二三四五六七八九十\d]+[：:、.．\s]*/,''))||`学习阶段${i+1}`,goal:section(b,'目标')||section(b,'学习任务')||'围绕画像短板完成本阶段学习任务。',points:points(b),duration:(b.match(/(\d+)\s*天/)?.[1]?`预计${b.match(/(\d+)\s*天/)[1]}天`:`预计${i+2}天`),raw:b}))}
function section(b,l){const m=b.match(new RegExp(`\\*\\*${l}[：:]?\\*\\*\\s*([^\\n]+)`));return m?clean(m[1]):''}
function points(b){
  const block=String(b||'');
  const firstLine=clean((block.split('\n')[0]||'').replace(/^##\s*阶段[一二三四五六七八九十\d]+[：:、.．\s]*/,''));
  const goalText=section(block,'目标')||section(block,'学习任务')||'';
  const primaryText=`${firstLine} ${goalText}`;
  const secondaryText=block;
  const primaryHits=stagePointKeywords.filter(k=>primaryText.includes(k));
  const secondaryHits=stagePointKeywords.filter(k=>secondaryText.includes(k)&&!primaryHits.includes(k));
  const merged=[...primaryHits,...secondaryHits];
  if(merged.length)return [...new Set(merged)].slice(0,5);
  const titleChunks=firstLine.split(/[、，,：:·\s]+/).map(item=>clean(item)).filter(item=>item&&item.length>=2);
  return [...new Set(titleChunks.length?titleChunks:['课程核心知识'])].slice(0,4);
}
function fallback(){return resources.value.length?[{title:'基础概念澄清',goal:'理解核心概念、阶段产物和输入输出关系。',points:['软件生命周期','需求分析'],duration:'预计2天',raw:''},{title:'方法关系建构',goal:'建立需求分析、总体设计、详细设计之间的顺序关系。',points:['需求分析','总体设计','详细设计'],duration:'预计3天',raw:''},{title:'练习与实操巩固',goal:'通过练习、案例和代码实操完成迁移应用。',points:['软件测试','代码实操'],duration:'预计2天',raw:''}]:[]}
function kps(r){if(Array.isArray(r.knowledge_points))return r.knowledge_points;try{return JSON.parse(r.knowledge_points||'[]')}catch{return[]}}
function score(r,text){return kps(r).reduce((n,p)=>n+(p&&text.includes(p)?5:0),0)+['需求分析','总体设计','详细设计','测试','生命周期','代码','练习'].reduce((n,k)=>n+(text.includes(k)&&`${r.title} ${r.content}`.includes(k)?2:0),0)}
function resourceStageIndex(r){const meta=r.metadata||{};const idx=r.stage_index||meta.stage_index||meta.stage?.stage_index;const n=Number(idx);return Number.isFinite(n)?n:null}
function expectedStageResourceTypes(){return ['doc','mindmap','video','reading']}
function hasCompleteStageResources(items,stageCount){
  const count=Number(stageCount)||0;
  if(!count||!Array.isArray(items)||!items.length)return false;
  const expected=expectedStageResourceTypes();
  const coverage=new Map();
  items.forEach(item=>{
    const stageIndex=resourceStageIndex(item);
    const type=String(item?.resource_type||'').trim();
    if(!stageIndex||!type)return;
    if(!coverage.has(stageIndex))coverage.set(stageIndex,new Set());
    coverage.get(stageIndex).add(type);
  });
  for(let i=1;i<=count;i++){
    const types=coverage.get(i);
    if(!types)return false;
    for(const type of expected){
      if(!types.has(type))return false;
    }
  }
  return true;
}
function matchRes(s,i,total){const exact=resources.value.filter(r=>resourceStageIndex(r)===i+1);const text=`${s.title} ${s.goal} ${s.points.join(' ')} ${s.raw}`;const m=resources.value.filter(r=>!resourceStageIndex(r)&&score(r,text)>0);const list=exact.length?exact:(m.length?m:resources.value.filter((r,idx)=>!resourceStageIndex(r)&&(total?idx%total===i:true)));const order=['doc','mindmap','quiz','code','video','reading'];return [...list].sort((a,b)=>order.indexOf(a.resource_type)-order.indexOf(b.resource_type))}
function pickPrimaryDoc(docs, stage){
  const stageText = [stage.title, stage.goal, ...(stage.points||[])].join(' ');
  const scored = docs.map((doc, index) => {
    const payload = resourceJson(doc) || {};
    const mainTitle = cleanDocDisplayText(payload.main_explanation?.title || '');
    const title = cleanDocDisplayText(doc.title || '');
    const quality = qScore(doc);
    let hit = 0;
    (stage.points || []).forEach((point) => {
      if (mainTitle.includes(point) || title.includes(point)) hit += 3;
      if ((doc.content || '').includes(point)) hit += 1;
    });
    hit += score(doc, stageText);
    return { doc, total: quality + hit - index * 0.01 };
  });
  scored.sort((a,b) => b.total - a.total);
  return scored[0]?.doc || docs[0];
}
function mergedDocResource(items,stage){
  const docs = items.filter(r=>r.resource_type==='doc');
  if(!docs.length) return fallbackDocResource(stage);
  const primary = pickPrimaryDoc(docs, stage);
  const payload = resourceJson(primary);
  if(!payload) return fallbackDocResource(stage);
  return {
    ...primary,
    id:primary?.id||`merged-doc-${stage.title}`,
    title: payload.resourcetitle || primary.title || `${stage.title}·综合讲解文档`,
    content: JSON.stringify(payload),
    personalization: primary.personalization,
    knowledge_points: [...new Set([...(primary.knowledge_points||[]), ...(stage.points||[])])],
    quality_score: qScore(primary),
    sources: primary.sources || []
  };
}
function fallbackDocResource(stage){
  const content=fallbackDocJson([],stage);
  return {id:`fallback-doc-${stage.title}`,resource_type:'doc',title:`${stage.title}・综合讲解文档`,content:JSON.stringify(content),knowledge_points:stage.points||[],personalization:'依据当前阶段目标和知识点自动补齐讲解文档，确保每个阶段都有可学习的结构化讲义。',quality_score:86,sources:[]};
}
function mergeDocJson(jsonDocs,docs,stage){
  const first=jsonDocs[0]||{};
  const fallback=fallbackDocJson(docs,stage);
  const points=[...new Set(docs.flatMap(r=>kps(r)).concat(stage.points||[]))].filter(Boolean);
  const firstMain=jsonDocs.map(d=>d.main_explanation).find(item=>item&&item.content)||null;
  const mergedExplanations=uniqueByText(jsonDocs.flatMap(d=>d.knowledge_explanation||[]),item=>item.title).slice(0,2);
  const mainTitle=cleanDocDisplayText(firstMain?.title||mergedExplanations[0]?.title||points[0]||stage.title||'核心知识讲解');
  const mainContent=cleanDocDisplayText(firstMain?.content||mergedExplanations[0]?.explanation||'');
  return {
    ...first,
    resourcetype:'doc',
    resourcetitle:`${stage.title}・综合讲解文档`,
    weakpoints:first.weakpoints?.length?first.weakpoints:points,
    studygoal:first.studygoal||stage.goal,
    overview:first.overview||fallback.overview,
    main_explanation:{title:mainTitle,content:mainContent},
    core_concepts:uniqueByText(jsonDocs.flatMap(d=>d.core_concepts||[]),item=>item.name).slice(0,3),
    knowledge_explanation:mergedExplanations.filter(item=>cleanDocDisplayText(item.title)!==mainTitle).slice(0,2),
    mistakes:uniqueByText(jsonDocs.flatMap(d=>d.mistakes||[]),item=>item.mistake).slice(0,3),
    learningresources:jsonDocs.flatMap(d=>d.learningresources||[]),
    summary:first.summary||fallback.summary,
    self_check:uniqueByText(jsonDocs.flatMap(d=>d.self_check||[]),item=>item.question).slice(0,3),
    lifecycle_position:first.lifecycle_position||fallback.lifecycle_position,
    case_study:first.case_study||fallback.case_study,
    learning_path:first.learning_path||fallback.learning_path,
  };
}
function fallbackDocJson(docs,stage){
  const points=[...new Set(docs.flatMap(r=>kps(r)).concat(stage.points||[]))].filter(Boolean);
  const mainPoint=points[0]||stage.title||'课程核心知识';
  const evidence=docs.flatMap(r=>resourceJson(r)?.learningresources||[]).filter(Boolean);
  return {
    resourcetype:'doc',
    resourcetitle:`${stage.title}・讲解文档待生成`,
    knowledgelevel:'待观察',
    studystyle:'综合学习',
    weakpoints:points,
    studygoal:stage.goal||`理解${mainPoint}`,
    estimatedtime:'待知识库检索成功后生成',
    overview:{
      title:'知识库依据暂不可用',
      content:'当前阶段暂未检索到可用于生成讲解文档的课程知识库片段。为避免把泛化模板误展示为教材讲解，本页面不再自动编造核心知识解释。请重新生成资源，或检查知识库索引与检索结果。'
    },
    main_explanation:{title:mainPoint,content:''},
    core_concepts:[],
    knowledge_explanation:[],
    lifecycle_position:null,
    case_study:null,
    mistakes:[],
    learning_path:['检查当前阶段是否有课程知识库依据','重新生成学习资源','确认讲解文档中出现课程知识库来源后再学习'],
    summary:{
      key_takeaways:['当前讲解文档缺少知识库依据','系统已阻止泛化兜底讲解冒充教材内容','请重新生成或检查知识库检索配置'],
      one_sentence:'当前阶段讲解文档待基于知识库重新生成。'
    },
    self_check:[],
    learningresources:evidence
  };
}
function pickTypeResource(items,stage,type){
  const direct=items.find(r=>r.resource_type===type);
  if(direct)return direct;
  const pool=resources.value.filter(r=>r.resource_type===type);
  if(!pool.length)return null;
  const stageText=`${stage.title} ${stage.goal} ${(stage.points||[]).join(' ')}`;
  return [...pool].sort((a,b)=>score(b,stageText)-score(a,stageText))[0]||pool[0];
}
function fallbackReadingResource(stage){return {id:`fallback-reading-${stage.title}`,resource_type:'reading',title:`${stage.title}・拓展阅读`,content:'',knowledge_points:stage.points||[],personalization:'根据当前阶段目标自动补齐拓展阅读入口，便于继续扩展学习。',quality_score:82,sources:[]}}
const localCourseVideos=[
  {file:'03 软件生命周期.mp4',keys:['软件生命周期','生命周期']},
  {file:'07 可行性研究分析1.mp4',keys:['可行性研究','可行性分析']},
  {file:'08 可行性研究分析2.mp4',keys:['可行性研究','可行性分析']},
  {file:'12 需求分析任务.mp4',keys:['需求分析','需求任务']},
  {file:'13 需求收集.mp4',keys:['需求收集','需求获取']},
  {file:'19 验证需求（下）.mp4',keys:['验证需求','需求验证']},
  {file:'21 总体设计过程.mp4',keys:['总体设计','设计过程']},
  {file:'22 总体设计原理.mp4',keys:['总体设计','设计原理']},
  {file:'30 详细设计结构化程序.mp4',keys:['详细设计','结构化程序']},
  {file:'36 编码.mp4',keys:['编码','编码实现']},
  {file:'37 测试目标方法.mp4',keys:['软件测试','测试目标','测试方法']},
  {file:'40 维护工作.mp4',keys:['软件维护','维护工作']},
  {file:'04 瀑布模型.mp4',keys:['瀑布模型']},
  {file:'09 系统流程图和数据流图.mp4',keys:['数据流图','系统流程图']},
];
function localVideoUrlForStage(stage){
  const text=`${stage.title||''} ${stage.goal||''} ${(stage.points||[]).join(' ')}`;
  const hit=localCourseVideos.find(item=>item.keys.some(key=>text.includes(key)))||localCourseVideos[0];
  const base=(import.meta.env.VITE_API_BASE_URL||'http://localhost:5000/api').replace(/\/$/,'');
  return `${base}/knowledge/video?path=${encodeURIComponent(hit.file)}`;
}
function withStageVideoUrl(resource,stage){
  if(!resource||resource.resource_type!=='video')return resource;
  return videoUrl(resource)?resource:{...resource,video_url:localVideoUrlForStage(stage),format:resource.format||'local_video',personalization:resource.personalization||'根据当前阶段知识点自动匹配本地课程视频。'};
}
function fallbackVideoResource(stage){return withStageVideoUrl({id:`fallback-video-${stage.title}`,resource_type:'video',title:`${stage.title}・教学短视频`,content:'',knowledge_points:stage.points||[],personalization:'根据当前阶段知识点自动匹配本地课程视频。',quality_score:80,sources:[]},stage)}
function displayResources(items,stage){
  const mergedDoc=mergedDocResource(items,stage);
  const mindmap=stageMindmapResource(stage,items.find(r=>r.resource_type==='mindmap'));
  const video=withStageVideoUrl(pickTypeResource(items,stage,'video')||fallbackVideoResource(stage),stage);
  const reading=pickTypeResource(items,stage,'reading')||fallbackReadingResource(stage);
  return [mindmap,mergedDoc,video,reading].filter(Boolean);
}
function mindmapStageKind(stage){
  const text=`${stage.title||''} ${stage.goal||''} ${(stage.points||[]).join(' ')}`;
  if(/案例|迁移|应用|实操|项目|综合/.test(text))return 'application';
  if(/UML|用例图|类图|时序图|对象|建模/.test(text))return 'uml';
  if(/需求分析|需求规格|需求定义|用户需求|功能需求/.test(text))return 'requirement';
  if(/可行性|立项|经济|技术可行|操作可行/.test(text))return 'feasibility';
  if(/测试|用例设计|缺陷|回归|验证/.test(text))return 'test';
  if(/生命周期|瀑布|开发阶段|维护/.test(text))return 'lifecycle';
  if(/流程|衔接|关系|输入|输出|迁移/.test(text))return 'process';
  return 'concept';
}
function stageMindmapBranches(stage){
  const points=stage.points?.length?stage.points:['课程核心知识'];
  const goal=clean(stage.goal||'理解本阶段核心知识并完成迁移应用');
  const kind=mindmapStageKind(stage);
  const mainPoint=points[0]||stage.title||'课程核心知识';
  if(kind==='uml')return [
    ['建模目标',[`从需求描述抽取对象、角色和交互`,`把抽象文字转成可视结构`,goal]],
    ['用例图',[`识别参与者与系统边界`,`描述用户目标和系统服务`,`确认谁在什么时候触发系统行为`]],
    ['类图',[`抽取类、属性、操作和关系`,`检查泛化、关联、聚合等结构`,`为后续编码和数据库设计提供线索`]],
    ['时序图',[`按时间顺序表达消息交互`,`验证对象协作是否支撑用例`,`发现职责分配是否合理`]],
    ['模型联动',[`需求说明 → 用例图 → 类图 → 时序图`,`用模型互相校验遗漏和矛盾`,`从静态结构看到动态行为`]],
    ['学习检查',[`能否解释每种图解决什么问题`,`能否把课程案例映射到对应模型`,`能否发现建模和编码之间的联系`]],
  ];
  if(kind==='requirement')return [
    ['需求来源',[`用户访谈、业务流程、现有系统和课程案例`,`区分真实需求与实现设想`,`识别需求背后的业务目标`]],
    ['需求分类',[`功能需求：系统必须完成什么`,`非功能需求：性能、安全、易用性等约束`,`业务规则与数据约束也要显式写出`]],
    ['规格说明',[`边界、输入、输出、异常和验收标准`,`形成可沟通、可设计、可测试的文档`,`让开发和测试都能据此展开工作`]],
    ['验证确认',[`检查一致性、完整性和可验证性`,`避免过早进入设计实现`,`通过评审减少返工风险`]],
    ['向后衔接',[`为总体设计提供稳定输入`,`把含糊描述转成明确约束`,`为测试用例预留验收依据`]],
  ];
  if(kind==='feasibility')return [
    ['研究目标',[`判断项目是否值得做、能否做成`,`为后续立项和方案选择提供依据`,`避免盲目投入开发资源`]],
    ['技术可行性',[`现有技术、团队能力和系统集成难度`,`识别关键技术风险`,`比较不同实现路径的复杂度`]],
    ['经济可行性',[`成本、收益、投入周期和资源约束`,`比较不同方案的性价比`,`明确预算与回报之间的平衡`]],
    ['操作与进度',[`用户环境、组织流程和实施阻力`,`检查时间计划是否现实`,`评估团队和业务部门是否能配合`]],
    ['结论输出',[`可行、不可行或有条件可行`,`给出继续推进的建议`,`说明限制条件和后续注意事项`]],
  ];
  if(kind==='test')return [
    ['测试依据',[`需求规格、设计说明和用户场景`,`把质量目标转化为可检查条件`,`明确通过和失败标准`]],
    ['用例设计',[`输入数据、执行步骤和预期结果`,`覆盖正常、异常和边界情况`,`围绕高风险功能优先设计`]],
    ['执行记录',[`记录实际结果和缺陷现象`,`区分测试发现问题与调试修复问题`,`沉淀可追踪的测试证据`]],
    ['缺陷回归',[`定位修复后重新验证`,`确认修改没有引入新问题`,`把问题闭环到质量改进`]],
    ['质量视角',[`测试不是最后补救，而是持续验证`,`越早发现问题，修复成本越低`,`结果要能反向促进需求和设计修正`]],
  ];
  if(kind==='lifecycle')return [
    ['阶段序列',[`可行性研究 → 需求分析 → 设计 → 编码 → 测试 → 维护`,`理解每个阶段的输入和输出`,`明确阶段之间不是孤立存在`]],
    ['阶段产物',[`报告、规格说明、设计文档、代码、测试记录`,`产物为后续阶段提供依据`,`每份文档都服务于下一步决策`]],
    ['角色协作',[`用户、分析员、设计人员、开发人员、测试人员`,`不同角色关注点不同但目标一致`,`沟通质量会直接影响后续阶段效率`]],
    ['质量控制',[`评审、验证、变更管理和持续反馈`,`避免问题在后续阶段放大`,`把错误前移发现`]],
    ['整体认知',[`理解${mainPoint}在生命周期中的位置`,`能够说明它承接什么、输出什么`,`形成阶段递进意识`]],
  ];
  if(kind==='application')return [
    ['案例起点',[`先回看前置阶段结论和输入条件`,`明确当前案例要解决的真实问题`,`识别需要迁移的知识点：${points.join('、')}`]],
    ['操作步骤',[`把概念转成步骤、图示或判断规则`,`按“输入 → 处理 → 输出”拆解任务`,`让抽象知识变成可执行动作`]],
    ['结果产物',[`形成案例分析结论、检查表或阶段输出`,`支撑后续测试、评审或复盘`,`验证知识点是否真正被用起来`]],
    ['迁移应用',[`更换场景后还能复用同一套思路`,`比较不同项目中的共性与差异`,`训练举一反三能力`]],
    ['复盘提升',[`检查哪一步最容易出错`,`总结可重复使用的方法模板`,`把经验沉淀回知识框架`]],
  ];
  if(kind==='process')return [
    ['前置输入',[`先明确已有教材依据和阶段目标`,`识别需要承接的知识点：${points.join('、')}`,`判断本阶段不该混入哪些其他阶段内容`]],
    ['过程转换',[`把概念转成步骤、图示或判断规则`,`建立输入、处理、输出之间的关系`,`找到关键判断点和依赖条件`]],
    ['后续输出',[`形成可用于案例分析或测评的结论`,`支撑下一阶段学习任务`,`让学习结果能够继续传递`]],
    ['迁移应用',[`用课程案例验证流程是否成立`,`检查是否能解释相邻阶段关系`,`尝试在新情境下复用流程`]],
    ['常见偏差',[`只记顺序却说不清每步作用`,`只会背术语不会落到产物`,`忽略阶段边界导致内容混杂`]],
  ];
  return points.map(point=>[point,[`理解${point}解决的问题`,`掌握输入、输出、产物和判断标准`,`结合课程案例说明应用场景`,`说清它与前后知识点如何衔接`,`总结学习时最容易混淆的地方`]]);
}
function buildStageMindmapMarkdown(stage){
  const title=clean(stage.title||'阶段知识导图');
  const points=stage.points?.length?stage.points:['课程核心知识'];
  const branches=stageMindmapBranches(stage);
  const lines=[`# ${title}`,'## 阶段目标',`### ${clean(stage.goal||'理解本阶段核心知识')}`];
  lines.push('## 覆盖知识点');
  points.slice(0,5).forEach(point=>lines.push(`### ${point}`));
  lines.push('## 阶段定位');
  lines.push(`### 学习重心`);
  lines.push(`#### ${mindmapStageKind(stage)==='application'?'把知识点迁移到案例与任务中':'围绕本阶段知识点建立清晰、可应用的理解'}`);
  lines.push('### 与前后阶段关系');
  lines.push('#### 承接前一阶段的概念或产物');
  lines.push('#### 为下一阶段输出判断依据、文档或操作线索');
  lines.push('## 阶段专属框架');
  branches.forEach(([name,items])=>{lines.push(`### ${name}`);items.slice(0,4).forEach(item=>lines.push(`#### ${clean(item)}`));});
  lines.push('## 易错点提醒');
  points.slice(0,3).forEach(point=>lines.push(`### ${point}`,`#### 不要把${point}和相邻阶段任务混在一起`,`#### 先说清作用，再记定义和步骤`));
  lines.push('## 学习检查');
  lines.push('### 能否说清本阶段输入和输出');
  lines.push('### 能否把知识点应用到课程案例');
  lines.push('### 能否解释它与前后阶段的衔接');
  return lines.join('\n');
}
function fallbackMindmapResource(stage){return stageMindmapResource(stage)}
function stageMindmapResource(stage,source=null){
  const points=stage.points?.length?stage.points:['课程核心知识'];
  return {...(source||{}),id:source?.id||`stage-mindmap-${stage.title}`,resource_type:'mindmap',title:`${stage.title}阶段知识导图`,content:buildStageMindmapMarkdown(stage),knowledge_points:points,quality_score:qScore(source||{quality_score:88}),sources:source?.sources||[]};
}
function stageQuizResource(stage){return (stage.allResources||[]).find(r=>r.resource_type==='quiz')}
function stageFramework(stage){const points=(stage.points||[]).slice(0,3);if(points.length>=2)return `${points.join(' → ')} 框架`;if(points.length===1)return `${points[0]} 基础框架`;return '概念 → 案例 → 测评'}
function typeName(t){return({doc:'讲解文档',quiz:'基础练习题',reading:'拓展阅读',mindmap:'思维导图',code:'代码案例',video:'教学短视频'}[t]||t||'学习资源')}
function resourceIcon(t){return({doc:'📄',mindmap:'🧠',quiz:'✏️',code:'💻',video:'▶️',reading:'📖'}[t]||'📎')}
function resourceClass(r){return `res-${r.resource_type||'default'}`}
function rid(r){return`${r.id||r.resource_type}-${r.title}`}
function visibleLearningResource(){
  const stage=stages.value[activeStageIndex.value];
  if(!stage)return null;
  const activeId=activeResourceTabs.value[activeStageIndex.value];
  return (stage.resources||[]).find(item=>rid(item)===activeId&&Number(item.id)>0)||null;
}
async function flushLearningDuration(){
  const resource=trackedResource;
  if(!resource||!trackedSince)return;
  const now=Date.now();
  const durationSec=Math.floor((now-trackedSince)/1000);
  trackedSince=now;
  if(durationSec<2)return;
  try{
    await resourceApi.usage(resource.id,{duration_sec:durationSec,progress:0,completed:false});
  }catch{
    // A later heartbeat will continue recording without interrupting learning.
  }
}
function syncLearningDurationTracker(){
  const next=visibleLearningResource();
  if(rid(next||{})===rid(trackedResource||{}))return;
  void flushLearningDuration();
  trackedResource=next;
  trackedSince=next?Date.now():0;
}
function handleLearningVisibility(){
  if(document.hidden){void flushLearningDuration();return;}
  trackedSince=trackedResource?Date.now():0;
  syncLearningDurationTracker();
}
function hasModelError(t){const text=String(t||'');return /\{\s*"?success"?\s*:\s*false/i.test(text)||text.includes('调用失败')||text.includes('AppIdNoAuthError')||text.includes('NoAuth')||text.includes('anthropic/messages')}
function preview(r){const text=resourceText(r);return text.length>180?`${text.slice(0,180)}...`:text}
function extractJsonText(raw){return String(raw||'').replace(/^\s*```(?:json)?\s*/i,'').replace(/```\s*$/,'').replace(/^\s*json\s*/i,'').trim()}
function resourceJson(r){const raw=extractJsonText(r.content);const start=raw.indexOf('{'),end=raw.lastIndexOf('}');if(start<0||end<=start)return null;try{const data=JSON.parse(raw.slice(start,end+1));return data&&typeof data==='object'&&!Array.isArray(data)?data:null}catch{return null}}
function imageUrl(path){const base=import.meta.env.VITE_API_BASE_URL||'http://localhost:5000/api';return `${base}/knowledge/image?path=${encodeURIComponent(path)}`}
function resourceImages(r){const meta=r.metadata||{};const json=resourceJson(r);const found=[];const add=(img,caption='知识库配图')=>{if(!img)return;const item=typeof img==='string'?{path:img,caption}:img;if(item.path&&!found.some(x=>x.path===item.path))found.push(item)};(Array.isArray(meta.images)?meta.images:[]).forEach(add);(json?.images||[]).forEach(add);(json?.learningresources||[]).forEach(item=>(item.images||[]).forEach(img=>add(img,item.title||'知识库配图')));String(r.content||'').match(/images[\\/][^\n\r，,；;）)]+?\.(?:png|jpg|jpeg|webp|gif)/gi)?.forEach(path=>add(path,path));return found.slice(0,6)}
function stageResourceImages(stage){const found=[];const add=(img)=>{if(img?.path&&!found.some(item=>item.path===img.path))found.push(img)};(stage.allResources||stage.resources||[]).flatMap(resourceImages).forEach(add);return found.slice(0,8)}
function isMindmap(r){return r.resource_type==='mindmap'}
function isReading(r){return r.resource_type==='reading'}
function isDoc(r){return r.resource_type==='doc'}
function isVideo(r){return r.resource_type==='video'}
function isFixedResource(r){return isMindmap(r)||isVideo(r)}
function videoUrl(r){
  const meta=r.metadata||{};
  const json=resourceJson(r)||{};
  const raw=r.video_url||meta.video_url||meta.video?.url||meta.url||json.video_url||json.videoUrl||json.url||'';
  if(raw){
    const url=String(raw).trim();
    if(/^https?:\/\//.test(url))return url;
    if(url.startsWith('/api/'))return `${(import.meta.env.VITE_API_BASE_URL||'http://localhost:5000/api').replace(/\/api$/,'')}${url}`;
    return url;
  }
  const match=String(r.content||'').match(/https?:\/\/[^\s)"'<>]+\.(?:mp4|webm|ogg)(?:\?[^\s)"'<>]+)?/i);
  return match?.[0]||'';
}
function playableVideo(r){const url=videoUrl(r);return Boolean(url)&&!url.includes('example.com')}
function readingStageSections(stage,points){
  const text=`${stage?.title||''} ${stage?.goal||''} ${points.join(' ')}`;
  if(/需求分析|需求规格|需求定义/.test(text))return {
    intro:`本阶段的拓展阅读围绕${points.join('、')}展开，重点不是记住术语，而是把“用户到底要什么、系统边界在哪里、怎样写成可验证文档”这三件事真正看明白。`,
    connection:`阅读时请把${points.join('、')}和课程中的需求获取、需求分类、规格说明、验收标准联系起来，重点关注它如何为后续设计、开发和测试提供稳定输入。`,
    explanation:`可以继续补充阅读真实项目中的需求访谈记录、用户故事、需求规格说明片段和验收标准示例。这样能帮助你理解，需求分析不是单纯列功能，而是把模糊问题转成清晰约束。`,
    caseText:`例如在线学习系统如果没有提前定义“学习进度如何统计”“异常提交如何处理”“教师和学生权限边界”，后续设计和测试都会不断返工。需求写得越明确，后续阶段越顺畅。`,
    guide:['先看需求来自谁、解决什么业务问题','再看需求如何分类，以及哪些属于约束条件','接着观察规格说明如何描述输入、输出、异常和验收','最后尝试把课程案例改写成一小段规范需求描述'],
    questions:['如果只写功能名称，不写边界和验收标准，会导致什么问题？','需求分析和总体设计的分界线在哪里？','怎样判断一条需求已经足够清晰、可测试？'],
    explore:'进一步可以阅读用户故事、用例描述、需求优先级划分、原型评审和需求变更管理等材料，观察教材概念如何在真实团队协作中落地。'
  };
  if(/生命周期|瀑布|开发阶段|维护/.test(text))return {
    intro:`本阶段阅读的核心是把${points.join('、')}放回完整软件工程流程中理解，建立“阶段顺序、阶段产物、阶段依赖”的整体视角。`,
    connection:`你会看到这些知识点如何连接可行性研究、需求分析、设计、编码、测试与维护。阅读时不要孤立看某一阶段，而要观察它承接什么、又为谁提供输出。`,
    explanation:`可以补充阅读软件生命周期模型、阶段评审、文档交接、变更管理和维护反馈等内容。越能从整体上理解阶段协同，越不容易把课程知识记成零散术语。`,
    caseText:`如果团队在需求阶段没有沉淀明确文档，设计人员只能边猜边做；如果测试结果没有回流到需求和设计复盘，问题就会在维护阶段反复出现。这正体现了生命周期的闭环价值。`,
    guide:['先梳理阶段顺序，不急着记细节','再看每个阶段的典型输入、输出和角色','观察阶段产物如何传递到下一阶段','最后用一个项目案例串起完整流程'],
    questions:['为什么说生命周期强调的是阶段之间的依赖而不是简单顺序？','如果某个阶段产物质量很差，会最先影响谁？','维护阶段为什么也是学习和改进的重要来源？'],
    explore:'可以继续阅读瀑布模型、迭代模型、敏捷流程、持续交付和运维反馈机制，对比不同开发模式下阶段衔接方式的变化。'
  };
  if(/案例|迁移|应用|实操|项目/.test(text))return {
    intro:`这部分阅读重点在于把${points.join('、')}真正迁移到案例任务中，训练“看到一个场景，能知道该用什么知识、按什么步骤做”的能力。`,
    connection:`请把阅读内容和前面阶段学过的概念、流程、产物联系起来，看看它们在真实项目里如何组合成完整行动路径，而不是停留在定义层面。`,
    explanation:`适合补充阅读案例分析、任务拆解、阶段产物模板、缺陷复盘和项目总结等内容。它们能帮助你把抽象知识转成“可执行、可检查、可复用”的实践框架。`,
    caseText:`例如让你分析一个在线学习系统的功能上线流程时，不只是说“先需求再设计再测试”，而是要能指出每一步要看什么材料、输出什么结论、如何判断是否可以进入下一步。`,
    guide:['先定位案例对应的软件工程阶段','再把知识点映射成步骤或判断规则','记录每一步产生的结果和证据','最后复盘哪些知识点可以迁移到其他案例'],
    questions:['如果换一个项目场景，这套分析思路还能复用吗？','案例中最关键的输入和输出是什么？','哪一步最容易凭感觉跳过，从而导致后续风险？'],
    explore:'可以继续阅读项目案例复盘、检查清单设计、阶段评审模板和质量改进记录，把课程知识转化成自己的做题或分析模板。'
  };
  return {
    intro:`围绕“${points.join('、')||'课程核心知识'}”进行拓展阅读，可以把教材中的概念、流程和阶段产物放到真实软件项目中理解。很多软件工程知识并不是为了考试而存在，而是为了帮助团队降低沟通成本、控制质量风险，并让需求、设计、测试和维护之间形成闭环。`,
    connection:`这些内容对应课程中的概念定义、流程活动、阶段产物和质量保障问题。学习时建议重点关注三个问题：它解决什么问题、需要什么输入、会产生什么输出。如果能把这三个问题讲清楚，说明你已经从记忆概念进入到理解应用阶段。`,
    explanation:`在实际项目中，${points.join('、')||'这些知识点'}通常会和需求管理、缺陷跟踪、版本控制、持续集成、质量评审等活动结合。补充阅读的价值在于帮助你看到教材知识背后的协作逻辑和工程目的。`,
    caseText:`假设团队正在开发一个在线学习系统。如果前期分析没有明确关键规则，后续设计和测试就会出现反复返工。相反，如果阶段输入、输出和验收标准已经说清，整个流程就会更顺畅。`,
    guide:['第一遍先看概念之间的关系，不必纠结细节','第二遍关注输入、过程、输出和参与角色','第三遍结合课程案例，尝试画出流程图或检查清单','最后用阶段测评检验自己能否迁移应用'],
    questions:['这些知识点在软件生命周期中处于什么位置？','它们会影响哪些后续阶段？','如果忽略这些活动，会造成哪些质量风险？','如何用一个课程案例说明它们的作用？'],
    explore:'探索建议：可以继续了解敏捷开发、DevOps、自动化测试、需求管理平台、缺陷生命周期管理和软件质量度量。学习时不需要追求工具细节，而要观察这些工具如何把教材中的概念变成可执行流程。'
  };
}
function readingText(r,stage={}){
const text=resourceText(r);if(text&&text.length>220)return text;const points=[...new Set([...(stage.points||[]),...kps(r)])].filter(Boolean);const sections=readingStageSections(stage,points);return `# ${r.title||`${points.join('、')||'课程核心知识'}拓展阅读`}

## 为什么值得读
${sections.intro}

## 与课程知识点的连接
${sections.connection}

## 拓展知识讲解
${sections.explanation}

## 真实场景示例
${sections.caseText}

## 阅读导读
${sections.guide.map(item=>`- ${item}`).join('\n')}

## 思考问题
${sections.questions.map(item=>`- ${item}`).join('\n')}

## 进一步探索方向
${sections.explore}`;}
function readingSectionRaw(markdown,title){
  const pattern=new RegExp(`##\s*${title}\s*\n([\s\S]*?)(?=\n##\s+|$)`);
  return markdown.match(pattern)?.[1]||'';
}
function readingSection(markdown,title){return cleanDocDisplayText(readingSectionRaw(markdown,title));}
function readingBullets(markdown,title){
  const raw=readingSectionRaw(markdown,title);
  return raw.split(/\n\s*[-•]\s+/).map(cleanDocDisplayText).filter(Boolean).slice(0,4);
}
function renderReading(r,stage={}){
  const markdown=readingText(r,stage);
  const points=[...new Set([...(stage.points||[]),...kps(r)])].filter(Boolean).slice(0,4);
  const intro=readingSection(markdown,'为什么值得读')||resourceText(r)||stage.goal||'通过拓展阅读，把本阶段知识点放到更完整的软件工程场景中理解。';
  const connection=readingSection(markdown,'与课程知识点的连接')||`本阅读围绕${points.join('、')||'课程核心知识'}展开，帮助你理解概念、流程、产物和应用边界。`;
  const explanation=readingSection(markdown,'拓展知识讲解')||'';
  const caseText=readingSection(markdown,'真实场景示例')||'';
  const guide=readingBullets(markdown,'阅读导读');
  const questions=readingBullets(markdown,'思考问题');
  const explore=readingSection(markdown,'进一步探索方向');
  const lines=[`> 预计时长：20分钟 · 关键词：${points.join('、')||'课程核心知识'}`,''];
  lines.push('## 本阶段阅读导入',cleanDocDisplayText(intro),'');
  lines.push('## 与课程知识点的连接',cleanDocDisplayText(connection),'');
  if(explanation)lines.push('## 拓展知识讲解',cleanDocDisplayText(explanation),'');
  if(caseText)lines.push('## 真实场景示例',cleanDocDisplayText(caseText),'');
  if(guide.length){lines.push('## 阅读导读');guide.forEach((item,index)=>lines.push(`${index+1}. ${item}`));lines.push('')}
  if(questions.length){lines.push('## 思考问题');questions.forEach(item=>lines.push(`- ${item}`));lines.push('')}
  if(explore)lines.push('## 进一步探索方向',cleanDocDisplayText(explore));
  return markdownRenderer.render(lines.filter(line=>line!==null&&line!==undefined).join('\n'));
}
function cleanDocDisplayText(value){
  return clean(String(value||''))
    .replace(/\\n/g,' ')
    .replace(/\{\s*"?query"?[\s\S]*$/i,'')
    .replace(/retrieved_chunks[\s\S]*$/i,'').replace(/章节路径：[^\n\r]+/g,'').replace(/页码：[^\n\r]+/g,'').replace(/标题：/g,'').replace(/内容：/g,'').replace(/结合课程知识库内容可知：/g,'')
    .replace(/[A-Z]:\\[^\s，。；]+/g,'')
    .replace(/\s{2,}/g,' ')
    .trim();
}
function uniqueByText(items,getter){const seen=new Set();return (items||[]).filter(item=>{const key=cleanDocDisplayText(getter(item)).slice(0,60);if(!key||seen.has(key))return false;seen.add(key);return true})}
function renderDoc(r,stage){
  const data=resourceJson(r)||{};
  const points=[...new Set([...(stage.points||[]),...kps(r)])].filter(Boolean).slice(0,4);
  const overview=cleanDocDisplayText(data.overview?.content||data.content||stage.goal||resourceText(r));
  const mainTitle=cleanDocDisplayText(data.main_explanation?.title||points[0]||stage.title||'核心知识讲解');
  const mainContent=cleanDocDisplayText(data.main_explanation?.content||data.main_explanation?.explanation||'');
  const concepts=uniqueByText(data.core_concepts||[],item=>item.name).slice(0,3);
  const explanations=uniqueByText(data.knowledge_explanation||[],item=>item.title).filter(item=>cleanDocDisplayText(item.title)!==mainTitle).slice(0,1);
  const mistakes=uniqueByText(data.mistakes||[],item=>item.mistake).slice(0,3);
  const checks=uniqueByText(data.self_check||[],item=>item.question).slice(0,3);
  const learningPath=uniqueByText((data.learning_path||[]).map(item=>({text:item})),item=>item.text).slice(0,3);
  const lines=[`> 预计时长：${cleanDocDisplayText(data.estimatedtime||data.studytimepreferred||'25分钟')} · 关键词：${points.join('、')||'课程核心知识'}`,''];
  if(overview)lines.push('## 本阶段学习导入',overview,'');
  if(mainContent) lines.push(`## 核心知识讲解：${mainTitle}`, mainContent, '');
  if(concepts.length){lines.push('## 相关核心概念');concepts.forEach(item=>{lines.push(`### ${cleanDocDisplayText(item.name)}`,cleanDocDisplayText(item.definition||item.why_it_matters||''));if(item.example)lines.push(`- 示例：${cleanDocDisplayText(item.example)}`);if(item.common_misunderstanding)lines.push(`- 易错：${cleanDocDisplayText(item.common_misunderstanding)}`);lines.push('')})}
  if(explanations.length){lines.push('## 补充知识点');explanations.forEach(item=>{lines.push(`### ${cleanDocDisplayText(item.title)}`,cleanDocDisplayText(item.explanation));if(item.process?.length)lines.push(`- 学习步骤：${item.process.map(cleanDocDisplayText).filter(Boolean).join(' → ')}`);if(item.input_output)lines.push(`- 输入：${cleanDocDisplayText(item.input_output.input)}；输出：${cleanDocDisplayText(item.input_output.output)}`);if(item.example)lines.push(`- 案例：${cleanDocDisplayText(item.example)}`);if(item.exam_focus)lines.push(`- 考查重点：${cleanDocDisplayText(item.exam_focus)}`);lines.push('')})}
  if(data.lifecycle_position){lines.push('## 在软件生命周期中的位置',`${cleanDocDisplayText(data.lifecycle_position.phase||'当前阶段')}：${cleanDocDisplayText(data.lifecycle_position.connection||'理解本阶段和前后续活动的关系。')}`,'');}
  if(data.case_study){lines.push(`## ${cleanDocDisplayText(data.case_study.title||'课程项目案例分析')}`);['scenario','analysis','takeaway'].forEach(key=>{if(data.case_study[key])lines.push(`- ${cleanDocDisplayText(data.case_study[key])}`)});lines.push('')}
  if(mistakes.length){lines.push('## 常见误区与纠正');mistakes.forEach(item=>{lines.push(`- **${cleanDocDisplayText(item.mistake)}**：${cleanDocDisplayText(item.correction||item.reason||item.example)}`)});lines.push('')}
  if(learningPath.length){lines.push('## 推荐学习路径');learningPath.forEach((item,index)=>lines.push(`${index+1}. ${cleanDocDisplayText(item.text)}`));lines.push('')}
  if(data.summary){lines.push('## 阶段小结');if(data.summary.one_sentence)lines.push(cleanDocDisplayText(data.summary.one_sentence));(data.summary.key_takeaways||[]).slice(0,3).forEach(item=>lines.push(`- ${cleanDocDisplayText(item)}`));lines.push('')}
  if(checks.length){lines.push('## 自测问题');checks.forEach(item=>lines.push(`- **${cleanDocDisplayText(item.question)}**  ${cleanDocDisplayText(item.hint)}`));}
  return markdownRenderer.render(lines.filter(line=>line!==null&&line!==undefined).join('\n'));
}
function normalizeMindmapRoot(title){
  const text=clean(String(title||'').replace(/个性化|知识思维导图|思维导图|阶段知识导图|软件工程知识导图/g,'')).trim();
  return text||'软件工程核心知识';
}
function mindmapPointProfile(point){
  const name=String(point||'知识点');
  if(name.includes('软件生命周期'))return {meaning:'理解软件从提出想法到退役维护的完整过程',focus:'区分需求、设计、实现、测试、维护等阶段的任务和产物',usage:'判断当前课程案例处于哪个开发阶段，以及前后阶段如何衔接',pitfall:'不要把生命周期等同于某一个具体步骤，它强调阶段顺序和相互影响'};
  if(name.includes('可行性'))return {meaning:'判断项目在技术、经济、操作和进度等方面是否值得继续推进',focus:'掌握可行性分析的维度、结论形式和对立项决策的影响',usage:'在项目前期判断方案是否可做、是否划算、是否适合用户环境',pitfall:'不要把可行性研究写成需求列表，它更关注是否值得做和能否做成'};
  if(name.includes('数据流图'))return {meaning:'用图形方式描述系统中数据如何输入、处理、存储和输出',focus:'识别外部实体、处理过程、数据流和数据存储之间的关系',usage:'把文字需求转成结构化流程，帮助发现遗漏的数据输入和输出',pitfall:'不要把数据流图画成程序流程图，它描述数据流动而不是代码执行顺序'};
  if(name.includes('需求分析'))return {meaning:'明确用户真正需要系统完成什么，以及系统边界在哪里',focus:'区分功能需求、非功能需求、约束条件和需求规格说明',usage:'把用户描述整理成可沟通、可验证、可设计的需求文档',pitfall:'不要过早进入技术实现，需求分析阶段重点是弄清问题而不是写方案'};
  if(name.includes('总体设计'))return {meaning:'从整体上规划系统架构、模块划分和主要接口关系',focus:'理解系统结构、模块职责、数据设计和关键技术路线',usage:'把需求转化为系统级设计蓝图，为详细设计和编码提供依据',pitfall:'不要陷入函数细节，总体设计关注的是整体结构和模块协作'};
  if(name.includes('详细设计'))return {meaning:'把总体设计中的模块进一步细化为可实现的过程、接口和数据结构',focus:'掌握算法逻辑、接口参数、数据结构和模块内部处理流程',usage:'指导编码实现，减少开发时对模块行为的理解偏差',pitfall:'不要只描述模块名称，要说明模块内部如何完成处理'};
  if(name.includes('测试'))return {meaning:'通过设计和执行测试用例发现软件缺陷并验证质量',focus:'理解测试目标、测试用例、测试阶段和缺陷定位之间的关系',usage:'根据需求和设计结果检查系统是否满足预期功能和质量要求',pitfall:'不要把测试等同于调试，测试是发现问题，调试是定位并修复问题'};
  return {meaning:`理解${name}在软件工程过程中的作用和边界`,focus:'掌握它解决的问题、依赖的信息、产生的结果和评价标准',usage:`结合课程项目判断${name}应该在什么场景下使用`,pitfall:'不要只背概念名称，要能说清它和相近知识点的区别'};
}
function mindmapPointDetails(point){
  const item=mindmapPointProfile(point);
  return [
    '#### 含义：'+item.meaning,
    '#### 重点：'+item.focus,
    '#### 应用：'+item.usage,
    '#### 易错：'+item.pitfall
  ].join('\n');
}
function normalizeMindmapMarkdown(r){
  const rootTitle=normalizeMindmapRoot(r.title||kps(r)[0]);
  const raw=extractJsonText(r.content||'').replace(/center[_\s-]*topic|center\s*theme|root\(\(|\)\)|mindmap/gi,'').trim();
  const rawLines=raw.split('\n').map(line=>line.trim()).filter(line=>line&&!/images[\\/]/i.test(line)&&!/知识库配图/.test(line));
  const points=[...new Set(kps(r).filter(Boolean))].slice(0,8);
  const hasGenericDetails=rawLines.some(line=>/理解.*解决什么问题|掌握输入、过程、输出和阶段产物|不要只记名称/.test(line));
  if(rawLines.some(line=>line.startsWith('#'))&&!hasGenericDetails){
    const cleanedLines=rawLines.map(line=>line.replace(/^[+\-–—]+\s*/,'').replace(/\s+/g,' ').trim()).filter(Boolean);
    const existing=cleanedLines.join('\n');
    const extraPoints=points.filter(point=>!existing.includes(point));
    const normalized=cleanedLines.map((line,index)=>index===0&&line.startsWith('#')?'# '+rootTitle:line).join('\n');
    const additions=extraPoints.length?['## 补充知识点解释',...extraPoints.map(point=>'### '+point+'\n'+mindmapPointDetails(point))].join('\n'):'';
    return (normalized.startsWith('#')?normalized:'# '+rootTitle+'\n'+normalized)+(additions?'\n'+additions:'');
  }
  const modules=points.length?points:[rootTitle,'核心概念','易错点'];
  return ['# '+rootTitle,'## 知识点展开',...modules.map(point=>'### '+point+'\n'+mindmapPointDetails(point)),'## 学习路径','### 先理解概念\n#### 明确基本定义\n#### 找到输入输出和阶段产物','### 再结合案例\n#### 用教材案例验证理解\n#### 对照项目流程定位知识点','### 最后练习评估\n#### 通过题目检查掌握程度\n#### 根据错题回到对应知识点'].join('\n');
}
function setMarkmapRef(r,el){
  const id=rid(r);
  if(el)markmapEls.set(id,el);else markmapEls.delete(id);
}
function setMarkmapViewportRef(r,el){
  const id=rid(r);
  if(el)markmapViewports.set(id,el);else markmapViewports.delete(id);
}
function ensureMindmapView(r){
  const id=rid(r);
  if(!markmapViews.value[id]){
    markmapViews.value={...markmapViews.value,[id]:{scale:1,x:0,y:0,fitted:false}};
  }
  return markmapViews.value[id];
}
function handleMindmapWheel(event,r){
  const id=rid(r);
  const view=ensureMindmapView(r);
  const currentScale=view.scale;
  const delta=event.deltaY<0?0.1:-0.1;
  const next=Math.max(0.7,Math.min(2.2,Number((currentScale+delta).toFixed(2))));
  if(next===currentScale)return;
  const viewport=markmapViewports.get(id)||event.currentTarget;
  const rect=viewport.getBoundingClientRect();
  const offsetX=event.clientX-rect.left-view.x;
  const offsetY=event.clientY-rect.top-view.y;
  const ratio=next/currentScale;
  view.x-=offsetX*(ratio-1);
  view.y-=offsetY*(ratio-1);
  view.scale=next;
  view.fitted=true;
  markmapViews.value={...markmapViews.value,[id]:{...view}};
}
function mindmapZoomStyle(r){
  const view=ensureMindmapView(r);
  return {transform:`translate(${view.x}px, ${view.y}px) scale(${view.scale})`,transformOrigin:'top left'};
}
function isMindmapDragging(r){
  return mindmapDragState.value.active&&mindmapDragState.value.id===rid(r);
}
function isMindmapNodeTarget(target){
  return Boolean(target?.closest?.('.markmap-node'));
}
function startMindmapDrag(event,r){
  if(event.button!==0)return;
  if(isMindmapNodeTarget(event.target))return;
  const id=rid(r);
  const viewport=markmapViewports.get(id)||event.currentTarget;
  if(!viewport)return;
  const view=ensureMindmapView(r);
  mindmapDragState.value={
    id,
    active:true,
    startX:event.clientX,
    startY:event.clientY,
    originX:view.x,
    originY:view.y
  };
  window.addEventListener('mousemove',handleMindmapDragMove);
  window.addEventListener('mouseup',stopMindmapDrag);
}
function handleMindmapDragMove(event){
  const state=mindmapDragState.value;
  if(!state.active||!state.id)return;
  const view=markmapViews.value[state.id];
  if(!view)return;
  const dx=event.clientX-state.startX;
  const dy=event.clientY-state.startY;
  view.x=state.originX+dx;
  view.y=state.originY+dy;
  view.fitted=true;
  markmapViews.value={...markmapViews.value,[state.id]:{...view}};
}
function stopMindmapDrag(){
  if(!mindmapDragState.value.active)return;
  mindmapDragState.value={id:'',active:false,startX:0,startY:0,originX:0,originY:0};
  window.removeEventListener('mousemove',handleMindmapDragMove);
  window.removeEventListener('mouseup',stopMindmapDrag);
}
async function fitMindmapToViewport(r){
  const mm=markmapInstances.get(rid(r));
  const el=markmapEls.get(rid(r));
  if(!mm||!el)return;
  const view=ensureMindmapView(r);
  view.fitted=false;
  await fitMarkmap(mm,el,r,true);
}
async function fitMarkmap(mm,el,r,force=false){
  const viewport=markmapViewports.get(rid(r));
  if(!viewport||!el)return;
  const current=ensureMindmapView(r);
  if(current.fitted&&!force)return;
  if(viewport.clientWidth<10||viewport.clientHeight<10)return;
  markmapViews.value={
    ...markmapViews.value,
    [rid(r)]:{scale:1,x:0,y:0,fitted:false}
  };
  await nextTick();
  await mm.fit(1.72);
  markmapViews.value={
    ...markmapViews.value,
    [rid(r)]:{scale:1,x:0,y:0,fitted:true}
  };
}
async function renderMarkmaps(){
  await nextTick();
  const stage=stages.value[activeStageIndex.value];
  if(!stage)return;
  for(const r of stage.resources||[]){
      if(!isMindmap(r)||activeResourceTabs.value[activeStageIndex.value]!==rid(r))continue;
      const id=rid(r);
      const el=markmapEls.get(id);
      const viewport=markmapViewports.get(id);
      if(!el||!viewport||viewport.clientWidth<10||viewport.clientHeight<10)continue;
      const {root}=markmapTransformer.transform(normalizeMindmapMarkdown(r));
      const options={autoFit:false,pan:false,zoom:false,duration:260,maxWidth:300,spacingVertical:8,spacingHorizontal:62,color:(node)=>['#2563eb','#7c3aed','#16a34a','#f97316'][node.state.depth%4]||'#64748b'};
      if(markmapInstances.has(id)){
        const mm=markmapInstances.get(id);
        await mm.setData(root);
        const view=ensureMindmapView(r);
        view.fitted=false;
        await fitMarkmap(mm,el,r);
      }else{
        const mm=Markmap.create(el,options);
        markmapInstances.set(id,mm);
        await mm.setData(root);
        await fitMarkmap(mm,el,r);
      }
  }
}
function refitAllMarkmaps(){
  for(const s of stages.value){
    for(const r of s.resources||[]){
      if(!isMindmap(r))continue;
      const mm=markmapInstances.get(rid(r));
      const el=markmapEls.get(rid(r));
      if(!mm||!el)continue;
      const view=ensureMindmapView(r);
      view.fitted=false;
      fitMarkmap(mm,el,r,true);
    }
  }
}
function pagesText(value){return Array.isArray(value)?value.join('、'):String(value||'')}
function resourceText(r){const raw=String(r.content||r.personalization||'点击学习资源页面查看完整内容。');if(hasModelError(raw))return `${typeName(r.resource_type)}已挂载到当前阶段，建议结合本阶段目标学习对应内容。`;const parsed=resourceJson(r);if(parsed)return clean(parsed.content||parsed.studygoal||parsed.resourcetitle||r.title);return clean(extractJsonText(raw))}
function resourceOpen(r){const id=rid(r);return openResources.value[id]??true}
function usesButtonToggleOnly(r){return isDoc(r)||isReading(r)}
function resourceCardClick(r){if(isFixedResource(r)||usesButtonToggleOnly(r))return;toggleResource(r)}
function openResourceDetail(resource,type){detailDialog.value={visible:true,type,resource}}
function toggleResource(r){const id=rid(r);openResources.value={...openResources.value,[id]:!openResources.value[id]}}
function toggleStage(i){if(i>current.value&&!done(i)){ElMessage.warning('请先完成前置阶段，再解锁后续学习内容');return}openStages.value={...openStages.value,[i]:!(openStages.value[i]??i===current.value)}}
function q(r){return r.quality||r.metadata?.quality||{}}function qScore(r){return Number(r.quality_score||q(r).total||80)}function qPass(r){return q(r).passed!==false&&qScore(r)>=75}
function sourceText(r){const n=evidenceSources(r).length;return n?`已关联 ${n} 条可追溯课程证据，并保留防幻觉审核信息。`:'建议在资源页复核课程依据。'}
function evidenceSources(r){
  const json=resourceJson(r)||{};
  const metadata=r.metadata||{};
  const detailed=[...(Array.isArray(metadata.evidence)?metadata.evidence:[]),...(Array.isArray(json.learningresources)?json.learningresources:[])];
  const fallback=Array.isArray(r.sources)?r.sources:[];
  const normalized=[...detailed,...fallback].map((item)=>{
    const path=item.section_path||item.sectionpath||item.path||[];
    const pathParts=Array.isArray(path)?path.map((part)=>String(part).trim()).filter(Boolean):String(path||'').split(/\s*[/＞>]\s*/).map((part)=>part.trim()).filter(Boolean);
    const pages=item.pages||item.page||[];
    return {
      title:String(item.title||item.section_title||item.source||item.source_name||'课程知识库证据').trim(),
      section_path:pathParts.join(' / '),
      section_title:String(item.section_title||pathParts[pathParts.length-1]||'').trim(),
      pages:Array.isArray(pages)?pages.join('、'):String(pages||''),
      source_file:String(item.source_file||item.source||item.source_name||'').trim(),
      chunk_index:item.chunk_index??'',
      content_preview:String(item.content_preview||item.content||'').trim().slice(0,120),
      node_id:String(item.section_node_id||item.node_id||'').trim(),
    };
  });
  const seen=new Set();
  return normalized.filter((item)=>{const key=`${item.title}|${item.section_path}|${item.chunk_index}`;if(seen.has(key))return false;seen.add(key);return Boolean(item.title)}).slice(0,8);
}
function openEvidenceSource(source){
  detailDialog.value.visible=false;
  router.push({path:'/knowledge',query:{evidence:source.title,section:source.section_title||undefined,path:source.section_path||undefined,nodeId:source.node_id||undefined,source:source.source_file||undefined,page:source.pages||undefined,chunk:source.chunk_index!==''?String(source.chunk_index):undefined}});
}
function done(i){return completed.value.includes(i)}function state(i){return done(i)?'completed':i===current.value?'current':'pending'}function label(i){return{completed:'已完成',current:'当前阶段',pending:'未开始'}[state(i)]}function tag(i){return{completed:'success',current:'primary',pending:'info'}[state(i)]}
async function toggle(i){
  const stage=stages.value[i];
  if(!stage)return;
  const nextCompleted=!done(i);
  const previous=[...completed.value];
  const nextList=nextCompleted?[...completed.value,i]:completed.value.filter(x=>x!==i);
  completed.value=nextList;
  localStorage.setItem('a3_path_done',JSON.stringify(nextList));
  try{
    const sessionId=currentSessionId();
    const res=await pathApi.saveStageProgress({stage_index:i+1,stage_title:stage.title,completed:nextCompleted,knowledge_points:stage.points||[],path_id:latest.value?.id||integrated.value?.path_id||null},sessionId);
    if(res.code!==200)throw new Error(res.msg||'阶段进度保存失败');
    if(nextCompleted){const added=res.data?.knowledge_jar_added||[];jarPoints.value=new Set([...jarPoints.value,...(stage.points||[])]);if(added.length)ElMessage.success(`阶段完成，${added.length} 个知识点已自动加入收藏瓶`)}
    window.dispatchEvent(new CustomEvent('a3-profile-session-refresh'));
  }catch(e){
    completed.value=previous;
    localStorage.setItem('a3_path_done',JSON.stringify(previous));
    ElMessage.error(e?.message||'阶段进度保存失败');
  }
}
function isJarCollected(point){return jarPoints.value.has(String(point||'').trim())}
async function loadKnowledgeJar(){const res=await knowledgeJarApi.list();if(res.code===200)jarPoints.value=new Set((res.data?.items||[]).map(item=>String(item.knowledge_point||'').trim()).filter(Boolean))}
async function toggleJarPoint(point,stage,index){const value=String(point||'').trim();if(!value||jarBusy.value)return;jarBusy.value=value;try{const collected=isJarCollected(value);const payload={knowledge_point:value,source:'manual',source_label:'学习路径手动收藏',stage_index:index+1,stage_title:stage.title};const res=collected?await knowledgeJarApi.remove(payload):await knowledgeJarApi.collect(payload);if(res.code!==200)throw new Error(res.msg||'收藏操作失败');const next=new Set(jarPoints.value);collected?next.delete(value):next.add(value);jarPoints.value=next;ElMessage.success(collected?'已从收藏瓶移出':'已加入知识收藏瓶')}catch(error){ElMessage.error(error?.message||'收藏操作失败')}finally{jarBusy.value=''}}
function ensureActiveResourceTabs(){
  const next={...activeResourceTabs.value};
  stages.value.forEach((stage,index)=>{
    const first=stage.resources?.[0];
    if(first&&!next[index])next[index]=rid(first);
  });
  activeResourceTabs.value=next;
}
function onResourceTabChange(){
  nextTick(()=>renderMarkmaps());
}
function selectStage(i){if(i>current.value&&!done(i)){ElMessage.warning('请先完成前置阶段，再解锁后续学习内容');return}activeStageIndex.value=i;ensureActiveResourceTabs();renderMarkmaps()}
function prevStage(){if(activeStageIndex.value>0)selectStage(activeStageIndex.value-1)}
async function nextStage(){const i=activeStageIndex.value;if(!done(i)){await toggle(i)}if(i<stages.value.length-1)selectStage(i+1)}
function stageRecord(i){return assessmentRecords.value.find(item=>Number(item.stageIndex)===i)}
function loadAssessmentRecords(){try{assessmentRecords.value=JSON.parse(localStorage.getItem('a3_stage_assessment_records')||'[]')}catch{assessmentRecords.value=[]}}
function goStageEvaluation(s,i){router.push({path:'/evaluation',query:{stage:String(i),from:'path',title:s.title,points:(s.points||[]).join('、')}})}
function currentSessionId(){return String(route.query.sessionId||activeProfileSessionId()||'')}
function toArray(value, keys=[]){
  if(Array.isArray(value))return value;
  if(value&&typeof value==='object'){
    for(const key of keys){
      if(Array.isArray(value[key]))return value[key];
    }
    for(const key of ['data','list','items','rows','records','paths','resources','resource_list']){
      if(Array.isArray(value[key]))return value[key];
    }
    if(value.path_content||value.resource_type||value.id)return [value];
  }
  return [];
}
function pathList(value){return toArray(value,['paths','path_list','list','items','records']).filter(item=>item&&typeof item==='object')}
function resourceList(value){return toArray(value,['resources','resource_list','list','items','records']).filter(item=>item&&typeof item==='object')}
async function loadAll(sessionId=currentSessionId()){
  const token=++pathLoadToken;
  const[ig,p,r,pf,sp]=await Promise.all([pathApi.integrated(sessionId),pathApi.list(sessionId),resourceApi.list(sessionId),profileApi.get(sessionId),pathApi.stageProgress(sessionId)]);
  if(token!==pathLoadToken)return;
  if(ig.code===200)integrated.value=ig.data||{};
  if(p.code===200)paths.value=pathList(p.data);
  if(r.code===200){
    const integratedResources=resourceList(ig.code===200?ig.data?.resources:[]);
    const listedResources=resourceList(r.data);
    resources.value=listedResources.length?listedResources:integratedResources;
  }
  if(pf.code===200)profile.value=pf.data||{};
  if(sp.code===200&&Array.isArray(sp.data?.items)){completed.value=sp.data.items.filter(item=>item.completed).map(item=>Math.max(Number(item.stage_index||0)-1,0));localStorage.setItem('a3_path_done',JSON.stringify(completed.value))}else{try{completed.value=JSON.parse(localStorage.getItem('a3_path_done')||'[]')}catch{completed.value=[]}}
  loadAssessmentRecords();
  await nextTick();
  if(token!==pathLoadToken)return;
  ensureActiveResourceTabs();
  await loadKnowledgeJar();
}
async function generateAll(extra='',forceResources=false){
  loading.value=true;progress.value=5;resetAgentSteps();
  const timer=setInterval(()=>progress.value=Math.min(progress.value+3,94),700);
  try{
    const need=[profile.value.study_goal,profile.value.error_prone_points||profile.value.weak_points,hint.value,extra].filter(Boolean).join('；');
    setAgentStep('PlannerAgent','running','规划中');progress.value=14;
    const sessionId=currentSessionId();
    const pr=await pathApi.generate({learning_need:need,adjustment:hint.value},sessionId);
    if(pr.code!==200)throw new Error(pr.msg||'学习路径生成失败');
    if(pr.data?.path_content){
      const currentPaths=pathList(paths.value);
      paths.value=[pr.data,...currentPaths.filter(item=>item.id!==pr.data.id)];
    }
    setAgentStep('PlannerAgent','done','已完成');
    setAgentStep('RetrieverAgent','running','检索中');progress.value=32;
    await new Promise(resolve=>setTimeout(resolve,350));
    setAgentStep('RetrieverAgent','done','已关联');
    setAgentStep('ResourceAgents','running','生成中');progress.value=52;
    const existingResources=resourceList(resources.value).length?resourceList(resources.value):resourceList(integrated.value?.resources);
    const plannedStages=parseStages(pr.data?.path_content||'');
    const plannedStageCount=plannedStages.length||baseStages.value.length||0;
    const canReuseExistingResources=!forceResources&&hasCompleteStageResources(existingResources,plannedStageCount);
    if(canReuseExistingResources){
      resources.value=existingResources;
      console.info('PathView resource generation skipped because existing resources already cover all stages', {count: existingResources.length, plannedStageCount});
    }else{
      console.info('PathView resource generation request start', {sessionId, needLength: need.length, plannedStageCount, existingResourceCount: existingResources.length});
      const rr=await resourceApi.generate({learning_need:need,path_content:pr.data?.path_content||''},sessionId);
      console.info('PathView resource generation response', rr);
      const generatedResources=resourceList(rr?.data);
      if(rr.code!==200&&!generatedResources.length){const detail=rr?.data?.error?`：${rr.data.error}`:'';throw new Error((rr.msg||'学习资源生成失败')+detail)}
      if(generatedResources.length)resources.value=generatedResources;
    }
    setAgentStep('ResourceAgents','done','已完成');
    setAgentStep('AuditAgent','running','审核中');progress.value=78;
    await new Promise(resolve=>setTimeout(resolve,450));
    setAgentStep('AuditAgent','done','已通过');
    setAgentStep('PackagerAgent','running','挂载中');progress.value=90;
    await loadAll(sessionId);
    setAgentStep('PackagerAgent','done','已刷新');progress.value=100;
    ElMessage.success('路径与资源一体化方案生成成功')
  }catch(e){
    console.warn('Path/resource generation warning', e);
    const hasVisibleResult=resources.value.length>0||stages.value.length>0;
    if(hasVisibleResult){
      agentSteps.value=agentSteps.value.map(item=>item.status==='running'?{...item,status:'done',statusText:'已完成'}:item);
      progress.value=Math.max(progress.value,100);
      ElMessage.warning('资源已生成并显示，部分刷新步骤返回了警告，可继续学习');
    }else{
      agentSteps.value=agentSteps.value.map(item=>item.status==='running'?{...item,status:'error',statusText:'失败'}:item);
      ElMessage.error(e?.message||'一体化生成失败');
    }
  }
  finally{clearInterval(timer);setTimeout(()=>{loading.value=false},650)}
}
function pace(c){hint.value=({fast:'学习节奏加快，资源更精炼。',slow:'学习节奏放慢，增加概念解释和基础练习。',practice:'增加练习题、代码案例和应用任务比例。'}[c]||'');generateAll(hint.value,true)}
async function fb(t){
  const config={
    easy:{adjustment:'学生反馈太简单，请提高后续应用和实操难度。',feedback_type:'too_easy',message:'已记录“太简单”反馈，正在提高后续阶段挑战度。'},
    hard:{adjustment:'学生反馈太难，请降低难度并增加基础讲解。',feedback_type:'too_hard',message:'已记录“太难”反馈，正在补强基础讲解与过渡资源。'},
    quiz:{adjustment:'结合练习结果调整后续路径，强化错题知识点。',feedback_type:'quiz_adjust',message:'已记录练习结果反馈，正在根据掌握情况重排后续学习方案。'}
  }[t]||{adjustment:'',feedback_type:'general_feedback',message:'已收到反馈，正在调整后续学习方案…'};
  hint.value=config.adjustment;
  try{
    const stage=activeStage.value;
    const sessionId=currentSessionId();
    if(stage&&sessionId){
      await pathApi.submitFeedback({
        stage_index:activeStageIndex.value+1,
        stage_title:stage.title,
        feedback_type:config.feedback_type,
        feedback_text:config.adjustment,
        knowledge_points:Array.isArray(stage.points)?stage.points:[]
      },sessionId);
    }
    window.dispatchEvent(new CustomEvent('a3-profile-session-refresh'));
    ElMessage.success(config.message);
  }catch(e){
    ElMessage.warning(e?.message||'反馈记录成功，但动态调整写入失败，将继续按当前结果重排路径。');
  }
  generateAll(hint.value,true);
}
async function triggerAutoGenerate(){
  if(autoGenerating.value||loading.value)return;
  autoGenerating.value=true;
  try{
    await loadAll(currentSessionId());
    await generateAll();
  }finally{
    autoGenerating.value=false;
  }
}
function hasExistingLearningPath(){
  if(Array.isArray(integrated.value?.stages) && integrated.value.stages.length>0) return true;
  if(Array.isArray(paths.value) && paths.value.length>0) return true;
  return false;
}
onMounted(async()=>{
  await loadAll(currentSessionId());
  renderMarkmaps();
  if(!hasExistingLearningPath()){
    await triggerAutoGenerate();
  }
  window.addEventListener('resize',refitAllMarkmaps);
  document.addEventListener('visibilitychange',handleLearningVisibility);
  syncLearningDurationTracker();
  usageHeartbeat=setInterval(()=>void flushLearningDuration(),60000);
});
onBeforeUnmount(()=>{void flushLearningDuration();if(usageHeartbeat)clearInterval(usageHeartbeat);document.removeEventListener('visibilitychange',handleLearningVisibility);stopMindmapDrag();window.removeEventListener('resize',refitAllMarkmaps);});
watch(()=>route.query.sessionId,async()=>{await flushLearningDuration();trackedResource=null;trackedSince=0;await loadAll(currentSessionId());renderMarkmaps();syncLearningDurationTracker()});
watch(stages,()=>{if(activeStageIndex.value>=stages.value.length)activeStageIndex.value=Math.max(stages.value.length-1,0);ensureActiveResourceTabs();nextTick(()=>renderMarkmaps())},{deep:true,flush:'post'});
watch(activeResourceTabs,()=>{syncLearningDurationTracker();nextTick(()=>renderMarkmaps())},{deep:true});
watch(activeStageIndex,()=>syncLearningDurationTracker());
watch(current,(value)=>{if(!done(activeStageIndex.value)&&activeStageIndex.value<value)activeStageIndex.value=value});
</script>

<style scoped>
.res-static-toggle{cursor:default}.res-static-toggle:hover{transform:none;box-shadow:0 10px 24px rgba(15,23,42,.045)}
.path-page{display:grid;gap:22px;background:#f7f9fc}.overview-card{overflow:hidden;border:1px solid #dbeafe;background:linear-gradient(135deg,#ffffff 0%,#f8fbff 62%,#eef6ff 100%);box-shadow:0 18px 48px rgba(15,23,42,.06)}.overview-grid{display:grid;grid-template-columns:minmax(0,1fr) 420px;gap:24px;align-items:start}.overview-main h2{margin:14px 0 8px;font-size:30px;color:#0f172a;letter-spacing:-.02em}.overview-main p{max-width:760px;color:#475569;line-height:1.85}.profile-tags{display:flex;flex-wrap:wrap;gap:10px;margin-top:14px;align-items:flex-start}.profile-tags :deep(.el-tag){max-width:100%;height:auto;min-height:32px;padding:7px 11px;white-space:normal;word-break:break-word;line-height:1.55}.overview-side{display:grid;gap:14px}.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}.stats div{min-height:102px;padding:18px;border:1px solid #dbeafe;border-radius:22px;background:rgba(255,255,255,.88);box-shadow:0 12px 28px rgba(37,99,235,.06)}.stats b{display:block;font-size:25px;color:#0f172a}.stats span{display:block;margin-top:6px;color:#64748b}.overview-actions{display:flex;justify-content:flex-end;gap:12px}.overview-progress{display:grid;grid-template-columns:minmax(0,1fr) 90px;gap:14px;align-items:center;margin-top:20px}.overview-progress span{color:#64748b;text-align:right;font-size:13px}.line,.stage-head,.res-head,.feedback{display:flex;align-items:center;justify-content:space-between;gap:14px}.run-grid{display:grid;grid-template-columns:minmax(0,1fr) 320px;gap:16px;margin-top:18px}.agent-flow{display:grid;gap:10px}.run-step{display:grid;grid-template-columns:42px minmax(0,1fr) 64px;align-items:center;gap:12px;padding:12px;border:1px solid #e2e8f0;border-radius:16px;background:#fff;color:#64748b;transition:.2s ease}.run-step b{display:grid;width:34px;height:34px;place-items:center;border-radius:12px;background:#e2e8f0;color:#475569}.run-step strong,.run-step span{display:block}.run-step span{font-size:12px}.run-step em{font-style:normal;font-size:12px;text-align:right}.run-step.running{border-color:#60a5fa;background:#eff6ff;color:#1d4ed8;box-shadow:0 10px 28px rgba(37,99,235,.12)}.run-step.running b{background:linear-gradient(135deg,#2563eb,#06b6d4);color:#fff}.run-step.done{border-color:#86efac;background:#f0fdf4;color:#15803d}.run-step.done b{background:#22c55e;color:#fff}.run-step.error{border-color:#fecaca;background:#fef2f2;color:#dc2626}.run-step.error b{background:#ef4444;color:#fff}.live-preview{padding:16px;border:1px solid #dbeafe;border-radius:18px;background:linear-gradient(135deg,#f8fbff,#fff)}.live-preview b{display:block;color:#0f172a}.live-preview p{color:#1d4ed8;line-height:1.7}.live-preview small{color:#64748b;line-height:1.6}.timeline{position:relative;display:grid;gap:20px;margin-left:26px}.timeline:before{position:absolute;top:12px;bottom:12px;left:17px;width:3px;border-radius:999px;background:#dbeafe;content:""}.stage{position:relative;display:grid;grid-template-columns:56px 1fr;gap:16px}.dot{z-index:1;display:flex;justify-content:center;padding-top:18px}.dot span{display:grid;width:38px;height:38px;place-items:center;border-radius:999px;background:#cbd5e1;color:#fff;font-weight:800}.stage.current .dot span{background:#2563eb;box-shadow:0 0 0 8px #dbeafe}.stage.completed .dot span{background:#16a34a}.stage-card{border-radius:22px}.stage.current .stage-card{border-color:#93c5fd;box-shadow:0 16px 36px rgba(37,99,235,.12)}.stage-title-block{min-width:0;flex:1}.stage-head-actions{display:flex;align-items:center;gap:8px;flex-shrink:0}.stage-head h3{margin:10px 0 6px;color:#0f172a}.stage-head p{margin:0;color:#64748b}.stage-brief{display:grid;grid-template-columns:minmax(260px,1.1fr) minmax(240px,.9fr);gap:12px;margin-top:14px}.stage-brief-goal,.stage-brief-points{padding:14px 16px;border:1px solid #dbeafe;border-radius:16px;background:linear-gradient(135deg,#f8fbff,#ffffff)}.stage-brief b{display:block;margin-bottom:7px;color:#1d4ed8;font-size:13px}.stage-brief span{color:#334155;line-height:1.75}.stage-brief-points div{display:flex;flex-wrap:wrap;gap:7px}.body{display:grid;gap:16px}.goal{padding:16px;border:1px solid #dbeafe;border-radius:16px;background:#f8fbff}.stage-eval{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:14px 16px;border:1px solid #bbf7d0;border-radius:16px;background:linear-gradient(135deg,#f0fdf4,#fff)}.stage-eval.stage-eval-standalone{margin-top:4px;border-color:#bfdbfe;background:linear-gradient(135deg,#eff6ff,#ffffff)}.stage-eval.stage-eval-standalone b{color:#1d4ed8}.stage-eval b{color:#15803d}.stage-eval p{margin:6px 0;color:#334155}.stage-eval span{color:#64748b;font-size:12px}.goal b,.section b,.feedback b{color:#1d4ed8}.goal p,.feedback p{margin:8px 0 0;color:#334155;line-height:1.8}.tags{display:flex;flex-wrap:wrap;gap:8px;align-items:center;color:#64748b}.section{display:flex;justify-content:space-between;color:#64748b}.res-list{display:grid;gap:16px}.res{position:relative;display:grid;gap:10px;padding:14px 14px 14px 16px;border:1px solid #dbeafe;border-left:5px solid #3b82f6;border-radius:18px;background:linear-gradient(135deg,#fff,#f8fbff);box-shadow:0 10px 24px rgba(15,23,42,.045);cursor:pointer;transition:.18s ease}.res:hover{transform:translateY(-2px);box-shadow:0 18px 36px rgba(15,23,42,.08)}.res-doc{border-left-color:#3b82f6}.res-mindmap{border-left-color:#8b5cf6}.res-quiz{border-left-color:#22c55e;background:linear-gradient(135deg,#f0fdf4,#ffffff)}.res-code{border-left-color:#f97316}.res-video{border-left-color:#ef4444}.res-reading{border-left-color:#64748b}.res-icon{display:grid;width:30px;height:30px;place-items:center;border-radius:10px;background:#f1f5f9;font-size:16px}.res-head{justify-content:space-between;flex-wrap:wrap;margin-bottom:2px}.res-title{display:flex;align-items:center;gap:10px;flex-wrap:wrap;min-width:0}.res-title strong{min-width:0;overflow:visible;white-space:normal;color:#0f172a;font-size:16px;line-height:1.5}.res-content,.json-doc{padding:16px;border:1px solid #e2e8f0;border-radius:18px;background:#fff;color:#334155;line-height:1.9;font-size:14px;white-space:normal;word-break:break-word}.res-content{white-space:pre-wrap}.res-content.collapsed,.json-doc.collapsed{display:-webkit-box;height:380px;max-height:380px;overflow:hidden;-webkit-line-clamp:13;-webkit-box-orient:vertical;color:#475569}.doc-reading-content,.reading-content{min-height:220px;padding:18px 20px;border:1px solid #e2e8f0;border-radius:16px;background:linear-gradient(135deg,#ffffff,#f8fafc);color:#334155;line-height:1.85;font-size:14px;overflow:hidden}.doc-reading-content.collapsed{display:-webkit-box;height:380px;max-height:380px;-webkit-line-clamp:13;-webkit-box-orient:vertical}.reading-content.collapsed{display:-webkit-box;max-height:300px;-webkit-line-clamp:10;-webkit-box-orient:vertical}.doc-reading-content :deep(h1),.reading-content :deep(h1){margin:0 0 16px;color:#0f172a;font-size:22px;line-height:1.4}.doc-reading-content :deep(h2),.reading-content :deep(h2){margin:22px 0 10px;padding-left:10px;border-left:4px solid #3b82f6;color:#1d4ed8;font-size:17px}.doc-reading-content :deep(h3),.reading-content :deep(h3){margin:16px 0 8px;color:#0f172a;font-size:15px}.doc-reading-content :deep(p),.reading-content :deep(p){margin:8px 0;color:#334155}.doc-reading-content :deep(ul),.doc-reading-content :deep(ol),.reading-content :deep(ul){margin:8px 0 8px 18px;padding:0}.doc-reading-content :deep(li),.reading-content :deep(li){margin:5px 0}.doc-reading-content :deep(strong),.reading-content :deep(strong){color:#0f172a}.doc-reading-content :deep(blockquote){margin:0 0 16px;padding:10px 14px;border-left:4px solid #93c5fd;border-radius:10px;background:#eff6ff;color:#475569}.json-summary{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:14px;white-space:normal}.json-summary div{padding:14px;border-radius:16px;background:linear-gradient(135deg,#f8fbff,#fff);border:1px solid #dbeafe}.json-summary span{display:block;color:#64748b;font-size:12px}.json-summary b{display:block;margin-top:4px;color:#0f172a;line-height:1.5}.doc-hero{padding:18px;border:1px solid #bfdbfe;border-radius:18px;background:linear-gradient(135deg,#eff6ff,#ffffff)}.doc-hero h3{margin:0 0 8px;color:#1d4ed8}.doc-hero p{margin:0;line-height:1.9}.json-block{margin-top:16px;padding-top:16px;border-top:1px dashed #dbeafe;white-space:normal}.json-block h4{margin:0 0 12px;color:#1d4ed8;font-size:16px}.json-block p{margin:7px 0;line-height:1.9}.concept-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}.concept-card,.explain-card,.mistake-list>div,.check-list>div{padding:14px;border:1px solid #e2e8f0;border-radius:16px;background:#f8fafc}.concept-card b,.mistake-list b,.check-list b{display:block;color:#0f172a}.concept-card small,.concept-card em,.mistake-list small{display:block;margin-top:6px;color:#64748b;font-style:normal;line-height:1.7}.explain-card{margin-top:10px;background:#fff}.explain-card h5{margin:0 0 8px;color:#0f172a;font-size:15px}.step-list{display:flex;flex-wrap:wrap;gap:8px;margin:10px 0}.step-list span{padding:7px 10px;border-radius:999px;background:#eef6ff;color:#1d4ed8;font-size:12px}.io-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin:10px 0}.io-grid div{padding:10px 12px;border-radius:14px;background:#f8fafc;border:1px solid #e2e8f0}.io-grid span{display:block;color:#64748b;font-size:12px}.io-grid b{display:block;margin-top:4px;color:#0f172a;line-height:1.6}.lifecycle-box,.case-box,.summary-box{padding:14px 16px;border:1px solid #bfdbfe;border-radius:16px;background:linear-gradient(135deg,#f8fbff,#fff)}.mistake-list,.check-list{display:grid;gap:10px}.summary-box ul{margin:8px 0 0 18px;padding:0}.kb-item{padding:10px 12px;margin-top:8px;border-radius:14px;background:#f8fbff}.kb-item b,.kb-item em{display:block}.kb-item em{margin-top:4px;color:#64748b;font-style:normal;font-size:12px}.markmap-panel{height:430px;padding:8px;border:1px solid #e9d5ff;border-radius:16px;background:linear-gradient(135deg,#fbf7ff,#ffffff);overflow:hidden}.markmap-viewport{width:100%;height:100%;overflow:auto;cursor:grab;border-radius:12px;background:#fafbfc}.markmap-viewport.dragging{cursor:grabbing}.markmap-viewport *{user-select:none}.markmap-zoom-layer{display:inline-block;min-width:max-content;min-height:max-content;transform-origin:top left;transition:transform .12s ease-out}.markmap-container{display:block;width:max-content;min-width:100%;height:max-content;min-height:100%;border-radius:12px;background:#fafbfc;font-family:Inter,Microsoft YaHei,sans-serif;pointer-events:none}.markmap-container :deep(.markmap-node){cursor:default}.markmap-container :deep(.markmap-node text){font-size:13px;fill:#0f172a}.markmap-container :deep(.markmap-link){stroke-width:1.8px}.video-resource-panel{height:460px;padding:14px;border:1px solid #fecaca;border-radius:18px;background:linear-gradient(135deg,#fff7f7,#ffffff);overflow:hidden}.video-player{display:block;width:100%;height:100%;object-fit:contain;border-radius:14px;background:#0f172a;box-shadow:0 14px 34px rgba(15,23,42,.12)}.video-placeholder{display:grid;place-items:center;height:100%;padding:24px;border:1px dashed #fecaca;border-radius:14px;background:#fff;color:#64748b;text-align:center}.video-placeholder b{color:#0f172a;font-size:16px}.video-placeholder p{max-width:520px;margin:8px 0 0;line-height:1.7}.image-gallery{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;padding:12px;border:1px dashed #bfdbfe;border-radius:18px;background:#f8fbff}.kb-image{padding:10px;border:1px solid #dbeafe;border-radius:16px;background:#fff;box-shadow:0 8px 18px rgba(15,23,42,.04)}.kb-image img{display:block;width:100%;height:190px;object-fit:contain;border-radius:12px;background:#fff}.kb-image p{margin:8px 0 0;color:#64748b;font-size:12px;line-height:1.5;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.res-meta{display:flex;flex-wrap:wrap;gap:8px;color:#64748b;font-size:12px}.res-meta span{padding:5px 9px;border-radius:999px;background:#f1f5f9}.res-actions{display:flex;justify-content:flex-end;align-items:center;gap:4px;padding-top:2px}.res-actions :deep(.el-button){padding:4px 6px;color:#64748b;font-size:13px}.res-actions :deep(.el-button:hover){color:#2563eb;background:transparent}.detail-dialog-body{display:grid;gap:14px;color:#334155;line-height:1.8}.detail-dialog-body h3{margin:0;color:#0f172a;font-size:18px}.detail-dialog-body p{margin:0;padding:12px 14px;border-radius:14px;background:#f8fafc}.detail-kv{display:flex;justify-content:space-between;gap:16px;padding:10px 12px;border:1px solid #e2e8f0;border-radius:12px;background:#fff}.detail-kv span{color:#64748b}.detail-kv b{color:#0f172a;text-align:right}.stage-workspace{display:grid;gap:14px}.route-panel{position:relative;padding:24px;border:1px solid #e5edf7;border-radius:28px;background:#fff;box-shadow:0 14px 34px rgba(15,23,42,.05);overflow:hidden}.route-head{display:flex;justify-content:space-between;gap:18px;align-items:flex-start;margin-bottom:18px}.route-head h3{margin:10px 0 6px;color:#0f172a;font-size:24px;letter-spacing:-.02em}.route-head p{margin:0;color:#64748b;line-height:1.75}.route-progress{display:grid;place-items:center;min-width:92px;height:76px;border:1px solid #e6edf5;border-radius:22px;background:#f8fbff;box-shadow:none}.route-progress b{color:#1d4ed8;font-size:24px}.route-progress span{color:#64748b;font-size:12px}.route-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}.route-card{position:relative;display:grid;grid-template-columns:42px minmax(0,1fr);gap:14px;min-height:220px;padding:20px;border:1px solid #e4edf6;border-radius:22px;background:#fcfdff;text-align:left;cursor:pointer;transition:.2s ease;box-shadow:0 8px 20px rgba(15,23,42,.035)}.route-card:hover{transform:translateY(-2px);border-color:#93c5fd;box-shadow:0 14px 28px rgba(37,99,235,.08)}.route-card.active{border-color:#60a5fa;background:#f7fbff;box-shadow:0 16px 30px rgba(37,99,235,.1)}.route-card.completed{border-color:#bbf7d0;background:#f8fdf9}.route-card.locked{opacity:.58}.route-index{display:grid;width:38px;height:38px;place-items:center;border-radius:16px;background:linear-gradient(135deg,#2563eb,#06b6d4);color:#fff;font-weight:900;box-shadow:0 10px 20px rgba(37,99,235,.2)}.route-card.completed .route-index{background:#16a34a}.route-content{display:flex;min-width:0;flex-direction:column}.route-title{display:flex;justify-content:space-between;gap:10px;align-items:center}.route-title b{color:#1d4ed8;font-size:13px}.route-title em{font-style:normal;color:#64748b;font-size:12px}.route-content h4{margin:8px 0 8px;color:#0f172a;font-size:17px;line-height:1.4}.route-content p{margin:0 0 12px;color:#475569;line-height:1.75;white-space:normal;word-break:break-word}.route-tags{display:flex;flex-wrap:wrap;gap:7px;align-items:center;margin-top:auto}.route-tags span{padding:4px 9px;border:1px solid #e2e8f0;border-radius:999px;background:#f8fafc;color:#64748b;font-size:12px}.route-progress-bar{margin-top:16px}.compact-timeline{margin-left:0}.compact-timeline:before{display:none}.compact-timeline .stage{grid-template-columns:minmax(0,1fr)}.resource-tabs{padding:6px 8px 12px;border:1px solid #dbeafe;border-radius:16px;background:#ffffff}.resource-tabs :deep(.el-tabs__header){margin-bottom:10px}.resource-tabs :deep(.el-tabs__content){overflow:visible}.resource-tab-label{display:inline-flex;align-items:center;gap:6px}.stage-nav-actions{display:flex;justify-content:space-between;gap:12px;padding:16px;border:1px solid #dbeafe;border-radius:18px;background:linear-gradient(135deg,#f8fbff,#ffffff)}.stage-nav-actions .el-button{min-width:120px}.feedback-card b{display:block;margin-top:10px;color:#0f172a;font-size:18px}.feedback p{max-width:760px}.feedback>div:last-child{display:flex;gap:10px;flex-wrap:wrap}@media(max-width:1200px){.overview-grid{grid-template-columns:1fr}.run-grid,.stage-brief,.json-summary,.concept-grid,.io-grid,.image-gallery,.prestudy-grid,.stage-switcher{grid-template-columns:1fr}}.prestudy-plan{position:relative;padding:26px;border:1px solid #e5edf7;border-radius:28px;background:#fff;box-shadow:0 16px 38px rgba(15,23,42,.05);overflow:hidden}.prestudy-head{display:flex;justify-content:space-between;gap:20px;align-items:flex-start;margin-bottom:20px}.prestudy-head h3{margin:10px 0 7px;color:#0f172a;font-size:26px;letter-spacing:-.02em}.prestudy-head p{max-width:720px;margin:0;color:#64748b;line-height:1.75}.prestudy-head .el-button{border-radius:999px;padding:10px 18px}.prestudy-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}.prestudy-card{position:relative;display:grid;grid-template-columns:1fr;min-height:210px;padding:22px 20px 18px 78px;border:1px solid #e4edf6;border-radius:24px;background:#fcfdff;box-shadow:0 10px 24px rgba(15,23,42,.035);cursor:pointer;transition:.2s ease;overflow:hidden}.prestudy-card:before{position:absolute;inset:0 auto 0 0;width:3px;background:linear-gradient(180deg,#3b82f6,#22c55e);content:"";opacity:.28}.prestudy-card:hover{transform:translateY(-2px);border-color:#93c5fd;box-shadow:0 14px 28px rgba(37,99,235,.08)}.prestudy-card.current{border-color:#60a5fa;background:#f7fbff;box-shadow:0 16px 32px rgba(37,99,235,.1)}.prestudy-card.completed{border-color:#bbf7d0;background:#f8fdf9}.prestudy-index{position:absolute;left:22px;top:50%;transform:translateY(-50%);display:grid;place-items:center;gap:7px}.prestudy-index span{display:grid;place-items:center;width:40px;height:40px;border-radius:16px;background:linear-gradient(135deg,#2563eb,#06b6d4);color:#fff;font-weight:900;box-shadow:0 12px 24px rgba(37,99,235,.22)}.prestudy-index em{font-style:normal;color:#64748b;font-size:12px}.prestudy-body{display:flex;min-width:0;flex-direction:column}.prestudy-body h4{margin:0 0 10px;color:#0f172a;font-size:18px;line-height:1.35}.prestudy-body p{flex:1;margin:0 0 14px;color:#475569;line-height:1.72}.prestudy-points{display:flex;flex-wrap:wrap;gap:7px;margin-bottom:12px}.prestudy-points :deep(.el-tag){border-radius:999px}.prestudy-meta{display:flex;flex-wrap:wrap;gap:8px;color:#64748b;font-size:12px}.prestudy-meta span{padding:5px 10px;border-radius:999px;background:#f1f5f9;border:1px solid #e2e8f0}
.markmap-viewport{position:relative;overflow:hidden;touch-action:none}.markmap-zoom-layer{display:block!important;width:100%;height:100%;will-change:transform}.markmap-container{width:100%!important;height:100%!important}.markmap-viewport .markmap{width:100%;height:100%}
.markmap-container{pointer-events:auto!important}.markmap-container :deep(.markmap-node){cursor:pointer!important}
@media(max-width:800px){.agents,.stats{grid-template-columns:1fr}.stage{grid-template-columns:42px 1fr}.stage-head,.feedback,.prestudy-head{flex-direction:column;align-items:flex-start}.prestudy-card{grid-template-columns:1fr}}.adaptive-focus-bar{display:flex;align-items:flex-start;gap:10px;margin-top:14px;padding:10px 12px;border:1px solid #fde7b0;border-radius:14px;background:#fffaf0;color:#7c5a10;line-height:1.65;font-size:13px}
.adaptive-panel .el-card__body{display:grid;gap:12px}.adaptive-ranking-list{display:grid;gap:12px}.adaptive-ranking-item{padding:14px 16px;border:1px solid #eceff5;border-radius:16px;background:#fff}.adaptive-ranking-title{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:6px}.adaptive-ranking-item p{margin:0;color:#475569;line-height:1.7}
.adaptive-explanation{margin-top:10px;color:#526072;line-height:1.75;font-size:14px;max-width:860px}
.evidence-source-list{display:grid;gap:10px}.evidence-source-card{display:grid;grid-template-columns:30px minmax(0,1fr) auto;align-items:center;gap:12px;width:100%;padding:13px 14px;border:1px solid #dbeafe;border-radius:14px;background:#f8fbff;color:#334155;text-align:left;cursor:pointer;transition:.18s ease}.evidence-source-card:hover{border-color:#60a5fa;background:#eff6ff;transform:translateY(-1px)}.evidence-index{display:grid;width:28px;height:28px;place-items:center;border-radius:9px;background:#dbeafe;color:#1d4ed8;font-size:12px;font-weight:800}.evidence-main{display:grid;min-width:0;gap:4px}.evidence-main strong{overflow:hidden;color:#0f172a;text-overflow:ellipsis;white-space:nowrap}.evidence-main small{overflow:hidden;color:#64748b;font-size:12px;text-overflow:ellipsis;white-space:nowrap}.evidence-main em{display:-webkit-box;overflow:hidden;color:#64748b;font-size:12px;font-style:normal;line-height:1.5;-webkit-box-orient:vertical;-webkit-line-clamp:2}.evidence-meta{display:grid;justify-items:end;gap:3px;color:#64748b;font-size:11px;white-space:nowrap}.evidence-meta b{color:#2563eb;font-size:12px}@media(max-width:720px){.evidence-source-card{grid-template-columns:30px minmax(0,1fr)}.evidence-meta{grid-column:2;justify-items:start}}
.stage-map-nav{position:sticky;z-index:8;top:10px;display:grid;grid-template-columns:190px minmax(0,1fr);gap:9px 15px;padding:13px 16px;border:1px solid rgba(191,219,254,.92);border-radius:18px;background:rgba(255,255,255,.95);box-shadow:0 12px 28px rgba(15,23,42,.08);backdrop-filter:blur(12px)}.stage-map-status{display:grid}.stage-map-status span{color:#2563eb;font-size:12px;font-weight:800}.stage-map-status b{margin-top:3px;color:#0f172a;font-size:14px}.stage-map-items{display:flex;gap:7px;overflow-x:auto}.stage-map-items button{display:flex;min-width:0;align-items:center;gap:7px;padding:7px 10px;border:1px solid #e2e8f0;border-radius:12px;background:#fff;color:#64748b;cursor:pointer}.stage-map-items button span{display:grid;flex:0 0 24px;height:24px;place-items:center;border-radius:8px;background:#e2e8f0;font-size:11px}.stage-map-items button b{max-width:150px;overflow:hidden;font-size:12px;text-overflow:ellipsis;white-space:nowrap}.stage-map-items button.active{border-color:#60a5fa;background:#eff6ff;color:#1d4ed8}.stage-map-items button.completed span{background:#22c55e;color:#fff}.stage-map-nav>.el-progress{grid-column:1/-1}.stage-guide-panel{padding:17px;border:1px solid #bfdbfe;border-radius:18px;background:linear-gradient(135deg,#f8fbff,#fff)}.stage-guide-title{display:flex;align-items:center;gap:12px;margin-bottom:13px}.stage-guide-title span{padding:5px 9px;border-radius:999px;background:#dbeafe;color:#1d4ed8;font-size:12px;font-weight:800}.stage-guide-title b{color:#0f172a}.stage-guide-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}.stage-guide-grid>div{padding:13px 14px;border:1px solid #e2e8f0;border-radius:14px;background:#fff}.stage-guide-grid small{display:block;color:#2563eb;font-weight:700}.stage-guide-grid strong{display:block;margin:7px 0;color:#0f172a;line-height:1.55}.stage-guide-grid p{margin:0;color:#64748b;font-size:12px;line-height:1.65}@media(max-width:1050px){.stage-map-nav,.stage-guide-grid{grid-template-columns:1fr}}@media(max-width:720px){.stage-map-nav{top:4px}.stage-map-items button b{max-width:96px}}
.stage-jar-row{display:grid;grid-template-columns:minmax(210px,.42fr) minmax(0,1fr);gap:16px;align-items:center;margin-top:12px;padding:13px 14px;border:1px solid #d8eee9;border-radius:15px;background:#f7fcfb}.stage-jar-row>div:first-child{display:grid;gap:4px}.stage-jar-row b{color:#167f70;font-size:13px}.stage-jar-row>div:first-child span{color:#718892;font-size:11px}.stage-jar-points{display:flex;flex-wrap:wrap;gap:7px}.stage-jar-points button{display:inline-flex;align-items:center;gap:5px;padding:6px 10px;border:1px solid #dce8e6;border-radius:999px;background:#fff;color:#526b75;font-size:11px;cursor:pointer;transition:.16s}.stage-jar-points button span{color:#19917e;font-weight:900}.stage-jar-points button:hover,.stage-jar-points button.collected{border-color:#74c9ba;background:#eaf8f5;color:#147568}.stage-jar-points button:disabled{cursor:wait;opacity:.55}@media(max-width:820px){.stage-jar-row{grid-template-columns:1fr}}
.stage-guide-summary{display:grid;grid-template-columns:minmax(180px,.35fr) 1px minmax(0,1fr);gap:16px;align-items:center;padding:13px 15px;border:1px solid #e2e8f0;border-radius:14px;background:#fff}.stage-guide-summary div{display:grid;gap:5px;min-width:0}.stage-guide-summary small{color:#64748b;font-size:11px}.stage-guide-summary strong{color:#172033;font-size:13px;line-height:1.6}.stage-guide-summary i{width:1px;height:34px;background:#e2e8f0}@media(max-width:720px){.stage-guide-summary{grid-template-columns:1fr}.stage-guide-summary i{display:none}}
.path-page{width:100%;min-height:100%;padding:24px 16px 28px;gap:26px;box-sizing:border-box;background:linear-gradient(180deg,#f4f7fb 0%,#f7f9fc 100%);overflow-x:hidden}
.plan-hero-card{display:grid;gap:22px;width:100%;box-sizing:border-box;padding:0 0 2px;overflow:visible;background:transparent;border:0;border-radius:0;box-shadow:none}
.plan-title-row{display:flex;align-items:flex-start;justify-content:space-between;gap:28px;padding:0 22px;box-sizing:border-box}
.plan-overview-card{display:grid;grid-template-columns:minmax(0,1fr) 380px;align-items:start;gap:28px;padding:18px 22px 20px;border:1px solid #e7ecf3;border-radius:20px;background:#fff;box-shadow:0 1px 2px rgba(20,34,55,.02),0 8px 28px rgba(31,47,70,.035);box-sizing:border-box}
.plan-overview-main{min-width:0}
.plan-hero-main{min-width:0;display:flex;flex-direction:column;align-items:flex-start;gap:6px}
.page-eyebrow{display:block;margin-top:6px;margin-bottom:0;color:#4386d8;font-size:12px;font-weight:800;letter-spacing:.1em;text-transform:uppercase}
.plan-hero-title{max-width:100%;margin:0;overflow-wrap:anywhere}
.overview-main .plan-hero-title{margin:0;font-size:38px;line-height:1.25;letter-spacing:-.04em}
.overview-main .plan-hero-description{max-width:50em;margin:0;color:#475569;font-size:16px;line-height:1.9}
.plan-status-tags{width:100%;display:flex;align-items:center;flex-wrap:wrap;gap:8px}
.plan-status-tag{height:auto;white-space:normal;overflow-wrap:anywhere}
.plan-feedback-panel{width:100%;box-sizing:border-box}
.plan-feedback-label{flex:0 0 auto}
.plan-feedback-content{min-width:0;flex:1;overflow-wrap:anywhere}
.plan-resource-note{max-width:100%;overflow-wrap:anywhere}
.plan-hero-side{min-width:0;display:flex;flex-direction:column;align-items:stretch}
.plan-hero-actions{min-height:36px;display:flex;align-items:center;justify-content:flex-end;gap:10px;margin-top:12px}
.plan-metrics-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:9px}
.plan-metric-card{min-width:0;min-height:82px;padding:13px 14px;box-sizing:border-box;display:flex;flex-direction:column;justify-content:center;border:1px solid #e1e8f1;border-radius:15px;background:linear-gradient(180deg,#f9fbfd 0%,#f5f8fc 100%)}
.plan-metric-value{white-space:nowrap}
.plan-metric-label{margin-top:7px;white-space:nowrap}
@media(max-width:1100px){.plan-overview-card{grid-template-columns:minmax(0,1fr) 330px;gap:20px}.plan-metric-card{padding-left:10px;padding-right:10px}}
@media(max-width:900px){.plan-overview-card{grid-template-columns:1fr}.plan-hero-side{width:100%}.plan-hero-actions{justify-content:flex-start}.plan-metrics-grid{grid-template-columns:repeat(3,minmax(0,1fr))}}
@media(max-width:600px){.plan-overview-card{padding:16px;border-radius:16px}.plan-hero-actions{display:grid;grid-template-columns:repeat(2,minmax(0,1fr))}.plan-hero-actions :deep(.el-button){width:100%}.plan-metrics-grid{grid-template-columns:1fr}.plan-feedback-panel{align-items:flex-start;flex-direction:column;gap:7px}}
</style>


