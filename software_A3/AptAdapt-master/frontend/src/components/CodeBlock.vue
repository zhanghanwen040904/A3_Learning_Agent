<template>
  <div class="code-block">
    <div class="code-header">
      <span class="lang">{{ code.language || 'verilog' }}</span>
      <el-button size="small" text @click="copy">复制</el-button>
    </div>
    <pre><code ref="codeEl" class="hljs">{{ code.source }}</code></pre>
    <div v-if="code.explanation" class="code-explanation">{{ code.explanation }}</div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import hljs from 'highlight.js/lib/core'
import verilog from 'highlight.js/lib/languages/verilog'
import asm from 'highlight.js/lib/languages/x86asm'
import python from 'highlight.js/lib/languages/python'
import c from 'highlight.js/lib/languages/c'
import 'highlight.js/styles/github.css'

hljs.registerLanguage('verilog', verilog)
hljs.registerLanguage('x86asm', asm)
hljs.registerLanguage('python', python)
hljs.registerLanguage('c', c)

const props = defineProps({
  code: { type: Object, default: () => ({ language: '', source: '', explanation: '' }) }
})
const codeEl = ref(null)

function highlight() {
  if (codeEl.value) {
    codeEl.value.removeAttribute('data-highlighted')
    codeEl.value.className = `hljs language-${props.code.language || 'verilog'}`
    hljs.highlightElement(codeEl.value)
  }
}

onMounted(highlight)
watch(() => props.code.source, highlight)

function copy() {
  navigator.clipboard.writeText(props.code.source || '')
}
</script>

<style scoped>
.code-block { border: 1px solid #e4e7ed; border-radius: 4px; overflow: hidden; }
.code-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 12px;
  background: #fafafa;
  border-bottom: 1px solid #e4e7ed;
  font-size: 13px;
}
pre { padding: 12px; overflow-x: auto; margin: 0; }
code { font-family: 'Fira Code', monospace; font-size: 13px; }
.code-explanation { padding: 10px 12px; border-top: 1px solid #e4e7ed; font-size: 13px; color: #606266; }
</style>
