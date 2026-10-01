# t-812ecc 数据访问规则收口 + provider 归位·复核

> 需求：REQ-261001145152-3982 V2 项目全面审查与优化梳理

## 在做什么
数据访问规则收口 + provider 归位·复核

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
对照 `docs/requirements/<REQ>/design/` 逐条核对；`npx vitest run <相关测试文件>` → 全绿；无偏离时显式写明「无偏离」及依据

---
## 汇报 1（2026-10-01T12:43:17.408Z，窗口 session-7fc133ad-e896-4aa2-9cb5-443ac7c5af22）

复核段：范围干净、没推高越层导入数、也没造第二份取数实现；另外发现并改掉了被我改过的那个文件里**仍写着旧数据源口径的说明文字**——文档与现实对齐了。

### 完成项

- 复核①：改动范围精确——仅 3 个文件（`application/services/core_plan_service.py`、`application/services/market_style_detector.py`、`adapters/outbound/datasources/providers/sector/akshare.py`），无越界
- 复核②：**未推高越层导入余量**——application 层顶层越层导入实测仍为 **44 处**（与 t-4f6f4b 收尾时一致），because 新引入的 `adapters` 引用是**函数内惰性导入**（本仓既有 182 处同此模式），未新增顶层违规
- 复核③：**未造重复实现**——新浪行业取数全仓只有 adapters 层的既有实现被复用；我为 `AkshareSectorProvider` 加的是**公开入口转发**（`fetch_sina_industries()` → 既有私有实现），不是新取数逻辑
- 复核④：归因证据复核仍在——批量失败清单改动后 2 条 / 回退后 2 条 / **差异 0 条**
- 复核⑤（发现并修正一处文档旧口径）：`market_style_detector.py` 的模块 docstring 仍写着"数据源：akshare ak.stock_sector_spot(...)"，与收口后的现实不符——已改为"取数出口：DataProviderManager 的 akshare 行业通道"并标注收口来源；改后 `stock_sector_spot` 在该文件已无残留、13 条测试仍全过
- 偏离结论：**相对用户裁定零偏离**（只修服务层两处、provider 包不动）；相对原卡有三处范围调整均有据：审计说 6 处直连实际剩 3 处（我删重复 provider 时已消 3 处）、卡说"建议下沉 provider"与 RFC 016 的"删除"冲突故按裁定留待专项、批量测试失败已证明与本卡无关

### 改动文件

- `application/services/core_plan_service.py`
- `application/services/market_style_detector.py`
- `adapters/outbound/datasources/providers/sector/akshare.py`

---
