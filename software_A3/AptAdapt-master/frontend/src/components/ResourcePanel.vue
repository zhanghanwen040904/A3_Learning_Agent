<template>
  <div class="resource-panel">
    <div class="panel-head">
      <div>
        <p class="aa-kicker">Resource Factory</p>
        <h2 class="aa-title">生成资源</h2>
      </div>
      <span>{{ resources.length }} 类</span>
    </div>

    <div class="resource-list">
      <article
        v-for="(res, index) in resources"
        :key="res.type"
        :class="['resource-card', { active: activeIndex === index }]"
        @click="activeIndex = index"
      >
        <div class="card-icon">{{ iconLabel(res.type) }}</div>
        <div>
          <h3>{{ res.title }}</h3>
          <p>{{ res.summary }}</p>
        </div>
      </article>
    </div>

    <div class="resource-detail">
      <MarkdownViewer v-if="activeResource.type === 'doc' || activeResource.type === 'video_script'" :content="activeResource.content" />
      <MindMapViewer v-else-if="activeResource.type === 'mindmap'" :data="activeResource.content" />
      <QuizCard v-else-if="activeResource.type === 'quiz'" :quiz="activeResource.content" />
      <CodeBlock v-else-if="activeResource.type === 'code'" :code="activeResource.content" />
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import MarkdownViewer from './MarkdownViewer.vue'
import MindMapViewer from './MindMapViewer.vue'
import QuizCard from './QuizCard.vue'
import CodeBlock from './CodeBlock.vue'

const activeIndex = ref(0)
const resources = ref([
  {
    type: 'doc',
    title: '个性化讲解文档',
    summary: '用生活类比解释三种 Cache 映射方式，并补充地址划分公式。',
    content: `## Cache 映射方式个性化讲解

Cache 映射方式解决的问题是：**主存块应该放到 Cache 的哪个位置**。

| 映射方式 | 特点 | 易错点 |
| --- | --- | --- |
| 直接映射 | 每个主存块只能进入固定 Cache 行 | 冲突率高 |
| 全相联映射 | 主存块可进入任意 Cache 行 | 查找和替换复杂 |
| 组相联映射 | 折中方案，先找组再找行 | 组号计算容易错 |

建议先掌握公式：Cache 行号 = 主存块号 mod Cache 行数。`
  },
  {
    type: 'mindmap',
    title: '知识点思维导图',
    summary: '结构化展示先修概念、映射方式与易错点。',
    content: `flowchart TD
  A[Cache 映射方式] --> B[直接映射]
  A --> C[全相联映射]
  A --> D[组相联映射]
  B --> E[行号 = 块号 mod 行数]
  C --> F[替换策略复杂]
  D --> G[性能与成本折中]`
  },
  {
    type: 'quiz',
    title: '分层练习题',
    summary: '基础题 3 道，进阶计算题 2 道，附解析。',
    content: {
      question: '某 Cache 采用直接映射，主存块号为 29，Cache 共有 8 行，该主存块映射到第几行？',
      options: ['1', '5', '6', '7'],
      answer: 1,
      explanation: '29 mod 8 = 5，因此映射到第 5 行。'
    }
  },
  {
    type: 'code',
    title: '代码/地址示例',
    summary: '演示主存地址如何映射到 Cache 行与组。',
    content: {
      language: 'c',
      source: 'int cache_line(int block_no, int line_count) {\\n  return block_no % line_count;\\n}',
      explanation: '直接映射中，主存块号对 Cache 行数取模即可得到映射行号。'
    }
  },
  {
    type: 'video_script',
    title: '视频脚本',
    summary: '60 秒动画分镜，适合录入演示视频。',
    content: `## 60 秒讲解分镜

1. 0-10s：展示主存块排队进入 Cache。
2. 10-25s：直接映射演示固定行号。
3. 25-40s：全相联映射展示任意位置。
4. 40-55s：组相联映射展示分组折中。
5. 55-60s：总结三者区别和适用场景。`
  }
])

const activeResource = computed(() => resources.value[activeIndex.value])

function iconLabel(type) {
  const map = { doc: 'DOC', mindmap: 'MAP', quiz: 'QZ', code: 'ASM', video_script: 'VID' }
  return map[type] || 'AI'
}
</script>

<style scoped>
.resource-panel {
  display: grid;
  gap: 14px;
}

.panel-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.panel-head span {
  color: var(--aa-muted);
  font-size: 14px;
}

.resource-list {
  display: grid;
  gap: 10px;
}

.resource-card {
  display: grid;
  grid-template-columns: 48px 1fr;
  gap: 12px;
  align-items: start;
  padding: 13px;
  border-radius: 8px;
  border: 1px solid rgba(89, 128, 176, 0.15);
  background: rgba(255, 255, 255, 0.64);
  cursor: pointer;
  transition: transform 0.2s ease, border-color 0.2s ease, background 0.2s ease;
}

.resource-card:hover,
.resource-card.active {
  transform: translateY(-2px);
  border-color: rgba(25, 191, 234, 0.38);
  background: rgba(234, 251, 255, 0.92);
}

.card-icon {
  width: 48px;
  height: 48px;
  display: grid;
  place-items: center;
  border-radius: 8px;
  color: var(--aa-cyan);
  font-size: 12px;
  font-weight: 900;
  background: rgba(226, 249, 255, 0.9);
  border: 1px solid rgba(64, 184, 230, 0.2);
}

.resource-card h3 {
  margin: 0 0 6px;
  color: var(--aa-text);
  font-size: 14px;
}

.resource-card p {
  margin: 0;
  color: var(--aa-muted);
  font-size: 12px;
  line-height: 1.55;
}

.resource-detail {
  max-height: 360px;
  overflow: auto;
  padding: 14px;
  border-radius: 8px;
  border: 1px solid rgba(89, 128, 176, 0.12);
  background: rgba(255, 255, 255, 0.68);
}
</style>
