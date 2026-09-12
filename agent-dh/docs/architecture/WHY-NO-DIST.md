# 为什么部分插件没有 dist 目录？

## 🎯 简短回答

**因为 DSH 使用 tsx 模式运行，可以直接加载 TypeScript 源码（`.ts` 文件），无需预构建为 JavaScript（`.mjs` 文件）。**

## 📊 当前状态

- **7 个包有 dist 目录**：agent-dh-client, agent-os-client, intelligence, investment-agent-loop, investment, quantsys-v2-client, trading
- **11 个包没有 dist 目录**：competition, data-manager, evolution, factor, market, memory, model, notification, risk, scheduler, strategy

## 🔍 深入理解

### 1. 所有包的 package.json 都指向 TypeScript 源码

```json
{
  "main": "./src/index.ts",        // ← 指向 .ts 文件，不是 .js
  "exports": {
    ".": {
      "import": "./src/index.ts",   // ← 直接导入 TypeScript
      "types": "./src/index.ts"
    }
  }
}
```

**关键点**：`main` 和 `exports` 都指向 `./src/index.ts`，而不是 `./dist/index.mjs`。

### 2. DSH 使用 tsx 模式启动

```bash
# ~/.dsh/profiles/investment/start.sh
exec node --import tsx/esm apps/cli/src/bin.ts \
  --profile investment \
  --port "$PORT"
```

**tsx 是什么？**
- `tsx` 是一个 TypeScript 执行器
- `node --import tsx/esm` 让 Node.js 能够直接运行 `.ts` 文件
- 无需预构建，支持热加载

### 3. 为什么有些包有 dist？

这些 dist 目录是**历史遗留**或**手动构建**的结果：

```bash
# 这些包曾经被手动构建过
packages/investment/dist/        # Aug 18 17:34 (2天前)
packages/trading/dist/           # Aug 18 17:34 (2天前)
packages/intelligence/dist/      # Aug 18 17:34 (2天前)
```

**但是**：这些 dist 目录**没有被使用**！因为 package.json 指向的是 `./src/index.ts`。

### 4. 为什么有些包没有 dist？

这些包**从未被构建过**，因为没有 build 脚本：

```json
// packages/competition/package.json
{
  "name": "@pi-investment/competition",
  "main": "./src/index.ts",
  // ❌ 没有 "scripts": { "build": "..." }
}
```

## ✅ 这两种方式都可以工作

### 方式 1：tsx 直接加载 TypeScript（当前使用）

```
DSH → 读取 package.json → main: "./src/index.ts" → tsx 加载 .ts 文件 → 运行
```

**优点**：
- ✅ 无需构建步骤
- ✅ 支持热加载（修改代码立即生效）
- ✅ 开发效率高

**缺点**：
- ❌ 首次加载稍慢（需要编译 TypeScript）
- ❌ 生产环境不推荐

### 方式 2：预构建为 JavaScript（传统方式）

```
DSH → 读取 package.json → main: "./dist/index.mjs" → 加载 .mjs 文件 → 运行
```

**优点**：
- ✅ 启动速度快
- ✅ 生产环境推荐

**缺点**：
- ❌ 需要构建步骤
- ❌ 修改代码需要重新构建

## 🎯 当前项目使用哪种方式？

**当前使用方式 1（tsx 模式）**，所有包都直接加载 `./src/index.ts`。

**dist 目录是可选的**，有以下情况：

1. **有 dist 的包**（7个）：
   - 曾经被手动构建过（`tsdown src/index.ts --dts`）
   - 或者是 client SDK 包（agent-dh-client, quantsys-v2-client 等）
   - **但当前未被使用**（因为 main 指向 .ts）

2. **没有 dist 的包**（11个）：
   - 从未被构建过
   - 没有 build 脚本
   - **正常工作**（通过 tsx 加载 .ts）

## 🔧 如果要切换到预构建模式

1. **为所有包添加 build 脚本**：

```json
{
  "scripts": {
    "build": "tsdown src/index.ts --dts"
  }
}
```

2. **修改 main 和 exports 指向 dist**：

```json
{
  "main": "./dist/index.mjs",
  "exports": {
    ".": {
      "import": "./dist/index.mjs",
      "types": "./dist/index.d.mts"
    }
  }
}
```

3. **构建所有包**：

```bash
cd agent-dh
pnpm -r build
```

4. **修改 DSH 启动脚本**（移除 tsx）：

```bash
# 从
node --import tsx/esm apps/cli/src/bin.ts

# 改为
node apps/cli/lib/bin.js
```

## 📝 总结

| 问题 | 答案 |
|------|------|
| 为什么部分插件没有 dist？ | 因为它们没有 build 脚本，且 DSH 使用 tsx 直接加载 .ts 文件 |
| dist 目录是必须的吗？ | **不是**，tsx 模式下不需要 |
| 有 dist 的包会被使用吗？ | **不会**，因为 package.json 指向 ./src/index.ts |
| 需要运行 pnpm build 吗？ | **不需要**，tsx 模式下直接加载 .ts |
| 如何验证插件是否工作？ | 检查 DSH 是否正常运行（端口 13080） |

## 🚀 实际验证

```bash
# 1. DSH 正在运行（使用 tsx）
ps aux | grep "tsx/esm.*investment"
# → node --import tsx/esm apps/cli/src/bin.ts --profile investment --port 13080

# 2. 检查没有 dist 的包是否工作
curl http://localhost:13080  # → 200 OK

# 3. 查看 DSH 日志（如果有）
# 应该能看到加载了所有 14 个插件，无论是否有 dist
```

---

**结论**：**dist 目录是可选的，当前项目使用 tsx 模式直接加载 TypeScript，无需构建。**
