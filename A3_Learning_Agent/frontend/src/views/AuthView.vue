<template>
  <div class="auth-shell">
    <section class="hero-panel">
      <div class="brand-row"><div class="brand-mark"><span class="logo-link link-a"></span><span class="logo-link link-b"></span><span class="logo-dot dot-a"></span><span class="logo-dot dot-b"></span><span class="logo-dot dot-c"></span><i>M</i></div><div><h1>MultiTutor</h1><p>学习智能体</p></div></div>
      <div class="hero-badge"><span></span>AI 驱动的个性化学习伙伴</div>
      <div class="hero-main">
        <h2>让学习更<span>高效</span><br />让成长更<span>可见</span></h2>
        <p>基于学习画像、多智能体协同与课程知识库，为你规划个性化学习路径，生成知识讲解、思维导图、练习评估与拓展材料。</p>
      </div><div class="visual-stage" aria-hidden="true">
        <div class="orbit orbit-one"></div><div class="orbit orbit-two"></div>
        <div class="agent-line line-a"></div><div class="agent-line line-b"></div><div class="agent-line line-c"></div><div class="agent-line line-d"></div>
        <div class="agent-core"><strong>AI</strong><small>Learning Agent</small></div>
        <div class="agent-node node-planner">Planner</div><div class="agent-node node-teacher">Teacher</div>
        <div class="agent-node node-resource">Resource</div><div class="agent-node node-eval">Evaluation</div>
      </div>
      <div class="auth-footer"><span>© 2026 MultiTutor 学习智能体</span><span>画像驱动 · 多智能体协同 · 知识库增强</span></div>
    </section>

    <section class="login-panel">
      <div class="login-card">
        <div class="card-header"><span class="card-kicker">欢迎回来</span><h3>登录你的学习空间</h3><p>继续个性化学习路径与知识探索</p></div>
        <div class="login-divider" aria-hidden="true"></div>
        <el-form :model="form" label-position="top" class="login-form" @keyup.enter="login">
          <el-form-item label="用户名"><el-input v-model="form.username" size="large" placeholder="请输入用户名" :prefix-icon="User" /></el-form-item>
          <el-form-item label="密码"><el-input v-model="form.password" size="large" type="password" show-password placeholder="请输入密码" :prefix-icon="Lock" /></el-form-item>
          <el-button class="login-button" type="primary" size="large" :loading="loading" @click="login">登录系统</el-button>
        </el-form>
        <div class="register-line"><span>还没有账号？</span><el-button link type="primary" @click="registerVisible = true">立即注册</el-button></div>
      </div>
    </section>

    <el-dialog v-model="registerVisible" title="创建新账号" width="420px" align-center>
      <el-form :model="registerForm" label-position="top">
        <el-form-item label="用户名"><el-input v-model="registerForm.username" size="large" placeholder="至少2位字符" :prefix-icon="User" /></el-form-item>
        <el-form-item label="密码"><el-input v-model="registerForm.password" size="large" type="password" show-password placeholder="至少6位字符" :prefix-icon="Lock" /></el-form-item>
        <el-form-item label="确认密码"><el-input v-model="registerForm.confirmPassword" size="large" type="password" show-password placeholder="请再次输入密码" :prefix-icon="Lock" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="registerVisible = false">取消</el-button><el-button type="primary" :loading="registerLoading" @click="register">注册并登录</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup>
