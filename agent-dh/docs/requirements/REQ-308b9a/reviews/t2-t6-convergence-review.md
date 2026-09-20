# REQ-308b9a 评审记录

## R1 · t2/t6 双实现收敛（CR-1）

**发现**：逐项裁决存在两套实现——`application/internal/verdicts.ts` 的 `applyVerdicts` 与
`http/routers/verdicts.ts` 的内联循环；后者文件头却写着"路由与会话工具共用的单一实现"。

**结论**：已收敛——路由改为 `return { requirements: [applied.requirement], tasks: applied.reworkTasks }`，
错误码仍由路由前置校验（版本/项存在性）保留 400 语义。

**风险**：无（行为等价 + 新增自动回退）。

## R2 · FR-8 语义变更（CR-2）

`applyVerdicts` 在 failed>0 时**同笔 mutate** 内物化返工卡并迁移 `accepting → implementing`。
原子性依赖 `JsonLedgerRepository.mutate` 的 `structuredClone` 草稿 + 抛错不落盘，已由 T-I2 故障注入锁定。

## R3 · FR-9 放行判据（CR-3）

判据由"全 passed"改为"无 pending"（`isFullyDecided`）。`not_verifiable` 算已裁决且不触发回退（T-I4）；
pending 一律拦（T-U4）。向后兼容：枚举超集扩展，老单可读（NFR-1）。

## R4 · FR-7 文档门（CR-4）

9 类文档门设在**提交**环节（AC-7.5）。豁免口径两条（artifacts 空 / 盘上无 requirement.md），
用于存量与测试种子；真实需求必经 brainstorming 落 requirement.md，必然受检。判据用 requirement.md 而非
"目录非空"——首次提交会写 verification.md，用目录非空会被自己生成的产物破坏（实测踩过）。
