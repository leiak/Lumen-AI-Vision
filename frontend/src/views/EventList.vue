<template>
  <el-form inline>
    <el-form-item label="风险等级">
      <el-select v-model="filters.risk_level" clearable>
        <el-option label="低" value="low" />
        <el-option label="中" value="medium" />
        <el-option label="高" value="high" />
        <el-option label="严重" value="critical" />
      </el-select>
    </el-form-item>
    <el-form-item label="状态">
      <el-select v-model="filters.status" clearable>
        <el-option label="候选" value="candidate" />
        <el-option label="确认" value="confirmed" />
        <el-option label="拒绝" value="rejected" />
        <el-option label="关闭" value="closed" />
      </el-select>
    </el-form-item>
    <el-button type="primary" @click="load">查询</el-button>
    <el-button type="success" @click="exportCsv">导出 CSV</el-button>
  </el-form>
  <el-table :data="events" style="width: 100%">
    <el-table-column prop="id" label="事件ID" />
    <el-table-column prop="camera_id" label="摄像头" />
    <el-table-column prop="area_id" label="区域" />
    <el-table-column prop="event_type" label="类型" />
    <el-table-column prop="risk_level" label="风险等级" />
    <el-table-column prop="status" label="状态" />
    <el-table-column label="操作">
      <template #default="{ row }">
        <router-link :to="`/events/${row.id}`">详情</router-link>
      </template>
    </el-table-column>
  </el-table>
</template>

<script setup lang="ts">
import { ElMessage } from "element-plus";
import { onMounted, ref } from "vue";
import { reactive } from "vue";
import { api } from "../api/client";

const events = ref([]);
const filters = reactive({ risk_level: "", status: "" });

async function load() {
  const response = await api.get("/events", { params: filters });
  events.value = response.data;
}

async function exportCsv() {
  const response = await api.get("/exports/events", { responseType: "blob" });
  const disposition = response.headers["content-disposition"] || "";
  const filename = disposition.split("filename=")[1]?.replace(/"/g, "") || "events.csv";
  const url = window.URL.createObjectURL(new Blob([response.data]));
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  window.URL.revokeObjectURL(url);
  ElMessage.success("事件 CSV 已下载");
}

onMounted(load);
</script>
