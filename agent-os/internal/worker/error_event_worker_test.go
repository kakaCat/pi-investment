package worker

import (
	"strings"
	"testing"
)

// 回归：v2 合法 structlog JSON 但 level=info/warning 的行不得被当错误入库
// （曾因掉进非结构化正则，JSON 内容里 critical/error 子串误命中——all_critical_ok、
// "Error 61 connecting"、event 文案 CRITICAL——把启动 INFO 噪音抓成错误事件）。
func TestClassifyLogLine_RejectsInfoWarningJSON(t *testing.T) {
	cases := []string{
		// 真实噪音行 1：all_critical_ok 含 critical 子串
		`{"summary": {"all_critical_ok": true, "failed": [], "degraded": ["Redis"], "checked": 3}, "event": "startup_dependency_check_ok", "trace_id": "7753157e", "logger": "main", "level": "info", "timestamp": "2026-09-09T18:05:56.310918Z"}`,
		// 真实噪音行 2：detail 里 "Error 61 connecting" + level=warning
		`{"dependency": "Redis", "detail": "连接失败: Error 61 connecting to 127.0.0.1:6379. Connection refused.（将降级为内存缓存，见 cache_factory）", "event": "dependency_check_degraded", "trace_id": "7753157e", "logger": "infrastructure.diagnostics.dependency_check", "level": "warning", "timestamp": "2026-09-09T18:05:56.310502Z"}`,
		// 真实噪音行 3：event 文案含大写 CRITICAL + level=info
		`{"event": "✅ CRITICAL routes: 4/4 (all must succeed)", "trace_id": "7753157e", "logger": "main", "level": "info", "timestamp": "2026-09-09T18:05:52.027080Z"}`,
		// level=debug
		`{"event": "debug line", "logger": "main", "level": "debug"}`,
		// 纯文本 INFO 前缀
		`INFO:uvicorn:Application startup complete.`,
		`2026-09-09 18:05:52 INFO     main: routes registered successfully`,
		// 启动 banner（无 level，含 exception/error 词但非错误）
		`Exception handlers registered successfully`,
		`Agent OS 结构化错误上报已启用 → http://127.0.0.1:8080/api/v1/scheduler/error-events`,
		// 事件 363337b4 回归：v2 决策打分空跑的纯文本汇总行，只含 'errors': 0，
		// 曾被 v2ErrRe 的 error 子串误采为 error 事件（9-10 共 19 次）
		`决策打分完成: {'scanned': 0, 'scored': 0, 'skipped_unmature': 0, 'skipped_invalid': 0, 'errors': 0}`,
		`决策打分完成: {'scanned': 0, 'scored': 0, 'errors': 0}`,
		`batch summary: processed=12 error_count: 0 failed: 0`,
		`任务完成: 失败=0 errors=0`,
	}
	for _, ln := range cases {
		if msg, ok := classifyLogLine(ln, "v2"); ok {
			t.Errorf("info/warning 行被误收为 error: ok=true msg=%q line=%s", msg, ln)
		}
	}
}

// 真 error 级 JSON / 文本必须照常入库
func TestClassifyLogLine_AcceptsError(t *testing.T) {
	cases := []string{
		`{"event": "akshare failed", "logger": "main", "level": "error", "error": "stock_margin_detail_sse() got an unexpected keyword"}`,
		`{"event": "boom", "logger": "worker", "level": "critical", "error": "panic in goroutine"}`,
		`2026-09-10 02:06:11 ERROR    main: Task 251 not found in scheduler_tasks`,
		`Traceback (most recent call last):`,
		// 非 0 计数不得被剥：真失败仍要入库
		`决策打分失败 errors=3 scanned=5`,
		`batch summary: processed=12 errors=2`,
	}
	for _, ln := range cases {
		msg, ok := classifyLogLine(ln, "v2")
		if !ok {
			t.Errorf("真 error 行被漏收: line=%s", ln)
			continue
		}
		if msg == "" {
			t.Errorf("msg 为空: line=%s", ln)
		}
	}
}

// 稳定 msg：同源同错误指纹稳定（去重依赖），不得含 timestamp/trace_id 等易变字段
func TestClassifyLogLine_StableMsg(t *testing.T) {
	ln := `{"event": "boom", "logger": "job.worker", "level": "error", "error": "connection refused", "trace_id": "abc123", "timestamp": "2026-09-10T02:00:00Z"}`
	msg, ok := classifyLogLine(ln, "v2")
	if !ok {
		t.Fatal("error 级应收")
	}
	if strings.Contains(msg, "abc123") || strings.Contains(msg, "02:00:00") {
		t.Errorf("msg 含易变字段 trace_id/timestamp: %q", msg)
	}
	if !strings.Contains(msg, "connection refused") {
		t.Errorf("msg 应含 error 主体: %q", msg)
	}
}