import { reactive, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { Lock, User } from "@element-plus/icons-vue";
import { authApi } from "../api";
const router = useRouter();
const route = useRoute();
const loading = ref(false);
const registerLoading = ref(false);
const registerVisible = ref(false);
const form = reactive({ username: "", password: "" });
const registerForm = reactive({ username: "", password: "", confirmPassword: "" });
function saveSession(data) { localStorage.setItem("token", data.token); localStorage.setItem("user", JSON.stringify({ id: data.id, username: data.username, profile_completed: data.profile_completed })); }
function validateLoginForm(target) { if (!target.username.trim()) { ElMessage.warning("请输入用户名"); return false; } if (!target.password) { ElMessage.warning("请输入密码"); return false; } return true; }
async function login() { if (!validateLoginForm(form)) return; loading.value = true; try { const res = await authApi.login(form); if (res.code === 200) { saveSession(res.data); if (res.data.profile_completed) localStorage.removeItem("a3_need_complete_user_info"); ElMessage.success("登录成功"); router.push(route.query.redirect || "/profile"); } else { ElMessage.error(res.msg || "用户名或密码错误"); } } finally { loading.value = false; } }
async function register() { if (!validateLoginForm(registerForm)) return; if (registerForm.password.length < 6) { ElMessage.warning("密码至少6位"); return; } if (registerForm.password !== registerForm.confirmPassword) { ElMessage.warning("两次密码不一致"); return; } registerLoading.value = true; try { const res = await authApi.register({ username: registerForm.username, password: registerForm.password }); if (res.code === 200) { saveSession(res.data); localStorage.setItem("a3_need_complete_user_info", "1"); ElMessage.success("注册成功，请完善个人信息"); registerVisible.value = false; router.push("/profile"); } else { ElMessage.error(res.msg || "注册失败"); } } finally { registerLoading.value = false; } }
</script>

<style scoped>
.auth-shell{--p:#4f7bff;--s:#6c63ff;--a:#21d4fd;position:relative;display:grid;grid-template-columns:minmax(0,55%) minmax(420px,45%);min-height:100vh;overflow:hidden;background:radial-gradient(circle at 16% 12%,rgba(33,212,253,.18),transparent 26%),radial-gradient(circle at 72% 8%,rgba(108,99,255,.18),transparent 28%),linear-gradient(135deg,#f6f9ff 0%,#eef6ff 48%,#fbfcff 100%);color:#0f172a}.auth-shell:before,.auth-shell:after{position:absolute;content:"";border-radius:999px;filter:blur(20px);opacity:.6;animation:bgFloat 9s ease-in-out infinite alternate}.auth-shell:before{left:-120px;top:90px;width:360px;height:360px;background:rgba(33,212,253,.2)}.auth-shell:after{right:8%;top:-130px;width:430px;height:430px;background:rgba(108,99,255,.18)}@keyframes bgFloat{to{transform:translate(28px,18px) scale(1.05)}}
.hero-panel{position:relative;display:grid;grid-template-rows:auto auto 1fr auto;min-height:100vh;padding:28px clamp(34px,4vw,58px) 20px}.brand-row,.hero-badge,.hero-main,.visual-stage,.auth-footer{position:relative;z-index:1}.brand-row{display:flex;align-items:center;gap:14px}.brand-mark{position:relative;display:grid;width:48px;height:48px;place-items:center;border-radius:16px;background:linear-gradient(135deg,var(--p),var(--a) 52%,var(--s));box-shadow:0 14px 28px rgba(79,123,255,.26);animation:logoFloat 4s ease-in-out infinite}.brand-mark i{z-index:2;color:#fff;font-size:12px;font-style:normal;font-weight:900;letter-spacing:-.04em}.logo-link{position:absolute;height:2px;border-radius:999px;background:rgba(255,255,255,.58);transform-origin:left}.link-a{left:14px;top:18px;width:22px;transform:rotate(30deg)}.link-b{left:16px;bottom:16px;width:22px;transform:rotate(-28deg)}.logo-dot{position:absolute;z-index:3;width:7px;height:7px;border-radius:50%;background:#fff;box-shadow:0 0 0 3px rgba(255,255,255,.16)}.dot-a{left:12px;top:14px}.dot-b{right:11px;top:25px}.dot-c{left:16px;bottom:12px}@keyframes logoFloat{50%{transform:translateY(-4px)}}.brand-row h1{margin:0;font-size:25px;font-weight:800;letter-spacing:-.03em}.brand-row p{margin:4px 0 0;color:#64748b;font-size:12px;font-weight:600}.hero-badge{justify-self:start;display:inline-flex;align-items:center;gap:8px;margin-top:22px;padding:7px 14px;border:1px solid rgba(79,123,255,.18);border-radius:999px;background:rgba(255,255,255,.62);color:#385bea;font-size:13px;font-weight:700;backdrop-filter:blur(18px);box-shadow:0 14px 32px rgba(79,123,255,.09)}.hero-badge span{width:8px;height:8px;border-radius:50%;background:#22c55e;box-shadow:0 0 0 5px rgba(34,197,94,.12)}
.hero-main{align-self:center;width:min(500px,52%);padding-bottom:18px}.hero-main h2{margin:0;font-size:clamp(38px,4.1vw,58px);font-weight:800;line-height:1.08;letter-spacing:-.065em}.hero-main h2 span{background:linear-gradient(90deg,var(--p),var(--s),var(--a));-webkit-background-clip:text;background-clip:text;color:transparent}.hero-main p{max-width:540px;margin:16px 0 0;color:#475569;font-size:14px;font-weight:500;line-height:1.65}.feature-list{display:grid;gap:10px;width:min(410px,100%);margin-top:18px}.feature-card{display:flex;align-items:center;gap:14px;padding:11px 14px;border:1px solid rgba(255,255,255,.78);border-radius:16px;background:rgba(255,255,255,.66);box-shadow:0 16px 36px rgba(79,123,255,.08);backdrop-filter:blur(18px);transition:.22s ease}.feature-card:hover{transform:translateY(-4px);box-shadow:0 24px 48px rgba(79,123,255,.16)}.feature-card b{display:grid;width:36px;height:36px;place-items:center;border-radius:15px;background:linear-gradient(135deg,#eef5ff,#fff);font-size:17px;box-shadow:inset 0 0 0 1px rgba(79,123,255,.1)}.feature-card strong{display:block;font-size:14px;font-weight:800}.feature-card small{display:block;margin-top:4px;color:#64748b;font-size:12px;font-weight:500}
.visual-stage{position:absolute;right:clamp(20px,4.2vw,64px);top:50%;width:300px;height:260px;transform:translateY(-50%)}.orbit{position:absolute;left:50%;top:50%;border:1px solid rgba(79,123,255,.14);border-radius:50%;transform:translate(-50%,-50%) rotate(-14deg)}.orbit-one{width:244px;height:170px}.orbit-two{width:178px;height:124px}.agent-line{position:absolute;left:50%;top:50%;height:2px;background:linear-gradient(90deg,rgba(79,123,255,.08),rgba(33,212,253,.55));transform-origin:left}.line-a{width:126px;transform:rotate(-34deg)}.line-b{width:128px;transform:rotate(34deg)}.line-c{width:118px;transform:rotate(145deg)}.line-d{width:118px;transform:rotate(-145deg)}.agent-core{position:absolute;left:50%;top:50%;display:grid;width:96px;height:96px;place-items:center;transform:translate(-50%,-50%);border:1px solid rgba(255,255,255,.86);border-radius:26px;background:linear-gradient(135deg,rgba(79,123,255,.96),rgba(33,212,253,.94) 55%,rgba(108,99,255,.96));color:#fff;box-shadow:0 32px 72px rgba(79,123,255,.25)}.agent-core strong{font-size:32px;font-weight:900}.agent-core small{margin-top:-20px;text-align:center;font-size:11px;font-weight:700;opacity:.86}.agent-node{position:absolute;padding:7px 10px;border:1px solid rgba(255,255,255,.82);border-radius:16px;background:rgba(255,255,255,.72);color:#385bea;font-size:11px;font-weight:800;box-shadow:0 18px 40px rgba(79,123,255,.12);backdrop-filter:blur(18px)}.node-planner{left:10px;top:48px}.node-teacher{right:10px;top:46px}.node-resource{left:14px;bottom:48px}.node-eval{right:12px;bottom:50px}.auth-footer{display:flex;justify-content:space-between;gap:18px;color:#64748b;font-size:12px;font-weight:500}
.login-panel{position:relative;z-index:1;display:grid;min-height:100vh;place-items:center;padding:26px clamp(24px,3.4vw,54px) 26px 24px}.login-card{width:min(430px,100%);padding:34px 32px 28px;border:1px solid rgba(255,255,255,.72);border-radius:24px;background:rgba(255,255,255,.66);box-shadow:0 34px 86px rgba(15,23,42,.14),inset 0 1px 0 rgba(255,255,255,.86);backdrop-filter:blur(24px)}.card-header{text-align:center}.card-header h3{margin:0;font-size:28px;font-weight:800;letter-spacing:-.04em}.card-header p{margin:10px 0 0;color:#64748b;font-size:14px;font-weight:500}.login-divider{height:2px;margin:22px 0 20px;border-radius:999px;background:linear-gradient(90deg,var(--p),var(--a))}.login-form :deep(.el-form-item){margin-bottom:16px}.login-form :deep(.el-form-item__label){margin-bottom:8px;color:#1e293b;font-size:13px;font-weight:700}.login-form :deep(.el-input__wrapper){min-height:46px;border-radius:14px;background:rgba(255,255,255,.78);box-shadow:0 0 0 1px rgba(148,163,184,.22) inset}.login-form :deep(.el-input__wrapper.is-focus){box-shadow:0 0 0 1px var(--p) inset,0 0 0 4px rgba(79,123,255,.12)}.form-options{display:flex;align-items:center;justify-content:space-between;margin:-2px 0 22px}.form-options :deep(.el-checkbox__label),.text-button,.register-line{font-size:12px;font-weight:500}.text-button{border:0;background:transparent;color:#4f7bff;cursor:pointer}.login-button{width:100%;height:46px;border:0;border-radius:14px;background:linear-gradient(90deg,var(--p),var(--s),var(--a));font-size:15px;font-weight:600;box-shadow:0 18px 36px rgba(79,123,255,.28);transition:.2s ease}.login-button:hover{transform:translateY(-2px) scale(1.015);box-shadow:0 24px 44px rgba(79,123,255,.34)}.agent-status{display:grid;grid-template-columns:1fr 1fr;gap:9px;margin-top:14px;padding:12px;border:1px solid rgba(79,123,255,.1);border-radius:16px;background:rgba(246,249,255,.68)}.agent-status div{display:flex;align-items:center;gap:7px;color:#475569;font-size:12px;font-weight:600}.agent-status span{width:7px;height:7px;border-radius:50%;background:#22c55e;box-shadow:0 0 0 4px rgba(34,197,94,.12)}.register-line{display:flex;align-items:center;justify-content:center;gap:5px;margin-top:22px;color:#64748b}
/* Balanced desktop composition */
.auth-shell{--p:#3467f6;--s:#5f5cf5;--a:#18bfe9;grid-template-columns:minmax(680px,3fr) minmax(480px,2fr);background:radial-gradient(circle at 14% 14%,rgba(56,189,248,.17),transparent 28%),radial-gradient(circle at 66% 10%,rgba(99,102,241,.17),transparent 30%),linear-gradient(135deg,#f8fbff 0%,#eef5ff 52%,#fafcff 100%)}
.hero-panel{padding:clamp(34px,4vh,56px) clamp(42px,4.5vw,82px) 28px}
.brand-row{gap:16px}.brand-mark{width:58px;height:58px;border-radius:18px}.brand-mark i{font-size:25px}.logo-link,.logo-dot{display:none}.brand-row h1{font-size:32px}.brand-row p{font-size:15px}.hero-badge{margin-top:30px;padding:9px 16px;font-size:14px}
.hero-main{width:min(520px,48%);padding-bottom:24px}.hero-main h2{font-size:clamp(48px,4.6vw,76px);line-height:1.04}.hero-main p{max-width:500px;margin-top:26px;font-size:17px;line-height:1.9}
.visual-stage{right:clamp(30px,4.2vw,76px);top:52%;width:clamp(320px,27vw,430px);height:390px}.orbit-one{width:350px;height:250px}.orbit-two{width:260px;height:184px}.agent-core{width:136px;height:136px;border:8px solid rgba(255,255,255,.62);border-radius:38px}.agent-core strong{font-size:44px}.agent-core small{margin-top:-28px;font-size:12px}.node-planner{left:4px;top:72px}.node-teacher{right:4px;top:70px}.node-resource{left:8px;bottom:72px}.node-eval{right:4px;bottom:74px}.agent-node{padding:9px 13px;font-size:12px}
.login-panel{padding:38px clamp(38px,4vw,78px) 38px 20px}.login-card{width:min(500px,100%);padding:52px 48px 42px;border-radius:32px;background:rgba(255,255,255,.78)}.card-header{text-align:left}.card-kicker{display:block;margin-bottom:12px;color:var(--p);font-size:14px;font-weight:800}.card-header h3{font-size:38px;line-height:1.18}.card-header p{margin-top:12px;font-size:16px}.login-divider{margin:30px 0 28px}.login-form :deep(.el-form-item){margin-bottom:22px}.login-form :deep(.el-form-item__label){font-size:14px}.login-form :deep(.el-input__wrapper){min-height:56px;border-radius:16px}.login-button{height:56px;margin-top:8px;border-radius:16px;font-size:17px}.register-line{margin-top:28px;font-size:14px}.auth-footer{font-size:13px}
@media(max-width:1500px){.auth-shell{grid-template-columns:minmax(620px,58%) minmax(460px,42%)}.hero-panel{padding-left:48px;padding-right:48px}.hero-main{width:48%}.hero-main h2{font-size:54px}.hero-main p{font-size:15px}.visual-stage{right:24px;width:310px}.orbit-one{width:290px;height:210px}.orbit-two{width:220px;height:155px}.agent-core{width:118px;height:118px}.login-panel{padding-right:34px}.login-card{padding:44px 40px 36px}}
@media(max-width:1120px){.auth-shell{grid-template-columns:1fr}.hero-panel{display:none}.login-panel{min-height:100vh;padding:28px 20px}.login-card{width:min(500px,100%)}}
@media(max-width:560px){.login-card{padding:34px 22px 28px;border-radius:24px}.card-header h3{font-size:30px}.card-header p{font-size:14px}}
</style>



