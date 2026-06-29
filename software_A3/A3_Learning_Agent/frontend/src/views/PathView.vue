<template>
  <div class="page path-page">
    <el-card class="panel top">
      <div class="top-grid">
        <div><el-tag effect="dark">路径带资源 · 资源随路径走</el-tag><h2>{{ title }}</h2><p>以学习路径为骨架，将讲解文档、题库、思维导图、代码案例和教学视频挂载到每个阶段，形成个性化学习闭环。</p><div class="basis"><span>画像依据</span><b>知识基础 + 薄弱点 + 学习目标</b><em>{{ basis }}</em></div></div>
        <div class="stats"><div><b>{{ totalDays }}</b><span>预计时长</span></div><div><b>{{ stages.length }}</b><span>阶段数</span></div><div><b>{{ resources.length }}</b><span>资源数</span></div></div>
      </div>
      <el-progress :percentage="percent" :stroke-width="12" striped striped-flow />
      <div class="actions"><el-button type="primary" :loading="loading" @click="generateAll()">重新生成路径与资源</el-button><el-dropdown @command="pace"><el-button>调整学习节奏</el-button><template #dropdown><el-dropdown-menu><el-dropdown-item command="fast">节奏加快</el-dropdown-item><el-dropdown-item command="slow">节奏放慢</el-dropdown-item><el-dropdown-item command="practice">增加实操练习</el-dropdown-item></el-dropdown-menu></template></el-dropdown></div>
    </el-card>

    <el-card v-if="loading" class="panel"><template #header><div class="line"><span>多智能体协同生成</span><el-tag type="primary">{{ progress }}%</el-tag></div></template><el-progress :percentage="progress" striped striped-flow /><div class="agents"><div v-for="a in agents" :key="a.name" :class="['agent',{on:progress>=a.p}]"><b>{{a.short}}</b><strong>{{a.name}}</strong><span>{{a.desc}}</span></div></div></el-card>

    <el-empty v-if="!loading&&!stages.length" class="panel" description="当前画像还没有路径学习方案。请先生成画像，再点击生成路径与资源。"><el-button type="primary" @click="generateAll()">立即生成路径与资源</el-button></el-empty>

    <div v-else class="timeline">
      <div v-for="(s,i) in stages" :key="s.key" :class="['stage',state(i)]">
        <div class="dot"><span>{{i+1}}</span></div>
        <el-card class="stage-card" shadow="never">
          <template #header><div class="stage-head"><div><el-tag :type="tag(i)" effect="dark">{{ label(i) }}</el-tag><h3>第{{i+1}}阶段：{{s.title}}</h3><p>{{s.duration}}</p></div><div><el-button size="small" plain @click="toggle(i)">{{done(i)?'取消完成':'标记完成'}}</el-button><el-button size="small" text @click="toggleStage(i)">{{s.open?'收起':'展开'}}</el-button></div></div></template>
          <el-collapse-transition><div v-show="s.open" class="body"><div class="goal"><b>阶段目标</b><p>{{s.goal}}</p></div><div class="tags"><span>覆盖知识点</span><el-tag v-for="p in s.points" :key="p" size="small" type="info">{{p}}</el-tag></div><div class="section"><b>本阶段配套资源</b><span>保留个性化说明与质量审核报告</span></div><div v-if="s.resources.length" class="res-list">
                <div v-for="r in s.resources" :key="rid(r)" class="res">
                  <div class="res-head">
                    <div class="res-title">
                      <el-tag size="small" effect="dark">{{typeName(r.resource_type)}}</el-tag>
                      <strong>{{r.title}}</strong>
                      <el-tag :type="qPass(r)?'success':'warning'" size="small" plain>{{qScore(r)}}分</el-tag>
                    </div>
                    <el-button size="small" text @click="toggleResource(r)">{{resourceOpen(r)?'收起正文':'查看正文'}}</el-button>
                  </div>
                  <template v-if="isMindmap(r)">
                    <div class="mermaid-panel" :class="{collapsed:!resourceOpen(r)}">
                      <div v-if="mermaidSvgs[rid(r)]" class="mermaid-svg" v-html="mermaidSvgs[rid(r)]"></div>
                      <el-alert v-else type="warning" :closable="false" title="思维导图正在渲染，若长时间未出现请重新生成资源。" />
                    </div>
                  </template>
                  <template v-else-if="resourceJson(r)">
                    <div class="json-doc" :class="{collapsed:!resourceOpen(r)}">
                      <div class="json-summary">
                        <div><span>知识基础</span><b>{{resourceJson(r).knowledgelevel||'待观察'}}</b></div>
                        <div><span>学习目标</span><b>{{resourceJson(r).studygoal||resourceJson(r).resourcetitle||r.title}}</b></div>
                        <div><span>学习偏好</span><b>{{resourceJson(r).studystyle||'综合学习'}}</b></div>
                      </div>
                      <div v-if="resourceJson(r).profilesummary" class="json-block"><h4>画像摘要</h4><p>专业：{{resourceJson(r).profilesummary.major||'未填写'}}；薄弱点：{{resourceJson(r).profilesummary.weakpoint||'待观察'}}；目标：{{resourceJson(r).profilesummary.studygoal||resourceJson(r).studygoal}}</p></div>
                      <div v-if="resourceJson(r).studentcontext" class="json-block"><h4>当前学习位置</h4><p>{{resourceJson(r).studentcontext.currentunit}} · {{resourceJson(r).studentcontext.currentchapter}} · {{resourceJson(r).studentcontext.currentsection}} <span v-if="resourceJson(r).studentcontext.currentpage">第 {{pagesText(resourceJson(r).studentcontext.currentpage)}} 页</span></p></div>
                      <div v-if="resourceJson(r).learningresources?.length" class="json-block"><h4>课程知识库依据</h4><div v-for="item in resourceJson(r).learningresources" :key="item.chunkid||item.title" class="kb-item"><b>{{item.title}}</b><em>{{item.source}} · {{item.sectionpath}}</em><p>{{item.content}}</p></div></div>
                      <div v-if="resourceJson(r).images?.length" class="json-block"><h4>知识库配图</h4><p v-for="img in resourceJson(r).images" :key="img">{{img}}</p></div>
                    </div>
                  </template>
                  <div v-else class="res-content" :class="{collapsed:!resourceOpen(r)}">{{resourceText(r)}}</div>
                  <div v-if="resourceOpen(r)&&resourceImages(r).length" class="image-gallery">
                    <div v-for="img in resourceImages(r)" :key="img.path||img" class="kb-image">
                      <img :src="imageUrl(img.path||img)" :alt="img.caption||'知识库配图'" loading="lazy" />
                      <p>{{img.caption||img.path||img}}</p>
                    </div>
                  </div>
                  <div v-if="r.resource_type==='quiz'" class="stage-eval inline-eval">
                    <div><b>阶段测评</b><p>{{stageRecord(i)?.completed?'已完成阶段测试，可根据结果继续巩固。':'完成基础练习后，建议进入本阶段知识点测评。'}}</p><span v-if="stageRecord(i)?.completed">最近得分：{{stageRecord(i).avgScore}}分 · {{stageRecord(i).completedAt}}</span></div>
                    <el-button type="primary" plain @click="goStageEvaluation(s,i)">{{stageRecord(i)?.completed?'查看/重测':'开始阶段测试'}}</el-button>
                  </div>
                  <div class="res-meta">
                    <span>知识点：{{kps(r).join('、')||'课程核心知识'}}</span>
                    <span>{{sourceText(r)}}</span>
                  </div>
                  <div class="res-extra">
                    <el-alert class="why" type="success" :closable="false" show-icon>
                      <template #title>为什么为我这样生成</template>
                      {{r.personalization||'依据学生画像、阶段目标和知识短板生成。'}}
                    </el-alert>
                    <el-collapse>
                      <el-collapse-item title="质量审核报告" name="a">
                        <div class="audit"><el-progress :percentage="qScore(r)"/><span>{{qPass(r)?'审核通过':'建议复核'}}</span></div>
                      </el-collapse-item>
                    </el-collapse>
                  </div>
                </div>
              </div><el-empty v-else description="本阶段暂未匹配到资源，重新生成后会自动挂载。" /></div></el-collapse-transition>
        </el-card>
      </div>
    </div>

    <el-card class="panel feedback"><div><b>动态调整入口</b><p>学习反馈会交给 EvaluatorAgent，并反馈 PlannerAgent 动态调整后续阶段难度与资源侧重点。</p></div><div><el-button @click="fb('easy')">觉得太简单</el-button><el-button @click="fb('hard')">觉得太难</el-button><el-button type="primary" plain @click="fb('quiz')">根据练习结果调整</el-button></div></el-card>
  </div>
