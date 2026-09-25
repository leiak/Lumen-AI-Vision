<template>
  <div class="metrics-page">
    <el-card class="toolbar">
      <div class="toolbar-body">
        <div>
          <h2>运营指标</h2>
          <p class="muted">用于评估事件质量、处理效率、模型表现和重点区域风险。</p>
        </div>
        <div class="toolbar-actions">
          <el-select v-model="days" style="width: 130px" @change="load">
            <el-option label="最近 1 天" :value="1" />
            <el-option label="最近 7 天" :value="7" />
            <el-option label="最近 30 天" :value="30" />
            <el-option label="最近 90 天" :value="90" />
          </el-select>
          <el-button type="primary" @click="load">刷新</el-button>
        </div>
      </div>
    </el-card>

    <el-row v-if="data" :gutter="12" class="kpi-row">
      <el-col v-for="item in kpis" :key="item.label" :xs="12" :sm="8" :md="6" :lg="3">
        <el-card class="kpi-card">
          <div class="kpi-label">{{ item.label }}</div>
          <div class="kpi-value">{{ item.value }}</div>
          <div class="kpi-sub">{{ item.sub }}</div>
        </el-card>
      </el-col>
    </el-row>

    <el-row v-if="data" :gutter="12">
      <el-col :xs="24" :lg="8">
        <el-card>
          <h3>风险分布</h3>
          <el-table :data="riskRows" size="small">
            <el-table-column prop="name" label="风险" />
            <el-table-column prop="count" label="数量" width="90" align="right" />
            <el-table-column prop="rate" label="占比" width="100" align="right" />
          </el-table>
        </el-card>
      </el-col>
      <el-col :xs="24" :lg="8">
        <el-card>
          <h3>状态分布</h3>
          <el-table :data="statusRows" size="small">
            <el-table-column prop="name" label="状态" />
            <el-table-column prop="count" label="数量" width="90" align="right" />
            <el-table-column prop="rate" label="占比" width="100" align="right" />
          </el-table>
        </el-card>
      </el-col>
      <el-col :xs="24" :lg="8">
        <el-card>
          <h3>行为分布</h3>
          <el-table :data="behaviorRows" size="small">
            <el-table-column prop="name" label="行为" />
            <el-table-column prop="count" label="数量" width="90" align="right" />
            <el-table-column prop="rate" label="占比" width="100" align="right" />
          </el-table>
        </el-card>
      </el-col>
    </el-row>

    <el-row v-if="data" :gutter="12" class="section">
      <el-col :xs="24" :lg="12">
        <el-card>
          <h3>每日趋势</h3>
          <el-table :data="data.daily_trend" size="small" max-height="360">
            <el-table-column prop="date" label="日期" />
            <el-table-column prop="event_total" label="事件" align="right" />
            <el-table-column prop="high_risk_total" label="高风险" align="right" />
            <el-table-column prop="closed_total" label="关闭" align="right" />
            <el-table-column prop="confirmed_total" label="确认" align="right" />
            <el-table-column prop="rejected_total" label="拒绝" align="right" />
          </el-table>
        </el-card>
      </el-col>
      <el-col :xs="24" :lg="12">
        <el-card>
          <h3>区域热点</h3>
          <el-table :data="data.hotspots.areas" size="small" max-height="360">
            <el-table-column prop="id" label="区域" show-overflow-tooltip />
            <el-table-column prop="event_total" label="事件" align="right" />
            <el-table-column prop="high_risk_total" label="高风险" align="right" />
            <el-table-column prop="closed_total" label="关闭" align="right" />
            <el-table-column prop="avg_duration_minutes" label="均时长(分)" align="right" />
          </el-table>
        </el-card>
      </el-col>
    </el-row>

    <el-row v-if="data" :gutter="12" class="section">
      <el-col :xs="24" :lg="12">
        <el-card>
          <h3>处理效率</h3>
          <el-descriptions :column="1" border>
            <el-descriptions-item label="任务闭环率">{{ percent(data.tasks.close_rate) }}</el-descriptions-item>
            <el-descriptions-item label="按时完成率">{{ percent(data.tasks.on_time_rate) }}</el-descriptions-item>
            <el-descriptions-item label="平均完成时长">{{ data.tasks.avg_completion_minutes }} 分钟</el-descriptions-item>
            <el-descriptions-item label="通知已读率">{{ percent(data.notifications.read_rate) }}</el-descriptions-item>
            <el-descriptions-item label="平均响应时长">{{ data.notifications.avg_response_minutes }} 分钟</el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>
      <el-col :xs="24" :lg="12">
        <el-card>
          <h3>复核质量</h3>
          <el-table :data="reviewRows" size="small">
            <el-table-column prop="name" label="复核结论" />
            <el-table-column prop="count" label="数量" width="90" align="right" />
            <el-table-column prop="rate" label="占比" width="100" align="right" />
          </el-table>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { api } from "../api/client";

const data = ref<any>(null);
const days = ref(7);

async function load() {
  const response = await api.get("/metrics/operations", { params: { days: days.value } });
  data.value = response.data;
}

const kpis = computed(() => {
  if (!data.value) return [];
  return [
    { label: "事件总数", value: data.value.events.total, sub: "所选周期内" },
    { label: "高风险事件", value: data.value.events.high_risk_total, sub: "high / critical" },
    { label: "事件关闭率", value: percent(data.value.events.closed_rate), sub: "closed / total" },
    { label: "任务闭环率", value: percent(data.value.tasks.close_rate), sub: "completed / total" },
    { label: "超时任务", value: data.value.tasks.overdue_total, sub: "pending + expired" },
    { label: "通知已读率", value: percent(data.value.notifications.read_rate), sub: "read / total" },
    { label: "行为记录", value: data.value.behaviors.total, sub: `${data.value.behaviors.by_model_type.rule || 0} 条规则结果` },
    { label: "平均置信度", value: data.value.behaviors.avg_confidence, sub: "behavior model" },
  ];
});

const riskRows = computed(() => toRows(data.value?.events.by_risk));
const statusRows = computed(() => toRows(data.value?.events.by_status));
const behaviorRows = computed(() => toRows(data.value?.behaviors.by_label));
const reviewRows = computed(() => toRows(data.value?.reviews.by_result));

function toRows(source: Record<string, number> | undefined) {
  const total = Object.values(source || {}).reduce((sum, value) => sum + value, 0);
  return Object.entries(source || {}).map(([name, count]) => ({
    name,
    count,
    rate: total ? `${Math.round((count / total) * 1000) / 10}%` : "0%",
  }));
}

function percent(value: number) {
  return `${Math.round(value * 10000) / 100}%`;
}

onMounted(load);
</script>

<style scoped>
.metrics-page {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.toolbar-body {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.toolbar-body h2 {
  margin: 0;
}

.muted {
  margin: 4px 0 0;
  color: #64748b;
  font-size: 13px;
}

.toolbar-actions {
  display: flex;
  gap: 8px;
}

.kpi-row {
  row-gap: 12px;
}

.kpi-card {
  height: 100%;
}

.kpi-label {
  color: #64748b;
  font-size: 12px;
}

.kpi-value {
  margin-top: 6px;
  font-size: 24px;
  font-weight: 700;
}

.kpi-sub {
  margin-top: 4px;
  color: #94a3b8;
  font-size: 12px;
}

.section {
  row-gap: 12px;
}

h3 {
  margin: 0 0 12px;
  font-size: 16px;
}
</style>
