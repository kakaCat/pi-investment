<template>
  <el-aside width="200px" class="sidebar">
    <div class="logo">🧠 Agent OS</div>
    <el-menu
      :default-active="$route.path"
      router
      background-color="#1a1a2e"
      text-color="#fff"
      active-text-color="#409eff"
    >
      <el-menu-item index="/overview">
        <el-icon><DataLine /></el-icon>
        <span>概览中心</span>
      </el-menu-item>
      <el-menu-item index="/scheduler/tasks">
        <el-icon><Timer /></el-icon>
        <span>调度中心</span>
      </el-menu-item>
      <el-menu-item index="/skills">
        <el-icon><Coin /></el-icon>
        <span>技能中心</span>
      </el-menu-item>
      <el-menu-item index="/events">
        <el-icon><Bell /></el-icon>
        <span>事件中心</span>
      </el-menu-item>
      <el-menu-item index="/system/status">
        <el-icon><Setting /></el-icon>
        <span>系统中心</span>
      </el-menu-item>
    </el-menu>
  </el-aside>
</template>

<script setup lang="ts">
import { DataLine, Timer, Coin, Bell, Setting } from '@element-plus/icons-vue'
</script>

<style scoped>
.sidebar {
  background: #1a1a2e;
}
.logo {
  padding: 20px;
  color: #fff;
  font-size: 18px;
  font-weight: bold;
  text-align: center;
}
</style>
