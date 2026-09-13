# 基准：买入持有（对照用，不交易）
my_indicator_name = "buy-and-hold-benchmark"
df["buy"] = False
df["sell"] = False
df.iloc[0, df.columns.get_loc("buy")] = True   # 首日买入，永不卖出
