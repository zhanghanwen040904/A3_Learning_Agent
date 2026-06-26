<template>
  <div class="evaluation-panel">
    <div class="panel-head">
      <div>
        <p class="aa-kicker">Evaluation</p>
        <h2 class="aa-title">学习效果</h2>
      </div>
      <span>动态更新</span>
    </div>
    <div ref="radarEl" class="chart"></div>
    <div class="metric-list">
      <div>
        <span>资源完成度</span>
        <b>76%</b>
      </div>
      <div>
        <span>练习正确率</span>
        <b>84%</b>
      </div>
      <div>
        <span>薄弱点减少</span>
        <b>3 项</b>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import * as echarts from 'echarts'

const radarEl = ref(null)

onMounted(() => {
  const radar = echarts.init(radarEl.value)
  radar.setOption({
    color: ['#19bfea'],
    radar: {
      radius: '64%',
      splitNumber: 4,
      axisName: { color: '#60788e' },
      splitLine: { lineStyle: { color: 'rgba(89,128,176,.16)' } },
      splitArea: { areaStyle: { color: ['rgba(25,191,234,.04)', 'rgba(39,201,148,.04)'] } },
      axisLine: { lineStyle: { color: 'rgba(89,128,176,.16)' } },
      indicator: [
        { name: 'Cache', max: 100 },
        { name: '流水线', max: 100 },
        { name: '中断', max: 100 },
        { name: 'ALU', max: 100 },
        { name: '指令', max: 100 }
      ]
    },
    series: [{
      type: 'radar',
      areaStyle: { opacity: 0.55 },
      data: [{ value: [82, 64, 58, 90, 74], name: '掌握度' }]
    }]
  })
})
</script>

<style scoped>
.evaluation-panel {
  padding: 18px;
}

.panel-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
}

.panel-head span {
  padding: 6px 10px;
  border-radius: 8px;
  color: #1b6c89;
  background: rgba(229, 249, 255, 0.78);
  border: 1px solid rgba(64, 184, 230, 0.18);
  font-size: 12px;
}

.chart {
  width: 100%;
  height: 220px;
}

.metric-list {
  display: grid;
  gap: 10px;
}

.metric-list div {
  display: flex;
  justify-content: space-between;
  padding: 10px 0;
  border-top: 1px solid rgba(89, 128, 176, 0.12);
}

.metric-list span {
  color: var(--aa-muted);
  font-size: 13px;
}

.metric-list b {
  color: var(--aa-green);
}
</style>
