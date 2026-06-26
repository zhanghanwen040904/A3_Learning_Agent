<template>
  <div class="agent-status-bar">
    <div v-for="agent in agents" :key="agent.name" class="agent-card">
      <span :class="['dot', agent.status]"></span>
      <div>
        <b>{{ agent.name }}</b>
        <p>{{ agent.label }}</p>
      </div>
    </div>
  </div>
</template>

<script setup>
const agents = [
  { name: 'Profile Agent', status: 'done', label: '画像已更新' },
  { name: 'RAG Agent', status: 'running', label: '检索 Cache 片段' },
  { name: 'MindMap Agent', status: 'running', label: '生成导图' },
  { name: 'Quiz Agent', status: 'idle', label: '等待调用' },
  { name: 'Reviewer Agent', status: 'idle', label: '排队审核' }
]
</script>

<style scoped>
.agent-status-bar {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.agent-card {
  min-height: 68px;
  padding: 12px;
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 10px;
  align-items: start;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.62);
  border: 1px solid rgba(89, 128, 176, 0.15);
}

.dot {
  display: block;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  margin-top: 4px;
  background: rgba(146, 168, 186, 0.5);
}

.dot.running {
  background: var(--aa-cyan);
  box-shadow: 0 0 16px rgba(25, 191, 234, 0.42);
  animation: pulse 1.2s infinite;
}

.dot.done {
  background: var(--aa-green);
  box-shadow: 0 0 16px rgba(39, 201, 148, 0.36);
}

.agent-card b {
  display: block;
  color: var(--aa-text);
  font-size: 13px;
  line-height: 1.25;
}

.agent-card p {
  margin: 4px 0 0;
  color: var(--aa-muted);
  font-size: 12px;
}

@keyframes pulse {
  0%, 100% { transform: scale(1); opacity: 1; }
  50% { transform: scale(1.35); opacity: 0.45; }
}

@media (max-width: 900px) {
  .agent-status-bar {
    grid-template-columns: 1fr;
  }
}
</style>
