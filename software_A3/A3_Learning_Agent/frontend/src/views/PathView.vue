<template>
  <div class="page path-page">
    <el-card class="panel top overview-card">
      <div class="overview-grid">
        <div class="overview-main">
          <el-tag effect="dark">路径带资源 · 资源随路径走</el-tag>
          <h2>{{ title }}・个性化学习方案</h2>
          <p>以学习路径为主线，将讲解文档、题库、思维导图、代码案例和教学视频挂载到每个阶段，形成可评估、可反馈、可调整的学习闭环。</p>
          <div class="profile-tags">
            <el-tooltip :content="basis" placement="bottom-start"><el-tag type="primary" effect="light">知识基础：{{profile.knowledge_base||profile.knowledge_level||'待观察'}}</el-tag></el-tooltip>
            <el-tooltip :content="basis" placement="bottom-start"><el-tag type="danger" effect="light">薄弱点：{{profile.error_prone_points||profile.weak_points||'待观察'}}</el-tag></el-tooltip>
            <el-tooltip :content="basis" placement="bottom-start"><el-tag type="success" effect="light">学习目标：{{profile.study_goal||'待观察'}}</el-tag></el-tooltip>
          </div>
        </div>
        <div class="overview-side">
          <div class="stats"><div><b>{{ totalDays }}</b><span>预计时长</span></div><div><b>{{ stages.length }}</b><span>学习阶段</span></div><div><b>{{ resources.length }}</b><span>配套资源</span></div></div>
          <div class="overview-actions"><el-button text :loading="loading" @click="generateAll()">重新生成</el-button><el-dropdown @command="pace"><el-button plain>调整学习节奏</el-button><template #dropdown><el-dropdown-menu><el-dropdown-item command="fast">节奏加快</el-dropdown-item><el-dropdown-item command="slow">节奏放慢</el-dropdown-item><el-dropdown-item command="practice">增加实操练习</el-dropdown-item></el-dropdown-menu></template></el-dropdown></div>
        </div>
      </div>
      <div class="overview-progress"><el-progress :percentage="percent" :stroke-width="10" striped striped-flow /><span>{{percent}}% 已完成</span></div>
    </el-card>

    <el-card v-if="loading" class="panel run-panel"><template #header><div class="line"><span>多智能体协同生成中</span><el-tag type="primary">{{ progress }}%</el-tag></div></template><el-progress :percentage="progress" striped striped-flow /><div class="run-grid"><div class="agent-flow"><div v-for="step in agentSteps" :key="step.name" :class="['run-step',step.status]"><b>{{step.short}}</b><div><strong>{{step.name}}</strong><span>{{step.desc}}</span></div><em>{{step.statusText}}</em></div></div><div class="live-preview"><b>当前系统正在做什么</b><p>{{agentSteps.find(s=>s.status==='running')?.desc||'正在整理学习路径与资源结果。'}}</p><small>你可以先查看已生成内容，系统会在完成后自动刷新路径与资源。</small></div></div></el-card>

    <el-empty v-if="!loading&&!stages.length" class="panel" description="当前画像还没有路径学习方案。请先生成画像，再点击生成路径与资源。"><el-button type="primary" @click="generateAll()">立即生成路径与资源</el-button></el-empty>

    <div v-else class="timeline">
      <div v-for="(s,i) in stages" :key="s.key" :class="['stage',state(i)]">
        <div class="dot"><span>{{i+1}}</span></div>
        <el-card class="stage-card" shadow="never">
          <template #header><div class="stage-head"><div><el-tag :type="tag(i)" effect="dark">{{ label(i) }}</el-tag><h3>第{{i+1}}阶段：{{s.title}}</h3><p>{{s.duration}}</p></div><div><el-button size="small" plain @click="toggle(i)">{{done(i)?'取消完成':'标记完成'}}</el-button><el-button size="small" text @click="toggleStage(i)">{{i>current&&!done(i)?'锁定':(s.open?'收起':'展开')}}</el-button></div></div></template>
          <el-collapse-transition><div v-show="s.open" class="body"><div class="goal"><b>阶段目标</b><p>{{s.goal}}</p></div><div class="tags"><span>覆盖知识点</span><el-tag v-for="p in s.points" :key="p" size="small" type="info">{{p}}</el-tag></div><div class="section"><b>本阶段配套资源</b><span>保留个性化说明与质量审核报告</span></div><div v-if="s.resources.length" class="res-list">
                <div v-for="r in s.resources" :key="rid(r)" :class="['res',resourceClass(r)]" @click="toggleResource(r)">
                  <div class="res-head">
                    <div class="res-title">
                      <span class="res-icon">{{resourceIcon(r.resource_type)}}</span>
                      <el-tag size="small" effect="dark">{{typeName(r.resource_type)}}</el-tag>
                      <strong>{{r.title}}</strong>
                      <el-tag :type="qPass(r)?'success':'warning'" size="small" plain>{{qScore(r)}}分</el-tag>
                    </div>
                    <el-button size="small" text @click.stop="toggleResource(r)">{{resourceOpen(r)?'收起正文':'查看正文'}}</el-button>
                  </div>
                  <template v-if="isMindmap(r)">
                    <div class="markmap-panel" :class="{collapsed:!resourceOpen(r)}">
                      <svg :ref="el=>setMarkmapRef(r,el)" class="markmap-container"></svg>
                    </div>
                  </template>
                  <template v-else-if="isReading(r)">
                    <div class="reading-content" :class="{collapsed:!resourceOpen(r)}" v-html="renderReading(r)"></div>
                  </template>
                  <template v-else-if="resourceJson(r)">
                    <div class="json-doc" :class="{collapsed:!resourceOpen(r)}">
                      <div class="json-summary">
                        <div><span>知识基础</span><b>{{resourceJson(r).knowledgelevel||'待观察'}}</b></div>
                        <div><span>学习目标</span><b>{{resourceJson(r).studygoal||resourceJson(r).resourcetitle||r.title}}</b></div>
                        <div><span>预计时长</span><b>{{resourceJson(r).estimatedtime||resourceJson(r).studytimepreferred||'25分钟'}}</b></div>
                      </div>
                      <div v-if="resourceJson(r).overview" class="doc-hero"><h3>{{resourceJson(r).overview.title||'本阶段学习导入'}}</h3><p>{{resourceJson(r).overview.content}}</p></div>
                      <div v-if="resourceJson(r).core_concepts?.length" class="json-block"><h4>核心概念讲解</h4><div class="concept-grid"><div v-for="item in resourceJson(r).core_concepts" :key="item.name" class="concept-card"><b>{{item.name}}</b><p>{{item.definition}}</p><small>{{item.why_it_matters}}</small><em v-if="item.example">例：{{item.example}}</em><em v-if="item.common_misunderstanding">易错：{{item.common_misunderstanding}}</em></div></div></div>
                      <div v-if="resourceJson(r).knowledge_explanation?.length" class="json-block"><h4>知识点详细讲解</h4><div v-for="item in resourceJson(r).knowledge_explanation" :key="item.title" class="explain-card"><h5>{{item.title}}</h5><p>{{item.explanation}}</p><div v-if="item.process?.length" class="step-list"><span v-for="(step,idx) in item.process" :key="step">{{idx+1}}. {{step}}</span></div><div v-if="item.input_output" class="io-grid"><div><span>输入</span><b>{{item.input_output.input}}</b></div><div><span>输出</span><b>{{item.input_output.output}}</b></div></div><p v-if="item.example"><strong>案例：</strong>{{item.example}}</p><p v-if="item.exam_focus"><strong>考查重点：</strong>{{item.exam_focus}}</p></div></div>
                      <div v-if="resourceJson(r).lifecycle_position" class="json-block lifecycle-box"><h4>在软件生命周期中的位置</h4><p><b>{{resourceJson(r).lifecycle_position.phase}}</b>：{{resourceJson(r).lifecycle_position.connection}}</p><div class="io-grid"><div><span>前置依赖</span><b>{{resourceJson(r).lifecycle_position.before}}</b></div><div><span>后续影响</span><b>{{resourceJson(r).lifecycle_position.after}}</b></div></div></div>
                      <div v-if="resourceJson(r).case_study" class="json-block case-box"><h4>{{resourceJson(r).case_study.title||'案例讲解'}}</h4><p><strong>场景：</strong>{{resourceJson(r).case_study.scenario}}</p><p><strong>分析：</strong>{{resourceJson(r).case_study.analysis}}</p><p><strong>收获：</strong>{{resourceJson(r).case_study.takeaway}}</p></div>
                      <div v-if="resourceJson(r).mistakes?.length" class="json-block"><h4>常见误区与纠正</h4><div class="mistake-list"><div v-for="item in resourceJson(r).mistakes" :key="item.mistake"><b>{{item.mistake}}</b><p>{{item.reason}}</p><p><strong>正确理解：</strong>{{item.correction}}</p><small>{{item.example}}</small></div></div></div>
                      <div v-if="resourceJson(r).learning_path?.length" class="json-block"><h4>推荐学习路径</h4><div class="step-list"><span v-for="(step,idx) in resourceJson(r).learning_path" :key="step">{{idx+1}}. {{step}}</span></div></div>
                      <div v-if="resourceJson(r).summary" class="json-block summary-box"><h4>阶段小结</h4><p>{{resourceJson(r).summary.one_sentence}}</p><ul><li v-for="item in resourceJson(r).summary.key_takeaways" :key="item">{{item}}</li></ul></div>
                      <div v-if="resourceJson(r).self_check?.length" class="json-block"><h4>自测问题</h4><div class="check-list"><div v-for="item in resourceJson(r).self_check" :key="item.question"><b>{{item.question}}</b><p>{{item.hint}}</p></div></div></div>
                      <div v-if="resourceJson(r).profilesummary" class="json-block"><h4>画像摘要</h4><p>专业：{{resourceJson(r).profilesummary.major||'未填写'}}；薄弱点：{{resourceJson(r).profilesummary.weakpoint||'待观察'}}；目标：{{resourceJson(r).profilesummary.studygoal||resourceJson(r).studygoal}}</p></div>
                      <div v-if="safeDocContext(r).pathText" class="json-block"><h4>当前学习位置</h4><p>{{safeDocContext(r).unit}} · {{safeDocContext(r).chapter}} · {{safeDocContext(r).section}} <span v-if="safeDocContext(r).pagesText">第 {{safeDocContext(r).pagesText}} 页</span></p></div>
                      <div v-if="safeKnowledgeRefs(r).length" class="json-block"><h4>课程知识库依据</h4><div v-for="item in safeKnowledgeRefs(r)" :key="item.key" class="kb-item"><b>{{item.title}}</b><em>{{item.sectionPathText}}</em><em v-if="item.source_file">来源：{{item.source_file}}</em><em v-if="item.pagesText">页码：{{item.pagesText}}</em><p>{{item.content_preview}}</p></div></div>
                    </div>
                  </template>
                  <div v-else class="res-content" :class="{collapsed:!resourceOpen(r)}">{{resourceText(r)}}</div>
                  <div v-if="!isReading(r)&&!isDoc(r)&&resourceOpen(r)&&resourceImages(r).length" class="image-gallery">
                    <div v-for="img in resourceImages(r)" :key="img.path||img" class="kb-image">
                      <img :src="imageUrl(img.path||img)" :alt="img.caption||'知识库配图'" loading="lazy" />
                      <p>{{img.caption||img.path||img}}</p>
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
              </div><el-empty v-else description="本阶段暂未匹配到资源，重新生成后会自动挂载。" />
              <div class="stage-eval stage-eval-standalone">
                <div><b>{{stageRecord(i)?.completed?'基础练习与阶段评估已完成':'基础练习与阶段评估'}}</b><p>{{stageQuizResource(s)?.title||'系统将根据本阶段知识点生成基础练习与阶段测评题。'}}</p><span v-if="stageRecord(i)?.completed">最近得分：{{stageRecord(i).avgScore}}分 · {{stageRecord(i).completedAt}}</span><span v-else>测评范围：{{(s.points||[]).join('、')||'本阶段核心知识点'}}</span></div>
                <el-button type="primary" @click="goStageEvaluation(s,i)">{{stageRecord(i)?.completed?'查看/重测':'开始练习测评'}}</el-button>
              </div>
            </div></el-collapse-transition>
        </el-card>
      </div>
    </div>

    <el-card class="panel feedback feedback-card"><div><el-tag type="primary" effect="light">学习反馈与动态调整</el-tag><b>让后续学习方案随掌握情况变化</b><p>提交学习反馈后，EvaluatorAgent 将分析你的掌握情况，由 PlannerAgent 动态调整后续阶段的难度与资源侧重。</p></div><div><el-button plain @click="fb('easy')">觉得太简单</el-button><el-button plain @click="fb('hard')">觉得太难</el-button><el-button type="primary" @click="fb('quiz')">根据练习结果调整</el-button></div></el-card>

    <el-dialog v-model="detailDialog.visible" :title="detailDialog.type==='basis'?'生成依据':'质量审核报告'" width="560px" destroy-on-close>
      <div v-if="detailDialog.resource" class="detail-dialog-body">
        <template v-if="detailDialog.type==='basis'">
          <h3>{{detailDialog.resource.title}}</h3>
          <p>{{detailDialog.resource.personalization||'依据学生画像、阶段目标、知识短板和课程知识库内容生成。'}}</p>
          <div class="detail-kv"><span>资源类型</span><b>{{typeName(detailDialog.resource.resource_type)}}</b></div>
          <div class="detail-kv"><span>关联知识点</span><b>{{kps(detailDialog.resource).join('、')||'课程核心知识'}}</b></div>
          <div class="detail-kv"><span>知识库来源</span><b>{{sourceText(detailDialog.resource)}}</b></div>
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
import { computed,nextTick,onMounted,ref,watch } from 'vue';
import { useRouter } from 'vue-router';
import { Transformer } from 'markmap-lib';
import { Markmap } from 'markmap-view';
import MarkdownIt from 'markdown-it';
import { ElMessage } from 'element-plus';
import { pathApi,profileApi,resourceApi } from '../api';
const router=useRouter();
const paths=ref([]),resources=ref([]),profile=ref({}),integrated=ref({}),loading=ref(false),progress=ref(0),completed=ref([]),hint=ref(''),openStages=ref({}),openResources=ref({}),assessmentRecords=ref([]),agentSteps=ref([]);
const detailDialog=ref({visible:false,type:'basis',resource:null});
const agents=[{name:'PlannerAgent',short:'PL',desc:'读取画像并规划阶段目标',p:18},{name:'RetrieverAgent',short:'RG',desc:'检索课程知识库和章节依据',p:34},{name:'ResourceAgents',short:'RA',desc:'生成讲解、练习、思维导图等资源',p:64},{name:'AuditAgent',short:'AU',desc:'校验事实准确性和格式质量',p:82},{name:'PackagerAgent',short:'PK',desc:'按阶段挂载资源并刷新页面',p:100}];
const markmapTransformer=new Transformer();
const markdownRenderer=new MarkdownIt({html:false,linkify:true,breaks:true});
const markmapEls=new Map();
const markmapInstances=new Map();
function resetAgentSteps(){agentSteps.value=agents.map(item=>({...item,status:'waiting',statusText:'等待'}))}
function setAgentStep(name,status,statusText){agentSteps.value=agentSteps.value.map(item=>item.name===name?{...item,status,statusText}:item)}
const latest=computed(()=>paths.value[0]||{}),rawStages=computed(()=>parseStages(latest.value.path_content||''));
const serverStages=computed(()=>Array.isArray(integrated.value.stages)?integrated.value.stages:[]);
const baseStages=computed(()=>serverStages.value.length?serverStages.value:(rawStages.value.length?rawStages.value:fallback()));
const title=computed(()=>integrated.value.topic||profile.value.target_course||profile.value.study_goal||baseStages.value[0]?.title||'个性化学习路径');
const basis=computed(()=>integrated.value.profile_basis?.summary||[profile.value.knowledge_base||profile.value.knowledge_level,profile.value.error_prone_points||profile.value.weak_points,profile.value.study_goal].filter(v=>v&&v!=='待进一步观察').join('；')||'等待画像生成后自动关联');
const current=computed(()=>Math.max(baseStages.value.findIndex((_,i)=>!completed.value.includes(i)),0));
const stages=computed(()=>baseStages.value.map((s,i)=>{const rawResources=Array.isArray(s.resources)?s.resources:matchRes(s,i,baseStages.value.length);return {...s,key:`${i}-${s.title}`,open:openStages.value[i]??i===current.value,allResources:rawResources,resources:displayResources(rawResources,s)}}));
const percent=computed(()=>Math.round(completed.value.length/Math.max(stages.value.length,1)*100));
const totalDays=computed(()=>integrated.value.total_duration||`${stages.value.reduce((n,s)=>n+Number(String(s.duration).match(/\d+/)?.[0]||0),0)||stages.value.length}天`);
function clean(t){return String(t||'').replace(/[#*_`>\-]/g,'').trim()}
function parseStages(md){return String(md||'').split(/\n(?=##\s*阶段[一二三四五六七八九十\d]+)/).filter(b=>/^##\s*阶段/.test(b.trim())).map((b,i)=>({title:clean((b.split('\n')[0]||'').replace(/^##\s*阶段[一二三四五六七八九十\d]+[：:、.．\s]*/,''))||`学习阶段${i+1}`,goal:section(b,'目标')||section(b,'学习任务')||'围绕画像短板完成本阶段学习任务。',points:points(b),duration:(b.match(/(\d+)\s*天/)?.[1]?`预计${b.match(/(\d+)\s*天/)[1]}天`:`预计${i+2}天`),raw:b}))}
function section(b,l){const m=b.match(new RegExp(`\\*\\*${l}[：:]?\\*\\*\\s*([^\\n]+)`));return m?clean(m[1]):''}
function points(b){const ks=['需求分析','总体设计','详细设计','软件测试','软件生命周期','用例图','类图','时序图','数据流图','模块划分','编码实现','软件维护'];const hit=ks.filter(k=>b.includes(k));return [...new Set(hit.length?hit:['课程核心知识'])].slice(0,5)}
function fallback(){return resources.value.length?[{title:'基础概念澄清',goal:'理解核心概念、阶段产物和输入输出关系。',points:['软件生命周期','需求分析'],duration:'预计2天',raw:''},{title:'方法关系建构',goal:'建立需求分析、总体设计、详细设计之间的顺序关系。',points:['需求分析','总体设计','详细设计'],duration:'预计3天',raw:''},{title:'练习与实操巩固',goal:'通过练习、案例和代码实操完成迁移应用。',points:['软件测试','代码实操'],duration:'预计2天',raw:''}]:[]}
function kps(r){if(Array.isArray(r.knowledge_points))return r.knowledge_points;try{return JSON.parse(r.knowledge_points||'[]')}catch{return[]}}
function score(r,text){return kps(r).reduce((n,p)=>n+(p&&text.includes(p)?5:0),0)+['需求分析','总体设计','详细设计','测试','生命周期','代码','练习'].reduce((n,k)=>n+(text.includes(k)&&`${r.title} ${r.content}`.includes(k)?2:0),0)}
function resourceStageIndex(r){const meta=r.metadata||{};const idx=r.stage_index||meta.stage_index||meta.stage?.stage_index;const n=Number(idx);return Number.isFinite(n)?n:null}
function matchRes(s,i,total){const exact=resources.value.filter(r=>resourceStageIndex(r)===i+1);const text=`${s.title} ${s.goal} ${s.points.join(' ')} ${s.raw}`;const m=resources.value.filter(r=>!resourceStageIndex(r)&&score(r,text)>0);const list=exact.length?exact:(m.length?m:resources.value.filter((r,idx)=>!resourceStageIndex(r)&&(total?idx%total===i:true)));const order=['doc','mindmap','quiz','code','video','reading'];return [...list].sort((a,b)=>order.indexOf(a.resource_type)-order.indexOf(b.resource_type))}
function mergedDocResource(items,stage){
  const docs=items.filter(r=>r.resource_type==='doc');
  if(!docs.length)return fallbackDocResource(stage);
  const first=docs[0];
  const jsonDocs=docs.map(resourceJson).filter(Boolean);
  const content=jsonDocs.length?mergeDocJson(jsonDocs,docs,stage):fallbackDocJson(docs,stage);
  return {...first,id:`merged-doc-${stage.title}`,title:`${stage.title}・综合讲解文档`,content:JSON.stringify(content),personalization:[...new Set(docs.map(r=>r.personalization).filter(Boolean))].join('；')||first.personalization,knowledge_points:[...new Set(docs.flatMap(r=>kps(r)))],quality_score:Math.round(docs.reduce((sum,r)=>sum+qScore(r),0)/docs.length),sources:docs.flatMap(r=>r.sources||[])}
}
function fallbackDocResource(stage){
  const content=fallbackDocJson([],stage);
  return {id:`fallback-doc-${stage.title}`,resource_type:'doc',title:`${stage.title}・综合讲解文档`,content:JSON.stringify(content),knowledge_points:stage.points||[],personalization:'依据当前阶段目标和知识点自动补齐讲解文档，确保每个阶段都有可学习的结构化讲义。',quality_score:86,sources:[]};
}
function mergeDocJson(jsonDocs,docs,stage){
  const first=jsonDocs[0]||{};
  const points=[...new Set(docs.flatMap(r=>kps(r)).concat(stage.points||[]))].filter(Boolean);
  return {...first,resourcetype:'doc',resourcetitle:`${stage.title}・综合讲解文档`,weakpoints:first.weakpoints?.length?first.weakpoints:points,studygoal:first.studygoal||stage.goal,overview:first.overview||fallbackDocJson(docs,stage).overview,core_concepts:jsonDocs.flatMap(d=>d.core_concepts||[]).slice(0,6),knowledge_explanation:jsonDocs.flatMap(d=>d.knowledge_explanation||[]).slice(0,8),mistakes:jsonDocs.flatMap(d=>d.mistakes||[]).slice(0,6),learningresources:jsonDocs.flatMap(d=>d.learningresources||[]),summary:first.summary||fallbackDocJson(docs,stage).summary,self_check:jsonDocs.flatMap(d=>d.self_check||[]).slice(0,5),lifecycle_position:first.lifecycle_position||fallbackDocJson(docs,stage).lifecycle_position,case_study:first.case_study||fallbackDocJson(docs,stage).case_study,learning_path:first.learning_path||fallbackDocJson(docs,stage).learning_path};
}
function fallbackDocJson(docs,stage){
  const points=[...new Set(docs.flatMap(r=>kps(r)).concat(stage.points||[]))].filter(Boolean);
  const topic=points.join('、')||stage.title||'软件工程核心知识';
  const sourceText=docs.map(r=>resourceText(r)).filter(Boolean).join('\n').slice(0,900);
  return {resourcetype:'doc',resourcetitle:`${stage.title}・综合讲解文档`,knowledgelevel:'待观察',studystyle:'综合学习',weakpoints:points,studygoal:stage.goal||`理解${topic}`,estimatedtime:'25分钟',overview:{title:'本阶段学习导入',content:`本阶段围绕${topic}展开。学习目标不是简单记住概念，而是理解它们在软件工程流程中的作用：解决什么问题、依赖什么输入、产生什么输出，并能结合案例分析常见质量风险。`},core_concepts:points.slice(0,4).map(p=>({name:p,definition:`${p}是本阶段需要重点掌握的软件工程知识点。`,why_it_matters:'它会影响需求、设计、实现、测试或维护等后续活动的质量。',example:`可结合课程项目分析${p}在当前阶段的作用。`,common_misunderstanding:'只记概念名称，不理解适用场景和阶段产物。'})),knowledge_explanation:points.slice(0,4).map(p=>({title:p,explanation:`${p}需要放在完整的软件工程活动中理解。它通常不是孤立知识点，而是和项目目标、阶段任务、输入输出和质量控制相关。学习时应先明确概念边界，再分析它解决的问题，最后通过课程案例理解它如何影响后续设计、实现、测试或维护。${sourceText?`课程资料提示：${sourceText}`:''}`,process:['明确概念边界','识别输入信息','理解处理活动','总结输出产物'],input_output:{input:'课程案例、需求描述、设计或实现信息',output:'概念理解、阶段产物或质量判断'},example:`以一个在线学习系统为例，可以用${p}判断当前阶段需要完成哪些任务以及可能产生哪些风险。`,exam_focus:'常考定义、作用、流程、输入输出和相近概念辨析。'})),lifecycle_position:{phase:'当前阶段',before:'前置课程概念和阶段资料',after:'后续设计、实现、测试、维护或质量评估',connection:`${topic}会连接软件生命周期中的前后活动，理解上下游关系有助于形成系统化认知。`},case_study:{title:'课程项目案例讲解',scenario:'假设团队正在开发一个在线学习系统，需要从需求理解、功能设计到测试验证逐步推进。',analysis:`在这个场景中，${topic}可以帮助团队明确当前阶段的关键任务。如果只停留在口头理解，容易出现概念混淆、阶段产物不清或测评答题时无法迁移的问题。通过把知识点转化为输入、过程和输出，学生可以更清楚地看到每个软件工程活动的价值。`,takeaway:'学习软件工程知识时，要始终追问它解决什么问题、输出什么产物、会影响哪些后续环节。'},mistakes:[{mistake:'只记概念名称',reason:'没有结合项目流程',correction:'从作用、输入输出和案例三个角度理解',example:'解释一个概念时同时说明它会产生什么阶段产物。'},{mistake:'混淆相近概念',reason:'没有比较适用场景',correction:'通过边界、目标和产物进行区分',example:'区分测试与调试、需求与设计等概念。'},{mistake:'忽略后续影响',reason:'只看当前阶段',correction:'分析它对后续环节的影响',example:'需求不清会导致测试用例难以设计。'}],learning_path:['先理解阶段目标和核心概念','再逐个学习知识点详细讲解','结合案例分析输入、过程和输出','最后完成自测并进入阶段评估'],summary:{key_takeaways:[`${topic}需要结合软件生命周期理解`,'学习重点是概念、流程、产物和易错点','通过案例和自测可以检验迁移应用能力'],one_sentence:`本阶段核心是把${topic}从概念记忆转化为软件工程场景中的应用能力。`},self_check:[{question:`请说明${points[0]||topic}解决什么问题？`,hint:'从目标、输入和输出角度回答。'},{question:'本阶段知识点会影响哪些后续阶段？',hint:'联系设计、测试、维护或质量评估。'},{question:'举一个课程案例说明本阶段知识点的作用。',hint:'用一个软件项目场景说明。'}],learningresources:docs.flatMap(r=>resourceJson(r)?.learningresources||[])};
}
function displayResources(items,stage){const mergedDoc=mergedDocResource(items,stage);const mindmap=items.find(r=>r.resource_type==='mindmap')||fallbackMindmapResource(stage);const reading=items.find(r=>r.resource_type==='reading');const video=items.find(r=>r.resource_type==='video');return [mergedDoc,mindmap,video,reading].filter(Boolean)}
function fallbackMindmapResource(stage){const points=stage.points?.length?stage.points:['课程核心知识'];return {id:`fallback-mindmap-${stage.title}`,resource_type:'mindmap',title:`${stage.title}・阶段知识导图`,content:[`# ${stage.title}`,'## 阶段目标',`### 学习任务\n- ${stage.goal||'理解本阶段核心知识'}`,'## 知识点展开',...points.map(p=>`### ${p}\n- ⭐ 概念定义\n- 关键作用\n- 典型应用场景\n- 与本阶段目标的关系`),'## 易错提醒','### 概念边界\n- ⚠️ 注意与相近概念区分\n- ⚠️ 不要只记结论，要理解适用条件','### 学习建议\n- 结合教材图示和案例理解流程\n- 完成基础练习后进入阶段评估'].join('\n'),knowledge_points:points,quality_score:85,sources:[]}}
function stageQuizResource(stage){return (stage.allResources||[]).find(r=>r.resource_type==='quiz')}
function typeName(t){return({doc:'讲解文档',quiz:'基础练习题',reading:'拓展阅读',mindmap:'思维导图',code:'代码案例',video:'教学短视频'}[t]||t||'学习资源')}
function resourceIcon(t){return({doc:'📄',mindmap:'🧠',quiz:'✏️',code:'💻',video:'▶️',reading:'📖'}[t]||'📎')}
function resourceClass(r){return `res-${r.resource_type||'default'}`}
function rid(r){return`${r.id||r.resource_type}-${r.title}`}
function hasModelError(t){const text=String(t||'');return /\{\s*"?success"?\s*:\s*false/i.test(text)||text.includes('调用失败')||text.includes('AppIdNoAuthError')||text.includes('NoAuth')||text.includes('anthropic/messages')}
function preview(r){const text=resourceText(r);return text.length>180?`${text.slice(0,180)}...`:text}
function extractJsonText(raw){return String(raw||'').replace(/^\s*```(?:json)?\s*/i,'').replace(/```\s*$/,'').replace(/^\s*json\s*/i,'').trim()}
function resourceJson(r){const raw=extractJsonText(r.content);const start=raw.indexOf('{'),end=raw.lastIndexOf('}');if(start<0||end<=start)return null;try{const data=JSON.parse(raw.slice(start,end+1));return data&&typeof data==='object'&&!Array.isArray(data)?data:null}catch{return null}}
function normalizeCompareText(value){return String(value||'').trim().toLowerCase().replace(/[\s\-_—–·•，。！？；：、,.!?;:()[\]{}<>《》“”"'`~]+/g,'')}
function dedupeBy(items,keyFn){const seen=new Set();return(items||[]).filter(item=>{const key=keyFn(item);if(!key||seen.has(key))return false;seen.add(key);return true})}
function safeDocContext(r){const doc=resourceJson(r)||{};const ctx=doc.studentcontext||{};const path=Array.isArray(ctx.path)?ctx.path:[];const unit=ctx.currentunit||path[0]||'';const chapter=ctx.currentchapter||path[1]||'';const section=ctx.currentsection||path[2]||'';const pages=Array.isArray(ctx.currentpage)?ctx.currentpage:(ctx.currentpage?[ctx.currentpage]:[]);return{unit,chapter,section,pages,pagesText:pages.join('、'),pathText:[unit,chapter,section].filter(Boolean).join(' > ')}}
function safeKnowledgeRefs(r){const doc=resourceJson(r)||{};return dedupeBy((doc.learningresources||[]).map(item=>{const sectionPath=Array.isArray(item?.section_path)?item.section_path:[];const pages=Array.isArray(item?.pages)?item.pages:[];return{key:`${item?.title||''}-${sectionPath.join('-')}-${pages.join('-')}`,title:item?.title||'未命名知识点',content_preview:item?.content_preview||'',sectionPathText:sectionPath.join(' > '),pagesText:pages.join('、'),source_file:item?.source_file||''}}),item=>normalizeCompareText(item.key))}
function imageUrl(path){const base=import.meta.env.VITE_API_BASE_URL||'http://localhost:5000/api';return `${base}/knowledge/image?path=${encodeURIComponent(path)}`}
function resourceImages(r){const meta=r.metadata||{};const json=resourceJson(r);const found=[];const add=(img,caption='知识库配图')=>{if(!img)return;const item=typeof img==='string'?{path:img,caption}:img;if(item.path&&!found.some(x=>x.path===item.path))found.push(item)};(Array.isArray(meta.images)?meta.images:[]).forEach(add);(json?.images||[]).forEach(add);(json?.learningresources||[]).forEach(item=>(item.images||[]).forEach(img=>add(img,item.title||'知识库配图')));String(r.content||'').match(/images[\\/][^\n\r，,；;）)]+?\.(?:png|jpg|jpeg|webp|gif)/gi)?.forEach(path=>add(path,path));return found.slice(0,6)}
function isMindmap(r){return r.resource_type==='mindmap'}
function isReading(r){return r.resource_type==='reading'}
function isDoc(r){return r.resource_type==='doc'}
function readingText(r){const text=resourceText(r);if(text&&text.length>220)return text;const points=kps(r).join('、')||'软件工程核心知识';return `# ${r.title||`${points}拓展阅读`}

## 为什么值得读
围绕“${points}”进行拓展阅读，可以把教材中的概念、流程和阶段产物放到真实软件项目中理解。很多软件工程知识并不是为了考试而存在，而是为了帮助团队降低沟通成本、控制质量风险，并让需求、设计、测试和维护之间形成闭环。

## 与课程知识点的连接
这些内容对应课程中的概念定义、流程活动、阶段产物和质量保障问题。学习时建议重点关注三个问题：它解决什么问题、需要什么输入、会产生什么输出。如果能把这三个问题讲清楚，说明你已经从记忆概念进入到理解应用阶段。

## 拓展知识讲解
在实际项目中，${points}通常会和需求管理、缺陷跟踪、版本控制、持续集成、质量评审等活动结合。例如，需求分析不仅是写需求文档，还包括识别用户目标、澄清边界、确认优先级和建立验收标准；软件测试也不只是运行程序，而是通过测试计划、测试用例、缺陷记录和回归验证持续降低风险。

## 真实场景示例
假设团队正在开发一个在线学习系统。如果前期需求分析没有明确“课程进度如何统计”“测评成绩如何影响推荐路径”，后续设计和测试阶段就会出现反复返工。相反，如果需求阶段已经定义好用户角色、业务流程、异常情况和验收标准，测试人员就能更早设计测试用例，开发人员也能更清楚地拆分模块。

## 阅读导读
- 第一遍先看概念之间的关系，不必纠结细节。
- 第二遍关注输入、过程、输出和参与角色。
- 第三遍结合课程案例，尝试画出流程图或检查清单。
- 最后用阶段测评检验自己能否迁移应用。

## 思考问题
- 这些知识点在软件生命周期中处于什么位置？
- 它们会影响哪些后续阶段？
- 如果忽略这些活动，会造成哪些质量风险？
- 如何用一个课程案例说明它们的作用？

## 进一步探索方向
探索建议：可以继续了解敏捷开发、DevOps、自动化测试、需求管理平台、缺陷生命周期管理和软件质量度量。学习时不需要追求工具细节，而要观察这些工具如何把教材中的概念变成可执行流程。`;}
function renderReading(r){return markdownRenderer.render(readingText(r));}
function normalizeMindmapRoot(title){
  const text=clean(String(title||'').replace(/个性化|知识思维导图|思维导图|阶段知识导图|软件工程知识导图/g,'')).trim();
  return text||'软件工程核心知识';
}
function normalizeMindmapMarkdown(r){
  const rootTitle=normalizeMindmapRoot(r.title||kps(r)[0]);
  const raw=extractJsonText(r.content||'').replace(/center[_\s-]*topic|center\s*theme|root\(\(|\)\)|mindmap/gi,'').trim();
  const lines=raw.split('\n').map(line=>line.trim()).filter(line=>line&&!/images[\\/]/i.test(line)&&!/知识库配图/.test(line));
  if(lines.some(line=>line.startsWith('#'))){
    const cleanedLines=lines.map(line=>line.replace(/^[+\-–—]+\s*/,'').replace(/\s+/g,' ').trim()).filter(Boolean);
    const normalized=cleanedLines.map((line,index)=>index===0&&line.startsWith('#')?`# ${rootTitle}`:line).join('\n');
    return normalized.startsWith('#')?normalized:`# ${rootTitle}\n${normalized}`;
  }
  const points=kps(r);
  const modules=points.length?points:[rootTitle,'核心概念','易错点'];
  return [`# ${rootTitle}`,'## 知识点展开',...modules.slice(0,8).map(p=>`### ${p}\n- ⭐ 概念定义\n- 关键作用\n- 应用场景\n- 常见误区`),'## 学习路径','### 先理解概念\n- 明确输入输出和阶段产物','### 再结合案例\n- 用教材案例验证理解','### 最后练习评估\n- 通过题目定位薄弱点'].join('\n');
}
function setMarkmapRef(r,el){
  const id=rid(r);
  if(el)markmapEls.set(id,el);else markmapEls.delete(id);
  renderMarkmaps();
}
async function renderMarkmaps(){
  await nextTick();
  for(const s of stages.value){
    for(const r of s.resources||[]){
      if(!isMindmap(r))continue;
      const id=rid(r);
      const el=markmapEls.get(id);
      if(!el)continue;
      const {root}=markmapTransformer.transform(normalizeMindmapMarkdown(r));
      const options={duration:260,maxWidth:220,spacingVertical:8,spacingHorizontal:56,color:(node)=>['#2563eb','#7c3aed','#16a34a','#f97316'][node.state.depth%4]||'#64748b'};
      if(markmapInstances.has(id)){
        const mm=markmapInstances.get(id);
        mm.setData(root);
        mm.fit();
      }else{
        const mm=Markmap.create(el,options,root);
        markmapInstances.set(id,mm);
        setTimeout(()=>mm.fit(),80);
      }
    }
  }
}function pagesText(value){return Array.isArray(value)?value.join('、'):String(value||'')}
function resourceText(r){const raw=String(r.content||r.personalization||'点击学习资源页面查看完整内容。');if(hasModelError(raw))return `${typeName(r.resource_type)}已挂载到当前阶段，建议结合本阶段目标学习对应内容。`;const parsed=resourceJson(r);if(parsed)return clean(parsed.content||parsed.studygoal||parsed.resourcetitle||r.title);return clean(extractJsonText(raw))}
function resourceOpen(r){return !!openResources.value[rid(r)]}
function openResourceDetail(resource,type){detailDialog.value={visible:true,type,resource}}
function toggleResource(r){const id=rid(r);openResources.value={...openResources.value,[id]:!openResources.value[id]}}
function toggleStage(i){if(i>current.value&&!done(i)){ElMessage.warning('请先完成前置阶段，再解锁后续学习内容');return}openStages.value={...openStages.value,[i]:!(openStages.value[i]??i===current.value)}}
function q(r){return r.quality||r.metadata?.quality||{}}function qScore(r){return Number(r.quality_score||q(r).total||80)}function qPass(r){return q(r).passed!==false&&qScore(r)>=75}
function sourceText(r){const n=[...new Set((r.sources||[]).map(s=>s.source||s.source_name).filter(Boolean))].length;return n?`已关联 ${n} 个课程知识库来源，并保留防幻觉审核信息。`:'建议在资源页复核课程依据。'}
function done(i){return completed.value.includes(i)}function state(i){return done(i)?'completed':i===current.value?'current':'pending'}function label(i){return{completed:'已完成',current:'当前阶段',pending:'未开始'}[state(i)]}function tag(i){return{completed:'success',current:'primary',pending:'info'}[state(i)]}
function toggle(i){completed.value=done(i)?completed.value.filter(x=>x!==i):[...completed.value,i];localStorage.setItem('a3_path_done',JSON.stringify(completed.value))}
function stageRecord(i){return assessmentRecords.value.find(item=>Number(item.stageIndex)===i)}
function loadAssessmentRecords(){try{assessmentRecords.value=JSON.parse(localStorage.getItem('a3_stage_assessment_records')||'[]')}catch{assessmentRecords.value=[]}}
function goStageEvaluation(s,i){router.push({path:'/evaluation',query:{stage:String(i),from:'path',title:s.title,points:(s.points||[]).join('、')}})}
async function loadAll(){const[ig,p,r,pf]=await Promise.all([pathApi.integrated(),pathApi.list(),resourceApi.list(),profileApi.get()]);if(ig.code===200)integrated.value=ig.data||{};if(p.code===200)paths.value=p.data||[];if(r.code===200)resources.value=(ig.code===200&&Array.isArray(ig.data?.resources))?ig.data.resources:(r.data||[]);if(pf.code===200)profile.value=pf.data||{};try{completed.value=JSON.parse(localStorage.getItem('a3_path_done')||'[]')}catch{completed.value=[]}loadAssessmentRecords()}
async function generateAll(extra=''){
  loading.value=true;progress.value=5;resetAgentSteps();
  const timer=setInterval(()=>progress.value=Math.min(progress.value+3,94),700);
  try{
    const need=[profile.value.study_goal,profile.value.error_prone_points||profile.value.weak_points,hint.value,extra].filter(Boolean).join('；');
    setAgentStep('PlannerAgent','running','规划中');progress.value=14;
    const pr=await pathApi.generate({learning_need:need,adjustment:hint.value});
    if(pr.code!==200)throw new Error(pr.msg||'学习路径生成失败');
    setAgentStep('PlannerAgent','done','已完成');
    setAgentStep('RetrieverAgent','running','检索中');progress.value=32;
    await new Promise(resolve=>setTimeout(resolve,350));
    setAgentStep('RetrieverAgent','done','已关联');
    setAgentStep('ResourceAgents','running','生成中');progress.value=52;
    const rr=await resourceApi.generate({learning_need:need});
    if(rr.code!==200)throw new Error(rr.msg||'学习资源生成失败');
    setAgentStep('ResourceAgents','done','已完成');
    setAgentStep('AuditAgent','running','审核中');progress.value=78;
    await new Promise(resolve=>setTimeout(resolve,450));
    setAgentStep('AuditAgent','done','已通过');
    setAgentStep('PackagerAgent','running','挂载中');progress.value=90;
    await loadAll();completed.value=[];localStorage.setItem('a3_path_done','[]');
    setAgentStep('PackagerAgent','done','已刷新');progress.value=100;
    ElMessage.success('路径与资源一体化方案生成成功')
  }catch(e){agentSteps.value=agentSteps.value.map(item=>item.status==='running'?{...item,status:'error',statusText:'失败'}:item);ElMessage.error(e?.message||'一体化生成失败')}
  finally{clearInterval(timer);setTimeout(()=>{loading.value=false},650)}
}
function pace(c){hint.value=({fast:'学习节奏加快，资源更精炼。',slow:'学习节奏放慢，增加概念解释和基础练习。',practice:'增加练习题、代码案例和应用任务比例。'}[c]||'');generateAll(hint.value)}
function fb(t){hint.value=({easy:'学生反馈太简单，请提高后续应用和实操难度。',hard:'学生反馈太难，请降低难度并增加基础讲解。',quiz:'结合练习结果调整后续路径，强化错题知识点。'}[t]||'');ElMessage.info('已收到反馈，正在调整后续学习方案…');generateAll(hint.value)}
onMounted(()=>{loadAll();renderMarkmaps()});
watch(stages,renderMarkmaps,{deep:true,flush:'post'});
</script>

<style scoped>
.path-page{display:grid;gap:22px;background:#f7f9fc}.overview-card{overflow:hidden;border:1px solid #dbeafe;background:linear-gradient(135deg,#ffffff 0%,#f8fbff 62%,#eef6ff 100%);box-shadow:0 18px 48px rgba(15,23,42,.06)}.overview-grid{display:grid;grid-template-columns:minmax(0,1fr) 420px;gap:24px;align-items:start}.overview-main h2{margin:14px 0 8px;font-size:30px;color:#0f172a;letter-spacing:-.02em}.overview-main p{max-width:760px;color:#475569;line-height:1.85}.profile-tags{display:flex;flex-wrap:wrap;gap:10px;margin-top:14px}.overview-side{display:grid;gap:14px}.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}.stats div{min-height:102px;padding:18px;border:1px solid #dbeafe;border-radius:22px;background:rgba(255,255,255,.88);box-shadow:0 12px 28px rgba(37,99,235,.06)}.stats b{display:block;font-size:25px;color:#0f172a}.stats span{display:block;margin-top:6px;color:#64748b}.overview-actions{display:flex;justify-content:flex-end;gap:12px}.overview-progress{display:grid;grid-template-columns:minmax(0,1fr) 90px;gap:14px;align-items:center;margin-top:20px}.overview-progress span{color:#64748b;text-align:right;font-size:13px}.line,.stage-head,.res-head,.feedback{display:flex;align-items:center;justify-content:space-between;gap:14px}.run-grid{display:grid;grid-template-columns:minmax(0,1fr) 320px;gap:16px;margin-top:18px}.agent-flow{display:grid;gap:10px}.run-step{display:grid;grid-template-columns:42px minmax(0,1fr) 64px;align-items:center;gap:12px;padding:12px;border:1px solid #e2e8f0;border-radius:16px;background:#fff;color:#64748b;transition:.2s ease}.run-step b{display:grid;width:34px;height:34px;place-items:center;border-radius:12px;background:#e2e8f0;color:#475569}.run-step strong,.run-step span{display:block}.run-step span{font-size:12px}.run-step em{font-style:normal;font-size:12px;text-align:right}.run-step.running{border-color:#60a5fa;background:#eff6ff;color:#1d4ed8;box-shadow:0 10px 28px rgba(37,99,235,.12)}.run-step.running b{background:linear-gradient(135deg,#2563eb,#06b6d4);color:#fff}.run-step.done{border-color:#86efac;background:#f0fdf4;color:#15803d}.run-step.done b{background:#22c55e;color:#fff}.run-step.error{border-color:#fecaca;background:#fef2f2;color:#dc2626}.run-step.error b{background:#ef4444;color:#fff}.live-preview{padding:16px;border:1px solid #dbeafe;border-radius:18px;background:linear-gradient(135deg,#f8fbff,#fff)}.live-preview b{display:block;color:#0f172a}.live-preview p{color:#1d4ed8;line-height:1.7}.live-preview small{color:#64748b;line-height:1.6}.timeline{position:relative;display:grid;gap:20px;margin-left:26px}.timeline:before{position:absolute;top:12px;bottom:12px;left:17px;width:3px;border-radius:999px;background:#dbeafe;content:""}.stage{position:relative;display:grid;grid-template-columns:56px 1fr;gap:16px}.dot{z-index:1;display:flex;justify-content:center;padding-top:18px}.dot span{display:grid;width:38px;height:38px;place-items:center;border-radius:999px;background:#cbd5e1;color:#fff;font-weight:800}.stage.current .dot span{background:#2563eb;box-shadow:0 0 0 8px #dbeafe}.stage.completed .dot span{background:#16a34a}.stage-card{border-radius:22px}.stage.current .stage-card{border-color:#93c5fd;box-shadow:0 16px 36px rgba(37,99,235,.12)}.stage-head h3{margin:10px 0 6px;color:#0f172a}.stage-head p{margin:0;color:#64748b}.body{display:grid;gap:16px}.goal{padding:16px;border:1px solid #dbeafe;border-radius:16px;background:#f8fbff}.stage-eval{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:14px 16px;border:1px solid #bbf7d0;border-radius:16px;background:linear-gradient(135deg,#f0fdf4,#fff)}.stage-eval.stage-eval-standalone{margin-top:4px;border-color:#bfdbfe;background:linear-gradient(135deg,#eff6ff,#ffffff)}.stage-eval.stage-eval-standalone b{color:#1d4ed8}.stage-eval b{color:#15803d}.stage-eval p{margin:6px 0;color:#334155}.stage-eval span{color:#64748b;font-size:12px}.goal b,.section b,.feedback b{color:#1d4ed8}.goal p,.feedback p{margin:8px 0 0;color:#334155;line-height:1.8}.tags{display:flex;flex-wrap:wrap;gap:8px;align-items:center;color:#64748b}.section{display:flex;justify-content:space-between;color:#64748b}.res-list{display:grid;gap:16px}.res{position:relative;display:grid;gap:12px;padding:18px 18px 18px 20px;border:1px solid #dbeafe;border-left:5px solid #3b82f6;border-radius:20px;background:linear-gradient(135deg,#fff,#f8fbff);box-shadow:0 12px 28px rgba(15,23,42,.05);cursor:pointer;transition:.18s ease}.res:hover{transform:translateY(-2px);box-shadow:0 18px 36px rgba(15,23,42,.08)}.res-doc{border-left-color:#3b82f6}.res-mindmap{border-left-color:#8b5cf6}.res-quiz{border-left-color:#22c55e;background:linear-gradient(135deg,#f0fdf4,#ffffff)}.res-code{border-left-color:#f97316}.res-video{border-left-color:#ef4444}.res-reading{border-left-color:#64748b}.res-icon{display:grid;width:30px;height:30px;place-items:center;border-radius:10px;background:#f1f5f9;font-size:16px}.res-head{justify-content:space-between;flex-wrap:wrap;margin-bottom:2px}.res-title{display:flex;align-items:center;gap:10px;flex-wrap:wrap;min-width:0}.res-title strong{min-width:0;overflow:visible;white-space:normal;color:#0f172a;font-size:16px;line-height:1.5}.res-content,.json-doc{padding:16px;border:1px solid #e2e8f0;border-radius:18px;background:#fff;color:#334155;line-height:1.9;font-size:14px;white-space:normal;word-break:break-word}.res-content{white-space:pre-wrap}.res-content.collapsed,.json-doc.collapsed{display:-webkit-box;max-height:220px;overflow:hidden;-webkit-line-clamp:8;-webkit-box-orient:vertical;color:#475569}.reading-content{min-height:260px;padding:22px 24px;border:1px solid #e2e8f0;border-radius:18px;background:linear-gradient(135deg,#ffffff,#f8fafc);color:#334155;line-height:1.95;font-size:14px;overflow:hidden}.reading-content.collapsed{display:-webkit-box;max-height:360px;-webkit-line-clamp:12;-webkit-box-orient:vertical}.reading-content :deep(h1){margin:0 0 16px;color:#0f172a;font-size:22px;line-height:1.4}.reading-content :deep(h2){margin:22px 0 10px;padding-left:10px;border-left:4px solid #3b82f6;color:#1d4ed8;font-size:17px}.reading-content :deep(p){margin:8px 0;color:#334155}.reading-content :deep(ul){margin:8px 0 8px 18px;padding:0}.reading-content :deep(li){margin:5px 0}.reading-content :deep(strong){color:#0f172a}.json-summary{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:14px;white-space:normal}.json-summary div{padding:14px;border-radius:16px;background:linear-gradient(135deg,#f8fbff,#fff);border:1px solid #dbeafe}.json-summary span{display:block;color:#64748b;font-size:12px}.json-summary b{display:block;margin-top:4px;color:#0f172a;line-height:1.5}.doc-hero{padding:18px;border:1px solid #bfdbfe;border-radius:18px;background:linear-gradient(135deg,#eff6ff,#ffffff)}.doc-hero h3{margin:0 0 8px;color:#1d4ed8}.doc-hero p{margin:0;line-height:1.9}.json-block{margin-top:16px;padding-top:16px;border-top:1px dashed #dbeafe;white-space:normal}.json-block h4{margin:0 0 12px;color:#1d4ed8;font-size:16px}.json-block p{margin:7px 0;line-height:1.9}.concept-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}.concept-card,.explain-card,.mistake-list>div,.check-list>div{padding:14px;border:1px solid #e2e8f0;border-radius:16px;background:#f8fafc}.concept-card b,.mistake-list b,.check-list b{display:block;color:#0f172a}.concept-card small,.concept-card em,.mistake-list small{display:block;margin-top:6px;color:#64748b;font-style:normal;line-height:1.7}.explain-card{margin-top:10px;background:#fff}.explain-card h5{margin:0 0 8px;color:#0f172a;font-size:15px}.step-list{display:flex;flex-wrap:wrap;gap:8px;margin:10px 0}.step-list span{padding:7px 10px;border-radius:999px;background:#eef6ff;color:#1d4ed8;font-size:12px}.io-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin:10px 0}.io-grid div{padding:10px 12px;border-radius:14px;background:#f8fafc;border:1px solid #e2e8f0}.io-grid span{display:block;color:#64748b;font-size:12px}.io-grid b{display:block;margin-top:4px;color:#0f172a;line-height:1.6}.lifecycle-box,.case-box,.summary-box{padding:14px 16px;border:1px solid #bfdbfe;border-radius:16px;background:linear-gradient(135deg,#f8fbff,#fff)}.mistake-list,.check-list{display:grid;gap:10px}.summary-box ul{margin:8px 0 0 18px;padding:0}.kb-item{padding:10px 12px;margin-top:8px;border-radius:14px;background:#f8fbff}.kb-item b,.kb-item em{display:block}.kb-item em{margin-top:4px;color:#64748b;font-style:normal;font-size:12px}.markmap-panel{padding:10px;border:1px solid #e9d5ff;border-radius:16px;background:linear-gradient(135deg,#fbf7ff,#ffffff);overflow:hidden}.markmap-panel.collapsed{max-height:380px}.markmap-container{display:block;width:100%;height:360px;border-radius:12px;background:#fafbfc;font-family:Inter,Microsoft YaHei,sans-serif}.markmap-container :deep(.markmap-node){cursor:pointer}.markmap-container :deep(.markmap-node text){font-size:13px;fill:#0f172a}.markmap-container :deep(.markmap-link){stroke-width:1.8px}.image-gallery{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;padding:12px;border:1px dashed #bfdbfe;border-radius:18px;background:#f8fbff}.kb-image{padding:10px;border:1px solid #dbeafe;border-radius:16px;background:#fff;box-shadow:0 8px 18px rgba(15,23,42,.04)}.kb-image img{display:block;width:100%;height:190px;object-fit:contain;border-radius:12px;background:#fff}.kb-image p{margin:8px 0 0;color:#64748b;font-size:12px;line-height:1.5;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.res-meta{display:flex;flex-wrap:wrap;gap:8px;color:#64748b;font-size:12px}.res-meta span{padding:5px 9px;border-radius:999px;background:#f1f5f9}.res-actions{display:flex;justify-content:flex-end;align-items:center;gap:4px;padding-top:2px}.res-actions :deep(.el-button){padding:4px 6px;color:#64748b;font-size:13px}.res-actions :deep(.el-button:hover){color:#2563eb;background:transparent}.detail-dialog-body{display:grid;gap:14px;color:#334155;line-height:1.8}.detail-dialog-body h3{margin:0;color:#0f172a;font-size:18px}.detail-dialog-body p{margin:0;padding:12px 14px;border-radius:14px;background:#f8fafc}.detail-kv{display:flex;justify-content:space-between;gap:16px;padding:10px 12px;border:1px solid #e2e8f0;border-radius:12px;background:#fff}.detail-kv span{color:#64748b}.detail-kv b{color:#0f172a;text-align:right}.feedback-card{border:1px solid #bfdbfe;background:linear-gradient(135deg,#eff6ff,#ffffff);box-shadow:0 16px 38px rgba(37,99,235,.08)}.feedback-card b{display:block;margin-top:10px;color:#0f172a;font-size:18px}.feedback p{max-width:760px}.feedback>div:last-child{display:flex;gap:10px;flex-wrap:wrap}@media(max-width:1200px){.overview-grid{grid-template-columns:1fr}.run-grid,.json-summary,.concept-grid,.io-grid,.image-gallery{grid-template-columns:1fr}}@media(max-width:800px){.agents,.stats{grid-template-columns:1fr}.stage{grid-template-columns:42px 1fr}.stage-head,.feedback{flex-direction:column;align-items:flex-start}}
</style>


