<template>
  <div class="path-tree">
    <div class="section-title">
      <div>
        <p class="aa-kicker">Learning Path</p>
        <h2 class="aa-title">个性化路径</h2>
      </div>
      <strong>68%</strong>
    </div>

    <ol class="timeline">
      <li v-for="node in pathNodes" :key="node.title" :class="node.status">
        <span></span>
        <div>
          <b>{{ node.title }}</b>
          <p>{{ node.desc }}</p>
        </div>
      </li>
    </ol>
  </div>
</template>

<script setup>
const pathNodes = [
  { title: '冯·诺依曼结构', desc: '系统结构和指令流基础', status: 'done' },
  { title: '数据表示与 ALU', desc: '补齐定点数、浮点数与运算器', status: 'done' },
  { title: 'Cache 映射方式', desc: '重点突破直接映射、组相联', status: 'active' },
  { title: '流水线冲突', desc: '结构、数据与控制相关', status: 'pending' },
  { title: '中断与 DMA', desc: '理解 I/O 协作机制', status: 'pending' }
]
</script>

<style scoped>
.path-tree {
  padding: 18px;
}

.section-title {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
}

.section-title strong {
  color: var(--aa-green);
  font-size: 22px;
}

.timeline {
  list-style: none;
  padding: 8px 0 0;
  margin: 0;
}

.timeline li {
  display: grid;
  grid-template-columns: 22px 1fr;
  gap: 10px;
  position: relative;
  padding: 13px 0;
}

.timeline li:not(:last-child)::after {
  content: "";
  position: absolute;
  left: 8px;
  top: 33px;
  width: 2px;
  height: calc(100% - 24px);
  background: rgba(89, 128, 176, 0.16);
}

.timeline li > span {
  width: 18px;
  height: 18px;
  margin-top: 2px;
  border-radius: 50%;
  background: rgba(146, 168, 186, 0.2);
  border: 2px solid rgba(146, 168, 186, 0.38);
  z-index: 1;
}

.timeline li.done > span {
  background: var(--aa-green);
  border-color: var(--aa-green);
  box-shadow: 0 0 18px rgba(39, 201, 148, 0.34);
}

.timeline li.active > span {
  background: var(--aa-cyan);
  border-color: var(--aa-cyan);
  box-shadow: 0 0 20px rgba(25, 191, 234, 0.42);
}

.timeline b {
  display: block;
  color: var(--aa-text);
  font-size: 14px;
  margin-bottom: 4px;
}

.timeline p {
  color: var(--aa-muted);
  font-size: 12px;
  line-height: 1.5;
  margin: 0;
}
</style>
