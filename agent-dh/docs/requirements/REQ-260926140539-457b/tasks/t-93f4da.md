# t-93f4da 实现全局生命周期 RTM 生成

> 需求：REQ-260926140539-457b RTM YAML 追溯基础设施 - Dive 模式自动化的数据底座

## 在做什么
实现全局生命周期 RTM 生成

## 解决什么问题
创建 src/rtm/lifecycle-generator.ts，实现 generateLifecycleRTM(reqId)，生成 current_stage=draft、各节点 status=pending 的骨架并落盘。

## 得到什么结果
运行 `pnpm test lifecycle-generator.test.ts` 通过；调用 generateLifecycleRTM 后 rtm-lifecycle.yml 存在；执行 `yq .lifecycle.current_stage` 返回 "draft"；`yq .lifecycle.stages | keys | length` 返回 7

---
## 汇报 1（2026-09-26T10:32:48.628Z，窗口 session-c5ea210f-afc3-4735-a4d1-f9058b378363）

这一步做完，需求一立项就有了一张「全局状态卡」：当前走到哪一阶段、各阶段完成没有、每个阶段确认过哪些产物，一眼可见。

### 完成项

- generateLifecycleRTM 生成/更新 rtm-lifecycle.yml
- 阶段状态按台账状态派生（archived→done）
- 已确认产物按阶段归档留痕

### 改动文件

- `packages/tools/reqboard/src/rtm/lifecycle-generator.ts`
- `packages/tools/reqboard/src/rtm/context.ts`

---
