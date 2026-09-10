package worker

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

// 回归：v2 合法 structlog JSON 但 level=info/warning 的行不得被当错误入库
// （曾因掉进非结构化正则，JSON 内容里 critical/error 子串误命中——all_critical_ok、
// "Error 61 connecting"、event 文案 CRITICAL——把启动 INFO 噪音抓成错误事件）。
// 回归（2026-09-10，w-8f2c4cc5）：任务汇总行只有在载荷显式标记失败时才收为错误，
// 且真正失败的任务行不得被误滤（保证过滤没有把信号一起滤掉）。
func TestClassifyLogLine_JobSummaryFailureSemantics(t *testing.T) {
	shouldReject := []string{
		`Job 'market_perception_daily' succeeded (run_id=x): {'status': 'success', 'steps': 3, 'failed_steps': []}`,
	}
	for _, ln := range shouldReject {
		if msg, ok := classifyLogLine(ln, "v2"); ok {
			t.Errorf("全绿任务回执行被误收为错误: msg=%q", msg)
		}
	}
	shouldAccept := []string{
		`Job 'market_perception_daily' succeeded (run_id=x): {'success': False, 'error': "'MarketPerceptionService' object has no attribute 'regime_daily'"}`,
		`Job 'filter_a' failed (run_id=y): {'status': 'failed', 'error': 'boom'}`,
	}
	for _, ln := range shouldAccept {
		if _, ok := classifyLogLine(ln, "v2"); !ok {
			t.Errorf("真实失败任务行被误滤: %s", ln)
		}
	}
}

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
		// 事件 764bb312 / c448196b 回归：scheduler_webhook 的 INFO 级任务回执行，载荷里
		// 的键名/空数组（strategy_errors、failed）会误触 v2ErrRe
		`Job 'signal_generate_sell' succeeded (run_id=30a54799-c015-43c4-ae92-d0dcaa593ef4): {'action': 'signal_generate', 'status': 'success', 'universe_size': 142, 'strategy_errors': [], 'signals_saved': 6}`,
		`Job 'pool_refresh_daily' succeeded (run_id=abc): {'action': 'pool_refresh', 'status': 'partial', 'failed': [], 'updated': 12}`,
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

// 回归（2026-09-10，w-8f2c4cc5）：traceback 续行不得单独成事件。
// 现场：一次 SQLAlchemy 连接异常在 log_tail 通道被逐行切碎成 8 个事件族共 91 次上报
// （错误板 62a2ae6f/56a0317c/6f43abae/131ed7ed/ca42d579/f539c83c/053267b0/195d2ff3/3cba07e1），
// 每族指纹不同 → 去重失效，板面被栈帧回显淹没。
func TestClassifyLogLine_RejectsTracebackContinuations(t *testing.T) {
	cases := []string{
		"raise translated_error from error",
		"self._adapt_connection._handle_exception(error)",
		"self._handle_exception(error)",
		"self._handle_dbapi_exception(",
		"raise sqlalchemy_exception.with_traceback(exc_info[2]) from e",
		`  File "/Users/yunpeng/pi-investment/quantsys-v2/venv/lib/python3.13/site-packages/sqlalchemy/engine/base.py", line 1969, in _exec_single_context`,
		"raise HTTPStatusError(message, request=request, response=self)",
		"(Background on this error at: https://sqlalche.me/e/20/f405)",
		"During handling of the above exception, another exception occurred:",
	}
	for _, ln := range cases {
		if msg, ok := classifyLogLine(ln, "v2"); ok {
			t.Errorf("traceback 续行被误收为 error: ok=true msg=%q line=%s", msg, ln)
		}
	}
	// 反向保护：traceback 锚点行与真正的错误行必须照常入库（不得因本次过滤被连带漏收）
	kept := []string{
		"Traceback (most recent call last):",
		"sqlalchemy.exc.OperationalError: connection to server failed",
		"2026-09-10 23:21:26 ERROR    main: raise failed for job filter_a",
	}
	for _, ln := range kept {
		if _, ok := classifyLogLine(ln, "v2"); !ok {
			t.Errorf("真 error 行被漏收: line=%s", ln)
		}
	}
}

