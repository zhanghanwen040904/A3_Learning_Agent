<template>
  <div class="quiz-card">
    <div class="question">{{ quiz.question }}</div>
    <el-radio-group v-model="selected" class="options" v-if="quiz.options">
      <el-radio v-for="(opt, i) in quiz.options" :key="i" :value="i" :disabled="submitted">
        {{ opt }}
      </el-radio>
    </el-radio-group>
    <div class="actions" v-if="!submitted">
      <el-button type="primary" size="small" @click="submit" :disabled="selected === null">
        提交
      </el-button>
    </div>
    <div v-if="submitted" :class="['result', isCorrect ? 'correct' : 'wrong']">
      <strong>{{ isCorrect ? '回答正确！' : '回答错误' }}</strong>
      <div class="explanation">{{ quiz.explanation }}</div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({ quiz: { type: Object, default: () => ({}) } })
const selected = ref(null)
const submitted = ref(false)

const isCorrect = computed(() => selected.value === props.quiz.answer)

function submit() {
  submitted.value = true
}
</script>

<style scoped>
.quiz-card { padding: 4px; }
.question { font-weight: 600; margin-bottom: 12px; }
.options { display: flex; flex-direction: column; gap: 8px; }
.actions { margin-top: 12px; }
.result { margin-top: 12px; padding: 10px; border-radius: 4px; }
.result.correct { background: #f0f9eb; color: #67c23a; }
.result.wrong { background: #fef0f0; color: #f56c6c; }
.explanation { margin-top: 6px; font-size: 13px; }
</style>
