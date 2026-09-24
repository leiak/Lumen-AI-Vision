<template>
  <el-container>
    <el-header>库门口异常停留识别</el-header>
    <el-menu mode="horizontal" router>
      <el-menu-item index="/">事件</el-menu-item>
      <el-menu-item index="/tasks">任务</el-menu-item>
      <el-menu-item index="/notifications">通知</el-menu-item>
      <el-menu-item index="/metrics">指标</el-menu-item>
    </el-menu>
    <el-main>
      <router-view />
    </el-main>
  </el-container>
</template>
