<template>
  <el-card :shadow="shadow" :body-style="bodyStyle" class="custom-card">
    <template v-if="$slots.header" #header>
      <slot name="header" />
    </template>

    <slot />

    <template v-if="$slots.footer" #footer>
      <slot name="footer" />
    </template>
  </el-card>
</template>

<script setup lang="ts">
interface Props {
  shadow?: 'always' | 'hover' | 'never'
  bodyStyle?: Record<string, any>
}

withDefaults(defineProps<Props>(), {
  shadow: 'hover',
  bodyStyle: () => ({})
})
</script>

<style scoped>
.custom-card {
  margin-bottom: 16px;
}
</style>
