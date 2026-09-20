# REQ-f0579a 测试设计（审计整改）

## 既有失败用例 → 修复映射（17 例全部回归）

| 失败群 | 用例 | 修复 |
|--------|------|------|
| 覆盖留痕 | verify-override×2 / acceptance-archive×2 / e2e-accept-override×1 | FR-1 删早退分支 |
| 客户端回归 | client-view×2（done 泳道、归档条、产物标签） | FR-2 恢复三处渲染 |
| 操作条断言 | board-info-fixes×3 | FR-3 断言精确化（测试内注释写明两条裁定合并点，防再被当 bug 改回） |
| 门禁债 | output-contract×2 / layer-boundary×1 / tools-dispatch×1 / message-hygiene×2 / size-budget×1 | FR-4/FR-5 |

## 新增回归测试

- tests/markdown-links.test.ts（3 例）：renderMarkdown 的 javascript:/data: 协议不渲染为链接；http/https/mailto/相对路径/锚点正常。**先写红测试复现再修**（bug 类型纪律）。

## 根因级发现（排查过程沉淀）

- output-contract「defineTaskStatusTool 未扫到任何 return 键」的真因：TaskStatusTool 的正则字面量内含裸反引号，被契约静态扫描器当模板字符串起点、吞掉后续全部 return。改写为 \x60 转义后扫描恢复。同类盲区今后凡见「扫描器可能失效」报警先查正则里的反引号。

## 终验命令

    npx vitest run            # 114 文件 / 1407 用例 0 失败
    npx tsc --noEmit          # 0 错误
    pnpm build                # + verify-client-build（WRAP_SENTINEL）