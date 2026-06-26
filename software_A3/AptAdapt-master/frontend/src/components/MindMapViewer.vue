<template>
  <div class="mindmap-viewer">
    <div ref="mermaidEl"></div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import mermaid from 'mermaid'

const props = defineProps({ data: { type: String, default: '' } })
const mermaidEl = ref(null)

mermaid.initialize({ startOnLoad: true, theme: 'default' })

async function render() {
  if (!props.data || !mermaidEl.value) return
  const { svg } = await mermaid.render('mindmap-svg', props.data)
  mermaidEl.value.innerHTML = svg
}

onMounted(render)
watch(() => props.data, render)
</script>

<style scoped>
.mindmap-viewer { min-height: 200px; overflow: auto; }
</style>
