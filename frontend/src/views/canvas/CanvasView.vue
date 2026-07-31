<template>
  <div class="canvas-view">
    <el-card>
      <template #header>
        <div class="card-header"><span>Canvas 可视化展示</span><el-button type="primary" @click="presentToCanvas"><el-icon><Monitor /></el-icon> 投屏</el-button></div>
      </template>
      <div class="chart-grid">
        <div class="chart-item"><h4>设备状态分布</h4><div ref="pieChartRef" class="chart-container"></div></div>
        <div class="chart-item"><h4>告警趋势</h4><div ref="lineChartRef" class="chart-container"></div></div>
        <div class="chart-item full-width"><h4>机柜容量分布</h4><div ref="barChartRef" class="chart-container"></div></div>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from "vue"
import { ElMessage } from "element-plus"
import { Monitor } from "@element-plus/icons-vue"
import * as echarts from "echarts"

const pieChartRef = ref<HTMLElement>()
const lineChartRef = ref<HTMLElement>()
const barChartRef = ref<HTMLElement>()
let pieChart: echarts.ECharts | null = null, lineChart: echarts.ECharts | null = null, barChart: echarts.ECharts | null = null

function initCharts() {
  if (pieChartRef.value) {
    pieChart = echarts.init(pieChartRef.value)
    pieChart.setOption({ tooltip: { trigger: "item" }, legend: { bottom: 0 }, series: [{ type: "pie", radius: ["40%", "70%"], data: [{ value: 1048, name: "正常" }, { value: 735, name: "告警" }, { value: 580, name: "离线" }, { value: 484, name: "维护" }] }] })
  }
  if (lineChartRef.value) {
    lineChart = echarts.init(lineChartRef.value)
    lineChart.setOption({ tooltip: { trigger: "axis" }, legend: { data: ["告警数", "故障数"] }, xAxis: { type: "category", data: ["周一", "周二", "周三", "周四", "周五", "周六", "周日"] }, yAxis: { type: "value" }, series: [{ name: "告警数", type: "line", data: [120, 132, 101, 134, 90, 230, 210] }, { name: "故障数", type: "line", data: [20, 32, 11, 34, 10, 30, 20] }] })
  }
  if (barChartRef.value) {
    barChart = echarts.init(barChartRef.value)
    barChart.setOption({ tooltip: { trigger: "axis" }, legend: { data: ["已用", "可用"] }, xAxis: { type: "category", data: ["A区", "B区", "C区", "D区"] }, yAxis: { type: "value", name: "U位" }, series: [{ name: "已用", type: "bar", data: [320, 302, 341, 374] }, { name: "可用", type: "bar", data: [120, 132, 101, 134] }] })
  }
}

function presentToCanvas() { ElMessage.info("投屏功能待接入 canvas 技能") }
function handleResize() { pieChart?.resize(); lineChart?.resize(); barChart?.resize() }
onMounted(() => { initCharts(); window.addEventListener("resize", handleResize) })
onUnmounted(() => { window.removeEventListener("resize", handleResize); pieChart?.dispose(); lineChart?.dispose(); barChart?.dispose() })
</script>

<style scoped>
.canvas-view { padding: 16px; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.chart-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px; }
.chart-item { background: var(--el-fill-color-lighter); border-radius: 8px; padding: 16px; }
.chart-item.full-width { grid-column: 1 / -1; }
.chart-item h4 { margin: 0 0 12px 0; font-size: 14px; color: var(--el-text-color-regular); }
.chart-container { width: 100%; height: 280px; }
</style>