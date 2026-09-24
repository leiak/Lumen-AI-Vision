<template>
    <el-button type="primary" @click="markAllRead">全部已读</el-button>
    <el-table :data="notifications" style="margin-top: 12px">
    <el-table-column prop="id" label="通知ID" />
    <el-table-column prop="event_id" label="事件ID" />
    <el-table-column prop="status" label="状态" />
    <el-table-column prop="sent_at" label="发送时间" />
    <el-table-column label="操作">
      <template #default="{ row }">
        <el-button v-if="row.status !== 'read'" size="small" @click="markRead(row.id)">已读</el-button>
      </template>
    </el-table-column>
  </el-table>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { api } from "../api/client";

const notifications = ref<any[]>([]);

async function load() {
  const response = await api.get("/notifications");
  notifications.value = response.data;
}

async function markRead(id: string) {
  await api.post(`/notifications/${id}/read`);
  await load();
}

async function markAllRead() {
  await api.post("/notifications/read-all");
  await load();
}

onMounted(load);
</script>
