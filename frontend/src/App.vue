<template>
  <el-container>
    <el-header>
      <div>库门口异常停留识别</div>
      <div>
        <el-badge v-if="unread > 0" :value="unread" :max="99" class="badge">
          <el-button text @click="goNotifications">通知</el-button>
        </el-badge>
        <el-button v-if="auth.user" text @click="logout">退出</el-button>
      </div>
    </el-header>
    <el-menu mode="horizontal" router>
      <el-menu-item index="/">事件</el-menu-item>
      <el-menu-item index="/tasks">任务</el-menu-item>
      <el-menu-item index="/notifications">通知</el-menu-item>
      <el-menu-item index="/metrics">指标</el-menu-item>
      <el-menu-item v-if="auth.user?.role === 'admin'" index="/admin">管理</el-menu-item>
    </el-menu>
    <el-main>
      <router-view />
    </el-main>
</el-container>
</template>

<script setup lang="ts">
import { onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { useAuthStore } from "./stores/auth";
import { api } from "./api/client";

const auth = useAuthStore();
const router = useRouter();
const unread = ref(0);

async function refreshUnread() {
  if (!auth.user) {
    unread.value = 0;
    return;
  }
  try {
    const response = await api.get("/notifications/unread-count");
    unread.value = response.data?.unread ?? 0;
  } catch {
    unread.value = 0;
  }
}

function goNotifications() {
  router.push("/notifications");
}

onMounted(async () => {
  if (auth.token) await auth.fetchMe();
  await refreshUnread();
  window.addEventListener("unread-changed", refreshUnread);
});

watch(() => auth.user?.id, refreshUnread);

function logout() {
  auth.logout();
  unread.value = 0;
  router.push("/login");
}
</script>

<style scoped>
.el-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.badge {
  margin-right: 12px;
}
</style>