<template>
  <el-header class="header">
    <span>Agent OS 监控面板</span>
    <div class="right">
      <el-tag type="success">🟢 在线</el-tag>
      <span>admin</span>
    </div>
  </el-header>
</template>

<style scoped>
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: #16213e;
  color: #fff;
}
.right {
  display: flex;
  gap: 12px;
  align-items: center;
}
</style>
