<template>
  <el-table
    :data="data"
    :stripe="stripe"
    :border="border"
    :loading="loading"
    :height="height"
    :max-height="maxHeight"
    style="width: 100%"
    @selection-change="handleSelectionChange"
    @sort-change="handleSortChange"
  >
    <el-table-column v-if="showSelection" type="selection" width="55" />
    <el-table-column v-if="showIndex" type="index" width="50" label="#" />

    <slot />
  </el-table>
</template>

<script setup lang="ts">
interface Props {
  data: any[]
  stripe?: boolean
  border?: boolean
  loading?: boolean
  height?: string | number
  maxHeight?: string | number
  showSelection?: boolean
  showIndex?: boolean
}

interface Emits {
  (e: 'selection-change', selection: any[]): void
  (e: 'sort-change', sort: { prop: string; order: string }): void
}

withDefaults(defineProps<Props>(), {
  stripe: true,
  border: false,
  loading: false,
  showSelection: false,
  showIndex: false
})

const emit = defineEmits<Emits>()

const handleSelectionChange = (selection: any[]) => {
  emit('selection-change', selection)
}

const handleSortChange = (sort: any) => {
  emit('sort-change', sort)
}
</script>
