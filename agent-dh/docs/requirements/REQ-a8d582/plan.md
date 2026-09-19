# REQ-a8d582 拆分计划

> 需求：[requirement.md](./requirement.md) · 设计：[design/design.md](./design/design.md)
> 档位：重档 · 类型：feature · 绑定窗口：w-054044c2

## 目标

让看板的「验收通过」在**验收阶段就一直可见**，并在人点下去之前把"不通过 / 未裁决"摆到眼前；由此带来的两个语义变化——**裁决不再自动打回**、**返工由"退回返工"触发**——一并落地，覆盖式通过必须留痕。

## 做法（三步）

1. **客户端**：按钮显示条件改为只看阶段；点「验收通过」先装配计数文案并弹确认框，确认后带覆盖说明发请求。
2. **服务端**：裁决只写验收单、不改状态；返工任务搬到"退回返工"动作里；pass 在"有不合格或没有材料"时要求显式覆盖并写入台账。
3. **收口**：重建 client 产物、跑全量单测、在 :13080 实测四条路径。

## 任务表

| key | 标题 | phase | side | depends_on |
|---|---|---|---|---|
| t1 | 验收态按钮常显 + 「验收通过」二次确认弹框 | implement | frontend | — |
| t2 | 验收裁决只记录，不再自动打回 | implement | backend | — |
| t3 | 返工任务改由「退回返工」生成 | implement | backend | t2 |
| t4 | 通过动作的覆盖语义与台账留痕 | implement | backend | t2 |
| t5 | 重建产物 + 全量回归 + :13080 实测四条路径 | test | fullstack | t1, t3, t4 |

## 验收命令

```bash
cd agent-dh/packages/pages/dsh-pmboard
pnpm build          # 改 src/ 后必须重建（构建新鲜度门）
npx vitest run      # 全量单测
python3 ../../../scripts/relink-profile.py --check   # profile 符号链接未漂移
```
