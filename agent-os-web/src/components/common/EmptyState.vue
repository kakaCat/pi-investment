<template>
  <div class="empty-state">
    <el-empty :description="description" :image-size="imageSize">
      <template #image v-if="customImage">
        <img :src="customImage" :alt="description" />
      </template>
      <slot name="extra"></slot>
    </el-empty>
  </div>
</template>

<script setup lang="ts">
interface Props {
  description?: string
  imageSize?: number
  customImage?: string
}

withDefaults(defineProps<Props>(), {
  description: '暂无数据',
  imageSize: 200,
})
</script>

<style scoped>
.empty-state {
  padding: 40px 0;
  text-align: center;
}
</style>
