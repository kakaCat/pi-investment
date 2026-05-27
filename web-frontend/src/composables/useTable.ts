import { ref, computed, toRaw } from 'vue'

/**
 * 表格组合式函数
 */
export function useTable<T = any>(options?: {
  pageSize?: number
  sortable?: boolean
}) {
  const data = ref<T[]>([])
  const loading = ref(false)
  const total = ref(0)
  const currentPage = ref(1)
  const pageSize = ref(options?.pageSize || 20)
  const sortBy = ref<string>('')
  const sortOrder = ref<'asc' | 'desc'>('asc')
  const selectedRows = ref<T[]>([])

  // 分页数据
  const paginatedData = computed(() => {
    if (!options?.sortable) return data.value

    const start = (currentPage.value - 1) * pageSize.value
    const end = start + pageSize.value
    return data.value.slice(start, end)
  })

  // 总页数
  const totalPages = computed(() => {
    return Math.ceil(total.value / pageSize.value)
  })

  // 是否有选中行
  const hasSelection = computed(() => selectedRows.value.length > 0)

  // 设置数据
  const setData = (newData: T[], newTotal?: number) => {
    data.value = newData
    if (newTotal !== undefined) {
      total.value = newTotal
    } else {
      total.value = newData.length
    }
  }

  // 加载数据
  const loadData = async (fetchFn: () => Promise<{ items: T[]; total: number }>) => {
    loading.value = true
    try {
      const response = await fetchFn()
      setData(response.items, response.total)
    } catch (error) {
      console.error('Failed to load data:', error)
    } finally {
      loading.value = false
    }
  }

  // 刷新数据
  const refresh = async (fetchFn: () => Promise<{ items: T[]; total: number }>) => {
    await loadData(fetchFn)
  }

  // 切换页码
  const changePage = (page: number) => {
    currentPage.value = page
  }

  // 切换每页条数
  const changePageSize = (size: number) => {
    pageSize.value = size
    currentPage.value = 1
  }

  // 排序
  const sort = (column: string, order: 'asc' | 'desc') => {
    sortBy.value = column
    sortOrder.value = order

    data.value.sort((a: any, b: any) => {
      const aVal = a[column]
      const bVal = b[column]

      if (order === 'asc') {
        return aVal > bVal ? 1 : -1
      } else {
        return aVal < bVal ? 1 : -1
      }
    })
  }

  // 选择行
  const selectRow = (row: T) => {
    const index = selectedRows.value.findIndex((r) => toRaw(r) === row)
    if (index > -1) {
      selectedRows.value.splice(index, 1)
    } else {
      selectedRows.value.push(row as any)
    }
  }

  // 全选/取消全选
  const toggleSelectAll = () => {
    if (selectedRows.value.length === data.value.length) {
      selectedRows.value = []
    } else {
      selectedRows.value = [...data.value]
    }
  }

  // 清空选择
  const clearSelection = () => {
    selectedRows.value = []
  }

  return {
    data,
    loading,
    total,
    currentPage,
    pageSize,
    sortBy,
    sortOrder,
    selectedRows,
    paginatedData,
    totalPages,
    hasSelection,
    setData,
    loadData,
    refresh,
    changePage,
    changePageSize,
    sort,
    selectRow,
    toggleSelectAll,
    clearSelection
  }
}
