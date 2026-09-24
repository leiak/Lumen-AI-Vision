<template>
  <el-table :data="tasks">
    <el-table-column prop="id" label="任务ID" />
    <el-table-column prop="event_id" label="事件ID" />
    <el-table-column prop="status" label="状态" />
    <el-table-column prop="due_at" label="截止时间" />
    <el-table-column label="操作">
      <template #default="{ row }">
        <el-button size="small" @click="update(row.id, 'processing')">处理中</el-button>
        <el-button size="small" type="primary" @click="complete(row.id)">完成</el-button>
      </template>
    </el-table-column>
  </el-table>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { api } from "../api/client";

const tasks = ref<any[]>([]);

async function load() {
  const response = await api.get("/tasks");
  tasks.value = response.data;
}

async function update(taskId: string, status: string, result?: string) {
  await api.patch(`/tasks/${taskId}`, { status, result });
  await load();
}

function complete(taskId: string) {
  update(taskId, "completed", "on_site_handled");
}

onMounted(load);
</script>
