<template>
  <el-card style="max-width: 420px; margin: 80px auto">
    <h2>登录</h2>
    <el-form :model="form" label-width="80px">
      <el-form-item label="用户名">
        <el-input v-model="form.username" />
      </el-form-item>
      <el-form-item label="密码">
        <el-input v-model="form.password" type="password" show-password />
      </el-form-item>
      <el-button type="primary" @click="login">登录</el-button>
    </el-form>
  </el-card>
</template>

<script setup lang="ts">
import { ElMessage } from "element-plus";
import { reactive } from "vue";
import { useRouter } from "vue-router";
import { useAuthStore } from "../stores/auth";

const router = useRouter();
const auth = useAuthStore();
const form = reactive({ username: "", password: "" });

async function login() {
  try {
    await auth.login(form.username, form.password);
    router.push("/");
  } catch {
    ElMessage.error("登录失败");
  }
}
</script>
