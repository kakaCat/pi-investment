# 错误事件处置：baostock.get_klines failed（NoneType.error_code）· d9361056

- **事件 ID**：`d9361056-af34-441c-8ae0-e8f9840ca429`（source=v2，error，频次 150；09-12 22:03~22:06）
- **处置窗口**：w-32314d00

## 1. 复现（本机实证，非推断）

```console
$ python - << py
import baostock as bs
bs.login()                                  # login: 0 success
# 传 YYYYMMDD：
rs = bs.query_history_k_data_plus('sz.000908', 'date,code,open,...',
                                  start_date='20260826', end_date='20260911', frequency='d', adjustflag='2')
日期格式不正确，请修改。                     # ← baostock 自己打印的
YYYYMMDD -> rs is None: True                 # ← 返回 None，没有 error_code 可读
# 传 ISO：
rs = bs.query_history_k_data_plus(..., start_date='2026-08-26', end_date='2026-09-11', ...)
ISO      -> rs is None: False，error_code=0，正常返回数据
```

## 2. 根因：调用方传 YYYYMMDD，baostock 只认 ISO；且 provider 没做 None 守护

`application/services/data_backfiller.py:176`：

```python
response = self.data_source_manager.get_klines(
    symbol=symbol_clean, period='daily',
    start_date=start_date.replace('-', ''),   # YYYYMMDD  ← baostock 不认
    end_date=end_date.replace('-', ''))
```

manager 把日期**原样转发**给各 provider（tencent/sina 容忍 YYYYMMDD，baostock 不容忍）→
baostock 返回 `None` → `baostock.py` 旧代码在 `if rs.error_code != "0"` 处抛
`AttributeError: NoneType object has no attribute error_code` → 被上层当作 provider 失败。

三个后果：①错误事件 150 条；②**抗 WAF 的 baostock 源在这条链路上等于不可用**（每次都判失败）；
③每次失败都要走完 3 次重试 + 退避，白白拉长回填时间。

## 3. 落地动作

1. **provider 边界归一日期**：新增 `BaostockKlineProvider._normalize_date()`（`YYYYMMDD` → `YYYY-MM-DD`，
   ISO 原样返回），调用方无需改动；
2. **补 `rs is None` 守护**：给出可读 `last_error`（不再 AttributeError），并明确按永久错误处理、不重试。

## 4. 验证

```console
# 真实 baostock 调用（修复后）
$ provider.get_klines("000908", "daily", "20260826", "20260911")   # 故意传 YYYYMMDD
rows=13   first=2026-08-26 close 6.53   last=2026-09-11 close 6.24

$ DataProviderManager().get_klines("000908", "daily", "20260826", "20260911")
success=True  source=database+baostock  n=13     ← 修复前这条链路必失败

$ pytest tests/test_baostock_date_normalization.py -q   → 3 passed
     （断言 provider 必须以 ISO 调 baostock；rs=None 时可读报错且只查一次、不重试）

$ 重启后该错误串出现次数 → 0
```

## 5. 结论

- **事件性质**：代码 bug（跨 provider 的日期格式契约不一致 + None 未守护），已修好并实证；
  修复同时**恢复**了 baostock 这条抗封禁通道的可用性。
- 通用纪律：**多 provider 共用入口必须各自容忍入参格式，或由 manager 统一归一**——
  「某个源能忍、另一个不能忍」的差异不会报契约错误，只会以 AttributeError/None 的形式散落成噪声。