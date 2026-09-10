package repository

import "testing"

// 跨语言指纹一致性（2026-09-10）：与 v2 Python 端 agent_os_reporter._fingerprint 逐位对齐。
// 向量由两端同跑生成；改动归一化规则时必须双端同步并重生成。
func TestFingerprintOf_CrossLanguageVectors(t *testing.T) {
	cases := []struct {
		msg, detail, want string
	}{
		{`{"event":"❌ 所有数据源都无法获取 600737.SH 的实时行情","trace_id":"aaaa1111","logger":"lg","timestamp":"2026-09-10T05:43:16.574188Z"}`, "", "af21467726aae1b99762c214caae8f5426de1bd5"},
		{`{"event":"计算散户资金流失败: timeout 30s","trace_id":"bb","logger":"lg","timestamp":"2026-09-10T06:00:00Z"}`, "", "4f4c8712cee3fe31be73b8b398b76fdc06091667"},
		{`plain text error pool=default price=17.82 ts=2026-09-10T05:43:16Z id=550e8400-e29b-41d4-a716-446655440000`, "", "68948263f623ba4506c592d1947985224c4cbe89"},
		{`{"event":"html <b> & > test","trace_id":"cc","logger":"lg"}`, "", "f892d1002dd82760ccef35efa70ae6908607fce3"},
		{"any msg here", "Traceback (most recent call last):\n  File \"/app/services/pool.py\", line 88, in shutdown\n    code()\nTypeError: x", "ce0711aeff698435f4df541136fa9f41956c4db6"},
	}
	for i, c := range cases {
		if got := FingerprintOfWithDetail("v2", "", c.msg, c.detail); got != c.want {
			t.Errorf("case %d: got %s, want %s", i, got, c.want)
		}
	}
}
