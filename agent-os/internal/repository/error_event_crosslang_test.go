package repository

import "testing"

// 跨语言指纹一致性（2026-09-10 建立，2026-09-11 w-8f2c4cc5 重生成）：与 v2 Python 端
// agent_os_reporter._fingerprint 逐位对齐。改动归一化规则时必须双端同步并重生成向量。
//
// 2026-09-11 规则变更：JSON 通道指纹改取「事件文案本身」（event/message/msg），并新增
// logger 模块前缀剥离（adapters.x.y: msg → msg）——使同一异常经 JSON 与纯文本两个通道
// 落盘时归并为一条事件（实测 00:52 SchedulerService.add_task TypeError 生成两条）。
func TestFingerprintOf_CrossLanguageVectors(t *testing.T) {
	cases := []struct {
		msg, detail, want string
	}{
		{`{"event":"❌ 所有数据源都无法获取 600737.SH 的实时行情","trace_id":"aaaa1111","logger":"lg","timestamp":"2026-09-10T05:43:16.574188Z"}`, "", "e281d0995e9aa9325ae551401692b72b6d08a363"},
		{`{"event":"计算散户资金流失败: timeout 30s","trace_id":"bb","logger":"lg","timestamp":"2026-09-10T06:00:00Z"}`, "", "bed33d6f01d2ad4be8cc62d0b0d7df20b6347b68"},
		{`plain text error pool=default price=17.82 ts=2026-09-10T05:43:16Z id=550e8400-e29b-41d4-a716-446655440000`, "", "68948263f623ba4506c592d1947985224c4cbe89"},
		{`{"event":"html <b> & > test","trace_id":"cc","logger":"lg"}`, "", "56a5d0bd39327aa05b53a61b45c0f204406a0d8e"},
		{"any msg here", "Traceback (most recent call last):\n  File \"/app/services/pool.py\", line 88, in shutdown\n    code()\nTypeError: x", "ce0711aeff698435f4df541136fa9f41956c4db6"},
		// 真实事故碎片（2026-09-11 00:52 SchedulerService.add_task TypeError）：JSON 落盘行、
		// 带 logger 前缀的文本行、裸事件文案三者必须同指纹；5xx 访问日志行口径不同，保持独立。
		{`{"event": "API错误: SchedulerService.add_task() got an unexpected keyword argument 'task_type'", "trace_id": "95509f30", "logger": "adapters.inbound.fastapi_app.shared", "level": "error", "timestamp": "2026-09-10T16:52:06.189571Z"}`, "", "b48a75eeed631a95d4be041e530b088409644bac"},
		{"adapters.inbound.fastapi_app.shared: API错误: SchedulerService.add_task() got an unexpected keyword argument 'task_type'", "", "b48a75eeed631a95d4be041e530b088409644bac"},
		{"API错误: SchedulerService.add_task() got an unexpected keyword argument 'task_type'", "", "b48a75eeed631a95d4be041e530b088409644bac"},
		{`INFO:     127.0.0.1:65290 - "POST /api/scheduler/tasks HTTP/1.1" 500 Internal Server Error`, "", "a5c77b5739d19fe7edd61a29720585e8123fb3a2"},
		// 反向护栏：异常名开头（TypeError: ...）不得被 logger 前缀规则误剥。
		{"TypeError: boom at 2026-09-10T05:43:16Z", "", "8437b899337892657a3d61c33d1df4066b4ea901"},
	}
	for i, c := range cases {
		if got := FingerprintOfWithDetail("v2", "", c.msg, c.detail); got != c.want {
			t.Errorf("case %d: got %s, want %s", i, got, c.want)
		}
	}
}
