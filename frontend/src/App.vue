<template>
  <el-container>
    <el-header>
      <div>库门口异常停留识别</div>
      <el-button v-if="auth.user" text @click="logout">退出</el-button>
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
import { onMounted } from "vue";
import { useRouter } from "vue-router";
import { useAuthStore } from "./stores/auth";

const auth = useAuthStore();
const router = useRouter();

onMounted(async () => {
  if (auth.token) await auth.fetchMe();
});

function logout() {
  auth.logout();
  router.push("/login");
}
</script>

<style scoped>
.el-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
</style>
