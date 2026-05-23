# 测试文档

本文档介绍如何在 web-frontend 项目中运行和编写测试。

## 测试框架

本项目使用以下测试工具：

- **Vitest**: 快速的单元测试框架，专为 Vite 项目优化
- **@vue/test-utils**: Vue 3 官方测试工具库
- **happy-dom**: 轻量级 DOM 实现，用于测试环境
- **@vitest/ui**: 可视化测试界面

## 运行测试

### 基本命令

```bash
# 运行所有测试
npm test

# 运行测试并监听文件变化
npm run test:watch

# 运行测试并生成覆盖率报告
npm run test:coverage

# 打开可视化测试界面
npm run test:ui
```

### 运行特定测试

```bash
# 运行特定文件的测试
npx vitest tests/unit/utils/format.test.ts

# 运行匹配模式的测试
npx vitest format

# 运行单个测试用例（使用 it.only）
# 在测试文件中使用 it.only('test name', () => {...})
```

## 测试结构

```
tests/
├── setup.ts                          # 全局测试配置
├── unit/                             # 单元测试
│   ├── utils/                        # 工具函数测试
│   │   └── format.test.ts
│   ├── composables/                  # 组合式函数测试
│   │   └── useTable.test.ts
│   └── components/                   # 组件测试
│       └── SignalCard.test.ts
└── README.md                         # 本文档
```

## 编写测试

### 1. 测试工具函数

工具函数测试示例（`tests/unit/utils/format.test.ts`）：

```typescript
import { describe, it, expect } from 'vitest'
import { formatPrice, formatPercent } from '@/utils/format'

describe('format.ts - Number Formatting', () => {
  describe('formatPrice', () => {
    it('should format number to fixed decimal places', () => {
      expect(formatPrice(123.456)).toBe('123.46')
      expect(formatPrice(123.456, 3)).toBe('123.456')
    })

    it('should return -- for invalid input', () => {
      expect(formatPrice('invalid')).toBe('--')
    })
  })
})
```

### 2. 测试组合式函数

组合式函数测试示例（`tests/unit/composables/useTable.test.ts`）：

```typescript
import { describe, it, expect, beforeEach } from 'vitest'
import { useTable } from '@/composables/useTable'

describe('useTable.ts', () => {
  let table: ReturnType<typeof useTable>

  beforeEach(() => {
    table = useTable({ pageSize: 10 })
  })

  it('should initialize with default values', () => {
    expect(table.data.value).toEqual([])
    expect(table.loading.value).toBe(false)
  })

  it('should set data correctly', () => {
    const testData = [{ id: 1, name: 'Test' }]
    table.setData(testData)
    expect(table.data.value).toEqual(testData)
  })
})
```

### 3. 测试 Vue 组件

Vue 组件测试示例（`tests/unit/components/SignalCard.test.ts`）：

```typescript
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import SignalCard from '@/components/trading/SignalCard.vue'

describe('SignalCard.vue', () => {
  const mockSignal = {
    id: '1',
    type: 'buy',
    symbol: '600000',
    symbolName: '浦发银行',
    price: 10.5,
    status: 'pending'
  }

  it('should render signal card', () => {
    const wrapper = mount(SignalCard, {
      props: { signal: mockSignal }
    })
    expect(wrapper.find('.signal-card').exists()).toBe(true)
  })

  it('should emit approve event', async () => {
    const wrapper = mount(SignalCard, {
      props: { signal: mockSignal }
    })
    await wrapper.find('.approve-button').trigger('click')
    expect(wrapper.emitted('approve')).toBeTruthy()
  })
})
```

## 测试最佳实践

### 1. 测试命名

- 使用描述性的测试名称
- 使用 `describe` 分组相关测试
- 使用 `it` 或 `test` 描述单个测试用例

```typescript
describe('Component/Function Name', () => {
  describe('Feature/Method Name', () => {
    it('should do something when condition', () => {
      // 测试代码
    })
  })
})
```

### 2. AAA 模式

遵循 Arrange-Act-Assert 模式：

```typescript
it('should calculate total correctly', () => {
  // Arrange - 准备测试数据
  const items = [{ price: 10 }, { price: 20 }]
  
  // Act - 执行操作
  const total = calculateTotal(items)
  
  // Assert - 验证结果
  expect(total).toBe(30)
})
```

### 3. 使用 beforeEach 和 afterEach

```typescript
describe('MyComponent', () => {
  let wrapper

  beforeEach(() => {
    // 每个测试前执行
    wrapper = mount(MyComponent)
  })

  afterEach(() => {
    // 每个测试后执行
    wrapper.unmount()
  })

  it('test case 1', () => {
    // 使用 wrapper
  })
})
```

