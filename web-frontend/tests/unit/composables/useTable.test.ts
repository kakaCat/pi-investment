import { describe, it, expect, beforeEach } from 'vitest'
import { useTable } from '@/composables/useTable'

interface TestItem {
  id: number
  name: string
  value: number
}

describe('useTable.ts', () => {
  let table: ReturnType<typeof useTable<TestItem>>

  beforeEach(() => {
    table = useTable<TestItem>({ pageSize: 10, sortable: true })
  })

  describe('Initialization', () => {
    it('should initialize with default values', () => {
      expect(table.data.value).toEqual([])
      expect(table.loading.value).toBe(false)
      expect(table.total.value).toBe(0)
      expect(table.currentPage.value).toBe(1)
      expect(table.pageSize.value).toBe(10)
      expect(table.selectedRows.value).toEqual([])
    })

    it('should use custom page size', () => {
      const customTable = useTable({ pageSize: 20 })
      expect(customTable.pageSize.value).toBe(20)
    })

    it('should use default page size when not provided', () => {
      const defaultTable = useTable()
      expect(defaultTable.pageSize.value).toBe(20)
    })
  })

  describe('setData', () => {
    it('should set data and total', () => {
      const testData: TestItem[] = [
        { id: 1, name: 'Item 1', value: 100 },
        { id: 2, name: 'Item 2', value: 200 }
      ]

      table.setData(testData, 50)

      expect(table.data.value).toEqual(testData)
      expect(table.total.value).toBe(50)
    })

    it('should set total to data length when not provided', () => {
      const testData: TestItem[] = [
        { id: 1, name: 'Item 1', value: 100 },
        { id: 2, name: 'Item 2', value: 200 }
      ]

      table.setData(testData)

      expect(table.total.value).toBe(2)
    })
  })

  describe('loadData', () => {
    it('should load data successfully', async () => {
      const mockData: TestItem[] = [
        { id: 1, name: 'Item 1', value: 100 },
        { id: 2, name: 'Item 2', value: 200 }
      ]

      const fetchFn = async () => ({
        items: mockData,
        total: 2
      })

      await table.loadData(fetchFn)

      expect(table.data.value).toEqual(mockData)
      expect(table.total.value).toBe(2)
      expect(table.loading.value).toBe(false)
    })

    it('should set loading state during fetch', async () => {
      const fetchFn = async () => {
        expect(table.loading.value).toBe(true)
        return { items: [], total: 0 }
      }

      await table.loadData(fetchFn)
      expect(table.loading.value).toBe(false)
    })

    it('should handle fetch errors', async () => {
      const fetchFn = async () => {
        throw new Error('Fetch failed')
      }

      await table.loadData(fetchFn)

      expect(table.loading.value).toBe(false)
      expect(table.data.value).toEqual([])
    })
  })

  describe('Pagination', () => {
    beforeEach(() => {
      const testData: TestItem[] = Array.from({ length: 25 }, (_, i) => ({
        id: i + 1,
        name: `Item ${i + 1}`,
        value: (i + 1) * 100
      }))
      table.setData(testData)
    })

    it('should calculate total pages correctly', () => {
      expect(table.totalPages.value).toBe(3) // 25 items / 10 per page = 3 pages
    })

    it('should paginate data correctly', () => {
      expect(table.paginatedData.value).toHaveLength(10)
      expect(table.paginatedData.value[0].id).toBe(1)
    })

    it('should change page', () => {
      table.changePage(2)
      expect(table.currentPage.value).toBe(2)
      expect(table.paginatedData.value[0].id).toBe(11)
    })

    it('should change page size and reset to first page', () => {
      table.changePage(2)
      table.changePageSize(20)

      expect(table.pageSize.value).toBe(20)
      expect(table.currentPage.value).toBe(1)
    })

    it('should handle last page with fewer items', () => {
      table.changePage(3)
      expect(table.paginatedData.value).toHaveLength(5) // 25 % 10 = 5 items
    })
  })

  describe('Sorting', () => {
    beforeEach(() => {
      const testData: TestItem[] = [
        { id: 3, name: 'Charlie', value: 300 },
        { id: 1, name: 'Alice', value: 100 },
        { id: 2, name: 'Bob', value: 200 }
      ]
      table.setData(testData)
    })

    it('should sort data in ascending order', () => {
      table.sort('value', 'asc')

      expect(table.sortBy.value).toBe('value')
      expect(table.sortOrder.value).toBe('asc')
      expect(table.data.value[0].value).toBe(100)
      expect(table.data.value[2].value).toBe(300)
    })

    it('should sort data in descending order', () => {
      table.sort('value', 'desc')

      expect(table.sortOrder.value).toBe('desc')
      expect(table.data.value[0].value).toBe(300)
      expect(table.data.value[2].value).toBe(100)
    })

    it('should sort by string field', () => {
      table.sort('name', 'asc')

      expect(table.data.value[0].name).toBe('Alice')
      expect(table.data.value[1].name).toBe('Bob')
      expect(table.data.value[2].name).toBe('Charlie')
    })
  })

  describe('Row Selection', () => {
    let testData: TestItem[]

    beforeEach(() => {
      testData = [
        { id: 1, name: 'Item 1', value: 100 },
        { id: 2, name: 'Item 2', value: 200 },
        { id: 3, name: 'Item 3', value: 300 }
      ]
      table.setData(testData)
    })

    it('should select a row', () => {
      table.selectRow(testData[0])

      expect(table.selectedRows.value).toHaveLength(1)
      expect(table.selectedRows.value[0]).toEqual(testData[0])
      expect(table.hasSelection.value).toBe(true)
    })

    it('should deselect a row when selected again', () => {
      table.selectRow(testData[0])
      table.selectRow(testData[0])

      expect(table.selectedRows.value).toHaveLength(0)
      expect(table.hasSelection.value).toBe(false)
    })

    it('should select multiple rows', () => {
      table.selectRow(testData[0])
      table.selectRow(testData[1])

      expect(table.selectedRows.value).toHaveLength(2)
    })

    it('should toggle select all', () => {
      table.toggleSelectAll()

      expect(table.selectedRows.value).toHaveLength(3)
      expect(table.hasSelection.value).toBe(true)

      table.toggleSelectAll()

      expect(table.selectedRows.value).toHaveLength(0)
      expect(table.hasSelection.value).toBe(false)
    })

    it('should clear selection', () => {
      table.selectRow(testData[0])
      table.selectRow(testData[1])
      table.clearSelection()

      expect(table.selectedRows.value).toHaveLength(0)
      expect(table.hasSelection.value).toBe(false)
    })
  })

  describe('Refresh', () => {
    it('should refresh data', async () => {
      const mockData: TestItem[] = [
        { id: 1, name: 'Item 1', value: 100 }
      ]

      const fetchFn = async () => ({
        items: mockData,
        total: 1
      })

      await table.refresh(fetchFn)

      expect(table.data.value).toEqual(mockData)
      expect(table.total.value).toBe(1)
    })
  })

  describe('Computed Properties', () => {
    it('should compute hasSelection correctly', () => {
      expect(table.hasSelection.value).toBe(false)

      const testData: TestItem[] = [{ id: 1, name: 'Item 1', value: 100 }]
      table.setData(testData)
      table.selectRow(testData[0])

      expect(table.hasSelection.value).toBe(true)
    })

    it('should return all data when sortable is false', () => {
      const nonSortableTable = useTable<TestItem>({ sortable: false })
      const testData: TestItem[] = Array.from({ length: 25 }, (_, i) => ({
        id: i + 1,
        name: `Item ${i + 1}`,
        value: (i + 1) * 100
      }))

      nonSortableTable.setData(testData)

      expect(nonSortableTable.paginatedData.value).toHaveLength(25)
    })
  })
})