// TestResolveOffset_PersistedCursor 回归：重启后不得回扫已处理过的历史行
// （2026-09-10 现场：agent-os 重启回扫末 256KB → open 事件由 216 涨到 222、
// 已 resolved/ignored 的族被 reopen、occurrenceCount 虚增，处置被自己撤销）
func TestResolveOffset_PersistedCursor(t *testing.T) {
	const size = 10 << 20 // 10MB 日志
	offsets := map[string]int64{"/tmp/a.log": size - 1024}

	if got := resolveOffset(offsets, "/tmp/a.log", size); got != size-1024 {
		t.Errorf("已知游标未生效（重启会回扫历史行）: got=%d want=%d", got, size-1024)
	}
	if got := resolveOffset(offsets, "/tmp/new.log", size); got != size-tailWindow {
		t.Errorf("首次见到的文件应只回扫末窗口: got=%d want=%d", got, size-tailWindow)
	}
	if got := resolveOffset(offsets, "/tmp/a.log", 1024); got != 0 {
		t.Errorf("轮转/截断后应回退到末窗口(0): got=%d", got)
	}
	if got := resolveOffset(map[string]int64{}, "/tmp/small.log", 100); got != 0 {
		t.Errorf("小文件起点应为 0 且不得为负: got=%d", got)
	}
}

// TestOffsetsPersistRoundTrip 回归：游标（日志偏移 + task_runs 水位）跨进程持久化与损坏降级
func TestOffsetsPersistRoundTrip(t *testing.T) {
	dir := t.TempDir()
	statePath := filepath.Join(dir, offsetsStateFileName)
	scanWatermark := time.Date(2026, 9, 10, 15, 46, 0, 0, time.UTC)

	w := &ErrorEventWorker{
		offsets:      map[string]int64{"/tmp/a.log": 12345},
		lastTaskScan: scanWatermark,
		statePath:    statePath,
	}
	w.persistState()

	raw, err := os.ReadFile(statePath)
	if err != nil {
		t.Fatalf("状态文件未落盘: %v", err)
	}
	if !strings.Contains(string(raw), "12345") || !strings.Contains(string(raw), "2026-09-10T15:46:00Z") {
		t.Fatalf("状态文件内容异常（偏移与水位都应落盘）: %s", raw)
	}

	// 模拟重启：新 worker 无内存游标，loadState 后应从 12345 继续、水位保持
	restarted := &ErrorEventWorker{offsets: map[string]int64{}, statePath: statePath}
	restarted.loadState()
	if got := resolveOffset(restarted.offsets, "/tmp/a.log", 1<<20); got != 12345 {
		t.Errorf("重启后日志游标未恢复: got=%d want=12345", got)
	}
	if !restarted.lastTaskScan.Equal(scanWatermark) {
		t.Errorf("重启后 task_runs 水位未恢复: got=%v want=%v", restarted.lastTaskScan, scanWatermark)
	}

	// 状态文件损坏：退化为空游标，不得 panic
	if err := os.WriteFile(statePath, []byte("{not json"), 0644); err != nil {
		t.Fatal(err)
	}
	broken := &ErrorEventWorker{offsets: map[string]int64{}, statePath: statePath}
	broken.loadState()
	if len(broken.offsets) != 0 || !broken.lastTaskScan.IsZero() {
		t.Errorf("损坏状态文件应退化为空游标: offsets=%v watermark=%v", broken.offsets, broken.lastTaskScan)
	}

	// statePath 为空（无目标场景）：读写均安全 no-op
	none := &ErrorEventWorker{offsets: map[string]int64{"/tmp/x": 1}}
	none.persistState()
	none.loadState()
}

// TestOffsetsStatePath 回归：状态文件落在 agent-os 日志目录（随日志一起轮转/清理）
func TestOffsetsStatePath(t *testing.T) {
	got := offsetsStatePath([]LogTarget{
		{Source: "v2", Path: "/tmp/v2/logs/out.log"},
		{Source: "os", Path: "/tmp/os/logs/err.log"},
	})
	if got != "/tmp/os/logs/"+offsetsStateFileName {
		t.Errorf("状态文件应落在 os 日志目录: %s", got)
	}
	if offsetsStatePath(nil) != "" {
		t.Error("无目标时应返回空路径")
	}
}