### 4. Mock 外部依赖

```typescript
import { vi } from 'vitest'

// Mock 模块
vi.mock('@/services/api', () => ({
  fetchData: vi.fn(() => Promise.resolve({ data: [] }))
}))

// Mock 函数
const mockFn = vi.fn()
mockFn.mockReturnValue('mocked value')
```

### 5. 测试异步代码

```typescript
it('should load data asynchronously', async () => {
  const promise = loadData()
  
  // 等待 Promise 完成
  await promise
  
  expect(data.value).toHaveLength(10)
})
```

### 6. 测试用户交互

```typescript
it('should handle button click', async () => {
  const wrapper = mount(MyComponent)
  
  // 触发点击事件
  await wrapper.find('button').trigger('click')
  
  // 验证结果
  expect(wrapper.emitted('submit')).toBeTruthy()
})
```

## 测试覆盖率

### 查看覆盖率报告

运行 `npm run test:coverage` 后，覆盖率报告会生成在 `coverage/` 目录：

- `coverage/index.html` - HTML 格式的详细报告
- `coverage/coverage-final.json` - JSON 格式的原始数据

### 覆盖率目标

建议的覆盖率目标：

- **语句覆盖率 (Statements)**: > 80%
- **分支覆盖率 (Branches)**: > 75%
- **函数覆盖率 (Functions)**: > 80%
- **行覆盖率 (Lines)**: > 80%

## 常见问题

### 1. 测试中如何处理 Element Plus 组件？

在 `tests/setup.ts` 中已经配置了 Element Plus 的 mock。如果需要测试特定组件，可以创建简单的 mock：

```typescript
const mockElButton = {
  name: 'ElButton',
  template: '<button><slot></slot></button>'
}

mount(MyComponent, {
  global: {
    components: { ElButton: mockElButton }
  }
})
```

### 2. 如何测试路由相关功能？

```typescript
import { createRouter, createMemoryHistory } from 'vue-router'

const router = createRouter({
  history: createMemoryHistory(),
  routes: [/* your routes */]
})

mount(MyComponent, {
  global: {
    plugins: [router]
  }
})
```

### 3. 如何测试 Pinia Store？

```typescript
import { setActivePinia, createPinia } from 'pinia'

beforeEach(() => {
  setActivePinia(createPinia())
})

it('should update store', () => {
  const store = useMyStore()
  store.updateData({ id: 1 })
  expect(store.data).toEqual({ id: 1 })
})
```

### 4. 测试中如何处理时间相关的函数？

使用 Vitest 的时间 mock：

```typescript
import { vi } from 'vitest'

beforeEach(() => {
  vi.useFakeTimers()
})

afterEach(() => {
  vi.useRealTimers()
})

it('should debounce function calls', () => {
  const fn = vi.fn()
  const debounced = debounce(fn, 1000)
  
  debounced()
  debounced()
  
  vi.advanceTimersByTime(1000)
  
  expect(fn).toHaveBeenCalledTimes(1)
})
```

## 调试测试

### 1. 使用 console.log

```typescript
it('debug test', () => {
  console.log('Debug info:', someValue)
  expect(someValue).toBe(expected)
})
```

### 2. 使用 wrapper.html()

```typescript
it('debug component', () => {
  const wrapper = mount(MyComponent)
  console.log(wrapper.html())
})
```

### 3. 使用 VS Code 调试

在 `.vscode/launch.json` 中添加配置：

```json
{
  "type": "node",
  "request": "launch",
  "name": "Debug Vitest Tests",
  "runtimeExecutable": "npm",
  "runtimeArgs": ["run", "test"],
  "console": "integratedTerminal"
}
```

## 持续集成

在 CI/CD 流程中运行测试：

```yaml
# .github/workflows/test.yml
name: Test

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-node@v2
      - run: npm install
      - run: npm test
      - run: npm run test:coverage
```

## 参考资源

- [Vitest 官方文档](https://vitest.dev/)
- [Vue Test Utils 文档](https://test-utils.vuejs.org/)
- [Testing Library 最佳实践](https://testing-library.com/docs/guiding-principles)
- [Vue 3 测试指南](https://vuejs.org/guide/scaling-up/testing.html)

## 贡献指南

编写新功能时，请确保：

1. 为新功能编写测试
2. 确保所有测试通过
3. 保持测试覆盖率在目标范围内
4. 遵循现有的测试模式和命名约定

如有问题，请查阅本文档或联系团队成员。
