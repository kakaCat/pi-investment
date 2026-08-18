<template>
  <el-container class="app-layout">
    <AppSidebar />
    <el-container>
      <AppHeader />
      <el-main>
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import AppSidebar from './AppSidebar.vue'
import AppHeader from './AppHeader.vue'
</script>

<style scoped>
.app-layout {
  height: 100vh;
}
</style>