</template>

<script setup>
import { computed,nextTick,onMounted,ref,watch } from 'vue';
import { useRouter } from 'vue-router';
import mermaid from 'mermaid';
import { ElMessage } from 'element-plus';
import { pathApi,profileApi,resourceApi } from '../api';
const router=useRouter();
const paths=ref([]),resources=ref([]),profile=ref({}),integrated=ref({}),loading=ref(false),progress=ref(0),completed=ref([]),hint=ref(''),openStages=ref({}),openResources=ref({}),mermaidSvgs=ref({}),assessmentRecords=ref([]);
const agents=[{name:'PlannerAgent',short:'PL',desc:'规划学习阶段与顺序',p:20},{name:'6类资源智能体',short:'RA',desc:'生成多模态学习资源',p:55},{name:'PackagerAgent',short:'PK',desc:'资源精准挂载阶段',p:78},{name:'EvaluatorAgent',short:'EV',desc:'反馈动态调整',p:100}];
const latest=computed(()=>paths.value[0]||{}),rawStages=computed(()=>parseStages(latest.value.path_content||''));
const serverStages=computed(()=>Array.isArray(integrated.value.stages)?integrated.value.stages:[]);
const baseStages=computed(()=>serverStages.value.length?serverStages.value:(rawStages.value.length?rawStages.value:fallback()));
const title=computed(()=>integrated.value.topic||profile.value.target_course||profile.value.study_goal||baseStages.value[0]?.title||'个性化学习路径');
const basis=computed(()=>integrated.value.profile_basis?.summary||[profile.value.knowledge_base||profile.value.knowledge_level,profile.value.error_prone_points||profile.value.weak_points,profile.value.study_goal].filter(v=>v&&v!=='待进一步观察').join('；')||'等待画像生成后自动关联');
const current=computed(()=>Math.max(baseStages.value.findIndex((_,i)=>!completed.value.includes(i)),0));
const stages=computed(()=>baseStages.value.map((s,i)=>({...s,key:`${i}-${s.title}`,open:openStages.value[i]??i===current.value,resources:Array.isArray(s.resources)?s.resources:matchRes(s,i,baseStages.value.length)})));
const percent=computed(()=>Math.round(completed.value.length/Math.max(stages.value.length,1)*100));
const totalDays=computed(()=>integrated.value.total_duration||`${stages.value.reduce((n,s)=>n+Number(String(s.duration).match(/\d+/)?.[0]||0),0)||stages.value.length}天`);
function clean(t){return String(t||'').replace(/[#*_`>\-]/g,'').trim()}
function parseStages(md){return String(md||'').split(/\n(?=##\s*阶段[一二三四五六七八九十\d]+)/).filter(b=>/^##\s*阶段/.test(b.trim())).map((b,i)=>({title:clean((b.split('\n')[0]||'').replace(/^##\s*阶段[一二三四五六七八九十\d]+[：:、.．\s]*/,''))||`学习阶段${i+1}`,goal:section(b,'目标')||section(b,'学习任务')||'围绕画像短板完成本阶段学习任务。',points:points(b),duration:(b.match(/(\d+)\s*天/)?.[1]?`预计${b.match(/(\d+)\s*天/)[1]}天`:`预计${i+2}天`),raw:b}))}
function section(b,l){const m=b.match(new RegExp(`\\*\\*${l}[：:]?\\*\\*\\s*([^\\n]+)`));return m?clean(m[1]):''}
function points(b){const ks=['需求分析','总体设计','详细设计','软件测试','软件生命周期','用例图','类图','时序图','数据流图','模块划分','编码实现','软件维护'];const hit=ks.filter(k=>b.includes(k));return [...new Set(hit.length?hit:['课程核心知识'])].slice(0,5)}
function fallback(){return resources.value.length?[{title:'基础概念澄清',goal:'理解核心概念、阶段产物和输入输出关系。',points:['软件生命周期','需求分析'],duration:'预计2天',raw:''},{title:'方法关系建构',goal:'建立需求分析、总体设计、详细设计之间的顺序关系。',points:['需求分析','总体设计','详细设计'],duration:'预计3天',raw:''},{title:'练习与实操巩固',goal:'通过练习、案例和代码实操完成迁移应用。',points:['软件测试','代码实操'],duration:'预计2天',raw:''}]:[]}
function kps(r){if(Array.isArray(r.knowledge_points))return r.knowledge_points;try{return JSON.parse(r.knowledge_points||'[]')}catch{return[]}}
function score(r,text){return kps(r).reduce((n,p)=>n+(p&&text.includes(p)?5:0),0)+['需求分析','总体设计','详细设计','测试','生命周期','代码','练习'].reduce((n,k)=>n+(text.includes(k)&&`${r.title} ${r.content}`.includes(k)?2:0),0)}
function matchRes(s,i,total){const text=`${s.title} ${s.goal} ${s.points.join(' ')} ${s.raw}`;const m=resources.value.filter(r=>score(r,text)>0);const list=m.length?m:resources.value.filter((_,idx)=>total?idx%total===i:true);const order=['doc','mindmap','quiz','code','video','reading'];return [...list].sort((a,b)=>order.indexOf(a.resource_type)-order.indexOf(b.resource_type))}
function typeName(t){return({doc:'讲解文档',quiz:'基础练习题',reading:'拓展阅读',mindmap:'思维导图',code:'代码案例',video:'教学短视频'}[t]||t||'学习资源')}
function rid(r){return`${r.id||r.resource_type}-${r.title}`}
function hasModelError(t){const text=String(t||'');return /\{\s*"?success"?\s*:\s*false/i.test(text)||text.includes('调用失败')||text.includes('AppIdNoAuthError')||text.includes('NoAuth')||text.includes('anthropic/messages')}
function preview(r){const text=resourceText(r);return text.length>180?`${text.slice(0,180)}...`:text}
function extractJsonText(raw){return String(raw||'').replace(/^\s*```(?:json)?\s*/i,'').replace(/```\s*$/,'').replace(/^\s*json\s*/i,'').trim()}
function resourceJson(r){const raw=extractJsonText(r.content);const start=raw.indexOf('{'),end=raw.lastIndexOf('}');if(start<0||end<=start)return null;try{const data=JSON.parse(raw.slice(start,end+1));return data&&typeof data==='object'&&!Array.isArray(data)?data:null}catch{return null}}
function imageUrl(path){const base=import.meta.env.VITE_API_BASE_URL||'http://localhost:5000/api';return `${base}/knowledge/image?path=${encodeURIComponent(path)}`}
function resourceImages(r){const meta=r.metadata||{};const json=resourceJson(r);const found=[];const add=(img,caption='知识库配图')=>{if(!img)return;const item=typeof img==='string'?{path:img,caption}:img;if(item.path&&!found.some(x=>x.path===item.path))found.push(item)};(Array.isArray(meta.images)?meta.images:[]).forEach(add);(json?.images||[]).forEach(add);(json?.learningresources||[]).forEach(item=>(item.images||[]).forEach(img=>add(img,item.title||'知识库配图')));String(r.content||'').match(/images[\\/][^\n\r，,；;）)]+?\.(?:png|jpg|jpeg|webp|gif)/gi)?.forEach(path=>add(path,path));return found.slice(0,6)}
function cleanMindLabel(text){return String(text||'').replace(/^[\-•·]+\s*/,'').replace(/^(center\s*theme|centertheme|subtheme|caption|content|title|topic|root)\s*/i,'').replace(/[()（）{}[\]<>|`"'#：:；;]/g,' ').replace(/\s+/g,' ').trim()}
function mermaidSource(r){
  const raw=String(r.content||'').replace(/^\s*```mermaid\s*/i,'').replace(/```\s*$/,'').replace(/^\s*mermaid\s*/i,'');
  let rootTitle='软件工程知识导图';
  const nodes=[];
  let skipImages=false;
  let lastTop='';
  for(const line of raw.split('\n')){
    const trimmed=line.trim();
    if(!trimmed||/^\s*(mermaid|mindmap)\s*$/i.test(trimmed))continue;
    if(/^\s*##\s*知识库配图/.test(trimmed)){skipImages=true;continue}
    if(skipImages)continue;
    if(/images[\\/].+\.(png|jpg|jpeg|webp|gif)/i.test(trimmed))continue;
    if(/^root\(\(.*\)\)/i.test(trimmed)){
      rootTitle=cleanMindLabel(trimmed.replace(/^root\(\((.*?)\)\).*$/i,'$1'))||rootTitle;
      continue;
    }
    if(/^(caption|配图建议)/i.test(trimmed))continue;
    const isCenter=/^center\s*theme|^centertheme/i.test(trimmed);
    const isSub=/^subtheme/i.test(trimmed);
    let text=cleanMindLabel(trimmed.replace(/^[\d.]+\s*/,''));
    if(!text)continue;
    if(!nodes.length&&!isCenter&&!isSub&&text.includes('知识导图')){
      rootTitle=text;
      continue;
    }
    if(isCenter){
      rootTitle=text;
      lastTop=text;
      continue;
    }
    if(isSub){
      nodes.push({depth:lastTop?3:2,text});
      continue;
    }
    const sourceIndent=line.match(/^\s*/)?.[0].length||0;
    const depth=Math.max(2,Math.min(5,Math.floor(sourceIndent/2)+2));
    nodes.push({depth,text});
  }
  if(!nodes.length){
    nodes.push({depth:2,text:'需求分析'},{depth:3,text:'定义 目标 方法 场景 资源'},{depth:2,text:'软件测试'},{depth:3,text:'测试计划 测试过程 测试报告'});
  }
  return ['mindmap',`  root((${rootTitle}))`,...nodes.map(n=>`${'  '.repeat(n.depth)}${n.text}`)].join('\n');
}
function isMindmap(r){return r.resource_type==='mindmap'}
function escapeHtml(text){return String(text||'').replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]))}
function mindmapFallbackHtml(r){const rows=mermaidSource(r).split('\n').filter(line=>!/^\s*mindmap\s*$/i.test(line)).map(line=>{const depth=Math.min(Math.floor((line.match(/^\s*/)?.[0].length||0)/2),5);const text=escapeHtml(line.trim().replace(/^root\(\((.*?)\)\)$/,'$1'));return `<div class="mind-fallback-node depth-${depth}" style="margin-left:${depth*22}px"><span></span><b>${text}</b></div>`}).join('');return `<div class="mind-fallback">${rows}</div>`}
async function renderMindmaps(){await nextTick();const next={...mermaidSvgs.value};for(const s of stages.value){for(const r of s.resources||[]){if(!isMindmap(r))continue;const id=rid(r);if(next[id])continue;try{const source=mermaidSource(r);await mermaid.parse(source);const {svg}=await mermaid.render(`mindmap-${id.replace(/[^a-zA-Z0-9_-]/g,'-')}`,source);next[id]=svg.includes('Syntax error in text')?mindmapFallbackHtml(r):svg}catch{next[id]=mindmapFallbackHtml(r)}}}mermaidSvgs.value=next}
function pagesText(value){return Array.isArray(value)?value.join('、'):String(value||'')}
function resourceText(r){const raw=String(r.content||r.personalization||'点击学习资源页面查看完整内容。');if(hasModelError(raw))return `${typeName(r.resource_type)}已挂载到当前阶段，建议结合本阶段目标学习对应内容。`;const parsed=resourceJson(r);if(parsed)return clean(parsed.content||parsed.studygoal||parsed.resourcetitle||r.title);return clean(extractJsonText(raw))}
function resourceOpen(r){return !!openResources.value[rid(r)]}
function toggleResource(r){const id=rid(r);openResources.value={...openResources.value,[id]:!openResources.value[id]}}
function toggleStage(i){openStages.value={...openStages.value,[i]:!(openStages.value[i]??i===current.value)}}
function q(r){return r.quality||r.metadata?.quality||{}}function qScore(r){return Number(r.quality_score||q(r).total||80)}function qPass(r){return q(r).passed!==false&&qScore(r)>=75}
function sourceText(r){const n=[...new Set((r.sources||[]).map(s=>s.source||s.source_name).filter(Boolean))].length;return n?`已关联 ${n} 个课程知识库来源，并保留防幻觉审核信息。`:'建议在资源页复核课程依据。'}
function done(i){return completed.value.includes(i)}function state(i){return done(i)?'completed':i===current.value?'current':'pending'}function label(i){return{completed:'已完成',current:'当前阶段',pending:'未开始'}[state(i)]}function tag(i){return{completed:'success',current:'primary',pending:'info'}[state(i)]}
function toggle(i){completed.value=done(i)?completed.value.filter(x=>x!==i):[...completed.value,i];localStorage.setItem('a3_path_done',JSON.stringify(completed.value))}
function stageRecord(i){return assessmentRecords.value.find(item=>Number(item.stageIndex)===i)}
function loadAssessmentRecords(){try{assessmentRecords.value=JSON.parse(localStorage.getItem('a3_stage_assessment_records')||'[]')}catch{assessmentRecords.value=[]}}
function goStageEvaluation(s,i){router.push({path:'/evaluation',query:{stage:String(i),from:'path',title:s.title,points:(s.points||[]).join('、')}})}
async function loadAll(){const[ig,p,r,pf]=await Promise.all([pathApi.integrated(),pathApi.list(),resourceApi.list(),profileApi.get()]);if(ig.code===200)integrated.value=ig.data||{};if(p.code===200)paths.value=p.data||[];if(r.code===200)resources.value=(ig.code===200&&Array.isArray(ig.data?.resources))?ig.data.resources:(r.data||[]);if(pf.code===200)profile.value=pf.data||{};try{completed.value=JSON.parse(localStorage.getItem('a3_path_done')||'[]')}catch{completed.value=[]}loadAssessmentRecords()}
async function generateAll(extra=''){loading.value=true;progress.value=8;const timer=setInterval(()=>progress.value=Math.min(progress.value+7,92),800);try{const need=[profile.value.study_goal,profile.value.error_prone_points||profile.value.weak_points,hint.value,extra].filter(Boolean).join('；');const pr=await pathApi.generate({learning_need:need,adjustment:hint.value});if(pr.code!==200)throw new Error(pr.msg||'学习路径生成失败');const rr=await resourceApi.generate({learning_need:need});if(rr.code!==200)throw new Error(rr.msg||'学习资源生成失败');await loadAll();completed.value=[];localStorage.setItem('a3_path_done','[]');progress.value=100;ElMessage.success('路径与资源一体化方案生成成功')}catch(e){ElMessage.error(e?.message||'一体化生成失败')}finally{clearInterval(timer);loading.value=false}}
function pace(c){hint.value=({fast:'学习节奏加快，资源更精炼。',slow:'学习节奏放慢，增加概念解释和基础练习。',practice:'增加练习题、代码案例和应用任务比例。'}[c]||'');generateAll(hint.value)}
function fb(t){hint.value=({easy:'学生反馈太简单，请提高后续应用和实操难度。',hard:'学生反馈太难，请降低难度并增加基础讲解。',quiz:'结合练习结果调整后续路径，强化错题知识点。'}[t]||'');generateAll(hint.value)}
onMounted(()=>{mermaid.initialize({startOnLoad:false,securityLevel:'loose',theme:'base',themeVariables:{primaryColor:'#dbeafe',primaryTextColor:'#0f172a',primaryBorderColor:'#60a5fa',lineColor:'#2563eb',fontFamily:'Inter, Microsoft YaHei, sans-serif'}});loadAll()});
watch(stages,renderMindmaps,{deep:true,flush:'post'});
</script>

<style scoped>
.path-page{display:grid;gap:18px}.top{background:linear-gradient(135deg,#fff,#f8fbff)}.top-grid{display:grid;grid-template-columns:1fr 390px;gap:22px;margin-bottom:18px}.top h2{margin:14px 0 8px;font-size:28px;color:#0f172a}.top p{color:#475569;line-height:1.8}.basis{display:flex;flex-wrap:wrap;gap:10px;align-items:center;color:#64748b}.basis b{color:#1d4ed8}.basis em{font-style:normal;color:#334155}.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}.stats div{padding:18px;border:1px solid #dbeafe;border-radius:18px;background:#fff}.stats b{display:block;font-size:24px;color:#0f172a}.actions{display:flex;gap:12px;margin-top:18px}.line,.stage-head,.res-head,.feedback{display:flex;align-items:center;justify-content:space-between;gap:14px}.agents{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-top:18px}.agent{padding:14px;border:1px solid #e2e8f0;border-radius:16px;background:#fff;color:#64748b}.agent.on{border-color:#60a5fa;background:#eff6ff;color:#1d4ed8}.agent b{display:grid;width:34px;height:34px;place-items:center;margin-bottom:8px;border-radius:12px;color:#fff;background:linear-gradient(135deg,#2563eb,#06b6d4)}.agent strong,.agent span{display:block}.agent span{font-size:12px}.timeline{position:relative;display:grid;gap:20px;margin-left:26px}.timeline:before{position:absolute;top:12px;bottom:12px;left:17px;width:3px;border-radius:999px;background:#dbeafe;content:""}.stage{position:relative;display:grid;grid-template-columns:56px 1fr;gap:16px}.dot{z-index:1;display:flex;justify-content:center;padding-top:18px}.dot span{display:grid;width:38px;height:38px;place-items:center;border-radius:999px;background:#cbd5e1;color:#fff;font-weight:800}.stage.current .dot span{background:#2563eb;box-shadow:0 0 0 8px #dbeafe}.stage.completed .dot span{background:#16a34a}.stage-card{border-radius:22px}.stage.current .stage-card{border-color:#93c5fd;box-shadow:0 16px 36px rgba(37,99,235,.12)}.stage-head h3{margin:10px 0 6px;color:#0f172a}.stage-head p{margin:0;color:#64748b}.body{display:grid;gap:16px}.goal{padding:16px;border:1px solid #dbeafe;border-radius:16px;background:#f8fbff}.stage-eval{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:14px 16px;border:1px solid #bbf7d0;border-radius:16px;background:linear-gradient(135deg,#f0fdf4,#fff)}.stage-eval.inline-eval{margin-top:4px}.stage-eval b{color:#15803d}.stage-eval p{margin:6px 0;color:#334155}.stage-eval span{color:#64748b;font-size:12px}.goal b,.section b,.feedback b{color:#1d4ed8}.goal p,.feedback p{margin:8px 0 0;color:#334155;line-height:1.8}.tags{display:flex;flex-wrap:wrap;gap:8px;align-items:center;color:#64748b}.section{display:flex;justify-content:space-between;color:#64748b}.res-list{display:grid;gap:16px}.res{display:grid;gap:12px;padding:18px;border:1px solid #dbeafe;border-radius:20px;background:linear-gradient(135deg,#fff,#f8fbff);box-shadow:0 12px 28px rgba(15,23,42,.05)}.res-head{justify-content:space-between;flex-wrap:wrap;margin-bottom:2px}.res-title{display:flex;align-items:center;gap:10px;flex-wrap:wrap;min-width:0}.res-title strong{min-width:0;overflow:visible;white-space:normal;color:#0f172a;font-size:16px;line-height:1.5}.res-content,.json-doc{padding:14px 16px;border:1px solid #e2e8f0;border-radius:16px;background:#fff;color:#334155;line-height:1.9;font-size:14px;white-space:pre-wrap;word-break:break-word}.res-content.collapsed,.json-doc.collapsed{display:-webkit-box;max-height:156px;overflow:hidden;-webkit-line-clamp:5;-webkit-box-orient:vertical;color:#475569}.json-summary{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:12px;white-space:normal}.json-summary div{padding:12px;border-radius:14px;background:#f8fafc}.json-summary span{display:block;color:#64748b;font-size:12px}.json-summary b{display:block;margin-top:4px;color:#0f172a;line-height:1.5}.json-block{margin-top:12px;padding-top:12px;border-top:1px dashed #dbeafe;white-space:normal}.json-block h4{margin:0 0 8px;color:#1d4ed8}.json-block p{margin:6px 0;line-height:1.8}.kb-item{padding:10px 12px;margin-top:8px;border-radius:14px;background:#f8fbff}.kb-item b,.kb-item em{display:block}.kb-item em{margin-top:4px;color:#64748b;font-style:normal;font-size:12px}.mermaid-panel{padding:16px;border:1px solid #dbeafe;border-radius:16px;background:linear-gradient(135deg,#f8fbff,#fff);overflow:auto}.mermaid-panel.collapsed{max-height:420px}.mermaid-svg{min-width:680px}.mermaid-svg :deep(svg){width:100%;height:auto;max-width:none}.mermaid-svg :deep(.mindmap-node){cursor:pointer}.mind-fallback{display:grid;gap:8px;min-width:520px}.mind-fallback-node{display:flex;align-items:center;gap:8px;padding:8px 12px;border-radius:12px;background:#eff6ff;color:#0f172a}.mind-fallback-node span{width:9px;height:9px;border-radius:999px;background:#3b82f6}.mind-fallback-node.depth-0{font-size:18px;font-weight:800;background:#dbeafe}.mind-fallback-node.depth-1{font-weight:700}.mind-fallback-node.depth-2{background:#f8fafc}.image-gallery{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;padding:12px;border:1px dashed #bfdbfe;border-radius:18px;background:#f8fbff}.kb-image{padding:10px;border:1px solid #dbeafe;border-radius:16px;background:#fff;box-shadow:0 8px 18px rgba(15,23,42,.04)}.kb-image img{display:block;width:100%;height:190px;object-fit:contain;border-radius:12px;background:#fff}.kb-image p{margin:8px 0 0;color:#64748b;font-size:12px;line-height:1.5;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.res-meta{display:flex;flex-wrap:wrap;gap:8px;color:#64748b;font-size:12px}.res-meta span{padding:5px 9px;border-radius:999px;background:#f1f5f9}.res-extra{display:grid;grid-template-columns:minmax(0,1fr) 320px;gap:12px;align-items:start}.why{margin-bottom:0}.audit{display:grid;grid-template-columns:1fr 72px;gap:10px;align-items:center}.feedback p{max-width:760px}.feedback>div:last-child{display:flex;gap:10px;flex-wrap:wrap}@media(max-width:1200px){.top-grid{grid-template-columns:1fr}.res-extra,.agents,.json-summary,.image-gallery{grid-template-columns:1fr}}@media(max-width:800px){.agents,.stats{grid-template-columns:1fr}.stage{grid-template-columns:42px 1fr}.stage-head,.feedback{flex-direction:column;align-items:flex-start}}
</style>
