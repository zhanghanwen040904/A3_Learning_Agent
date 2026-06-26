<template>
  <div class="markdown-body" v-html="rendered"></div>
</template>

<script setup>
import { computed } from 'vue'
import markdownit from 'markdown-it'

const props = defineProps({ content: { type: String, default: '' } })
const md = markdownit({ html: true, linkify: true })
const rendered = computed(() => md.render(props.content))
</script>

<style scoped>
.markdown-body { line-height: 1.8; }
.markdown-body :deep(pre) { background: #f5f7fa; padding: 12px; border-radius: 4px; overflow-x: auto; }
.markdown-body :deep(code) { font-family: 'Fira Code', monospace; font-size: 13px; }
.markdown-body :deep(table) { border-collapse: collapse; width: 100%; }
.markdown-body :deep(th), .markdown-body :deep(td) { border: 1px solid #e4e7ed; padding: 6px 10px; }
</style>
