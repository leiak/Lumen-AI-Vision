<template>
  <el-row v-if="data" :gutter="16">
    <el-col :span="6">
      <el-card>事件总数<div>{{ data.event_total }}</div></el-card>
    </el-col>
    <el-col :span="6">
      <el-card>任务总数<div>{{ data.task_total }}</div></el-card>
    </el-col>
    <el-col :span="6">
      <el-card>任务闭环率<div>{{ data.task_close_rate }}</div></el-card>
    </el-col>
  </el-row>
  <el-card v-if="data" style="margin-top: 16px">
    <h3>事件状态</h3>
    <el-tag v-for="(count, status) in data.event_by_status" :key="status">{{ status }}: {{ count }}</el-tag>
    <h3>风险分布</h3>
    <el-tag v-for="(count, risk) in data.event_by_risk" :key="risk">{{ risk }}: {{ count }}</el-tag>
  </el-card>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { api } from "../api/client";

const data = ref<any>(null);

onMounted(async () => {
  const response = await api.get("/metrics/summary");
  data.value = response.data;
});
</script>
