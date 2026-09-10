package worker

import (
	"context"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/pi-investment/agent-os/internal/domain"
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

// 成功访问日志不得采为错误（2026-09-11 w-f4aa1f6a）
// 实证误报：GET /api/market/perception/panic-index/series 200 —— URL 路径含 "panic"
// 命中 errorLineRe 被收成事件并复发 7 次（事件 1d28d866）。
func TestClassifyLogLine_RejectsSuccessfulAccessLine(t *testing.T) {
	cases := []string{
		`INFO:     127.0.0.1:54841 - "GET /api/market/perception/panic-index/series?days=30 HTTP/1.1" 200 OK`,
		`INFO:     127.0.0.1:54841 - "GET /api/error-events/1d28d866 HTTP/1.1" 200 OK`,
		`INFO:     127.0.0.1:54841 - "POST /api/scheduler/error-events HTTP/1.1" 201 Created`,
		`INFO:     127.0.0.1:54841 - "GET /api/x HTTP/1.1" 304 Not Modified`,
	}
	for _, ln := range cases {
		if msg, ok := classifyLogLine(ln, "v2"); ok {
			t.Errorf("成功访问日志被误采为事件（msg=%q）: line=%s", msg, ln)
		}
	}
}

// 失败的访问日志仍须采集（不能因噎废食）
func TestClassifyLogLine_KeepsFailedAccessLine(t *testing.T) {
	cases := []struct {
		line string
		want bool
	}{
		{`INFO:     127.0.0.1:63159 - "GET /api/signals HTTP/1.1" 500 Internal Server Error`, true},
		{`INFO:     127.0.0.1:63159 - "GET /api/backtest/results HTTP/1.1" 500 Internal Server Error`, true},
		// 4xx 且不含 error 关键字的行本来就不采（既有行为，本次未改）；
		// 本次 guard 只拦 2xx/3xx，故 4xx 含关键字的行必须仍然采集。
		{`INFO:     127.0.0.1:63159 - "GET /api/nope HTTP/1.1" 404 Not Found`, false},
		{`INFO:     127.0.0.1:63159 - "PATCH /api/x HTTP/1.1" 409 Conflict - resource error`, true},
		// 非访问日志行不受影响
		{`2026-09-10 02:06:11 ERROR    main: Task 251 not found in scheduler_tasks`, true},
	}
	for _, c := range cases {
		_, ok := classifyLogLine(c.line, "v2")
		if ok != c.want {
			t.Errorf("访问日志判定错误：want=%v got=%v line=%s", c.want, ok, c.line)
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
		// 2026-09-11 补测（w-8f2c4cc5）：板面实测漏过的 5 类碎片——其中 venv 路径碎片
		// 曾因字符类不含 "/" 而持续漏收（[\w\.\-]* 匹配不到以 / 分隔的路径）
		"i-investment/quantsys-v2/venv/lib/python3.13/site-packages/sqlalchemy/dialects/postgresql/asyncpg.py",
		"from domain.exceptions import (",
		"ys-v2/domain/exceptions.py)",
		"\t\"error\", \"timestamp\": \"2026-09-09T15:05:10.782623Z\"}",
		"The above exception was the direct cause of the following exception:",
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
		// 反向保护：含路径但带时间戳/等级的真实错误行不得被路径类模式连带漏收
		"2026-09-10 10:38 ERROR    kline_sync: backfill failed at /data/kline_sync.py",
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

// 回归（2026-09-11，w-f4aa1f6a）：一次 FastAPI RecursionError traceback 在 log_tail 通道炸成
// 22 条事件，其中 13 条是栈帧回显——FastAPI/Starlette 栈帧函数名（wrap_app_handling_exceptions）
// 含 "exception" 子串，命中 errorLineRe 被误收；每族指纹不同，去重完全失效（板面 1 个根因 = 22 条）。
// 用例逐行固化这 22 行的分类结果：文件里 9 条有效锚点必须收、13 条续行必须拒。
func TestClassifyLogLine_RecursionErrorBurstRegression(t *testing.T) {
	noise := []string{
		`await wrap_app_handling_exceptions(app, request)(scope, receive, send)`,
		`await self.app(scope, receive_or_disconnect, send_no_error)`,
		`await wrap_app_handling_exceptions(self.app, conn)(scope, receive, send)`,
		`|   File "/Users/yunpeng/pi-investment/quantsys-v2/venv/lib/python3.13/site-packages/fastapi/encoders.py", line 341, in jsonable_encoder`,
		`|   File "/Users/yunpeng/pi-investment/quantsys-v2/venv/lib/python3.13/site-packages/starlette/middleware/base.py", line 195, in __call__`,
		`|     raise BaseExceptionGroup(`,
		`|     await wrap_app_handling_exceptions(self.app, conn)(scope, receive, send)`,
		`|     await self.app(scope, receive_or_disconnect, send_no_error)`,
		`| RecursionError: maximum recursion depth exceeded`,
		`| ExceptionGroup: unhandled errors in a TaskGroup (1 sub-exception)`,
		`|         "unhandled errors in a TaskGroup", self._exceptions`,
		`  File "/Users/yunpeng/pi-investment/quantsys-v2/venv/lib/python3.13/site-packages/starlette/middleware/exceptions.py", line 63, in __call__`,
		`       ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^`,
	}
	for _, ln := range noise {
		if msg, ok := classifyLogLine(ln, "v2"); ok {
			t.Errorf("栈帧回显被误收为 error: msg=%q line=%s", msg, ln)
		}
	}
	// 反向保护：真正的错误锚点一个都不能被这次过滤连带漏收
	anchors := []string{
		`ALERT: Unhandled exception - RecursionError: maximum recursion depth exceeded`,
		`RecursionError: maximum recursion depth exceeded`,
		`RecursionError on GET /api/signals`,
		`UNHANDLED EXCEPTION: RecursionError on GET /api/signals`,
		`Exception in ASGI application`,
		`INFO:     127.0.0.1:63159 - "GET /api/signals HTTP/1.1" 500 Internal Server Error`,
		`{"level":"error","logger":"adapters.inbound.fastapi_app.routes.backtest_async","event":"Failed to get backtest results: Object of type BacktestResult is not JSON serializable"}`,
		`{"level":"error","event":"Failed to get backtest results: Object of type BacktestResult is not JSON serializable"}`,
	}
	for _, ln := range anchors {
		if _, ok := classifyLogLine(ln, "v2"); !ok {
			t.Errorf("真 error 锚点被漏收: line=%s", ln)
		}
	}
}

// Glob 目标展开回归（2026-09-11，w-f4aa1f6a W2）：DSH 日志文件名每次自重启都变，
// 固死路径采集必然漏收 → 用 Glob 逐文件独立游标。同时验证 Path 目标原样保留、
// 目录不参与、无匹配不报错。
func TestExpandTargets_GlobAndPath(t *testing.T) {
	dir := t.TempDir()
	for _, n := range []string{"restart-2.log", "restart-1.log"} {
		if err := os.WriteFile(filepath.Join(dir, n), []byte("x\n"), 0644); err != nil {
			t.Fatal(err)
		}
	}
	if err := os.Mkdir(filepath.Join(dir, "restart-3.log"), 0755); err != nil {
		t.Fatal(err)
	}
	picked := expandTargets([]LogTarget{
		{Source: "v2", Path: "/tmp/fixed.log"},
		{Source: "dsh", Glob: filepath.Join(dir, "restart-*.log")},
		{Source: "dsh", Glob: filepath.Join(dir, "none-*.log")},
	})
	if len(picked) != 3 {
		t.Fatalf("应展开为 3 个目标（固定 1 + glob 命中 2），实际 %d: %+v", len(picked), picked)
	}
	if picked[0].Path != "/tmp/fixed.log" {
		t.Errorf("固定路径目标应原样保留: %+v", picked[0])
	}
	if !strings.HasSuffix(picked[1].Path, "restart-1.log") {
		t.Errorf("glob 命中应按路径升序: %+v", picked[1])
	}
	if picked[2].Source != "dsh" || !strings.HasSuffix(picked[2].Path, "restart-2.log") {
		t.Errorf("glob 第二命中异常: %+v", picked[2])
	}
}

// fakeErrorEventRepo 只捕获 Upsert 入参，用于驱动 processLines 的续行聚合分支
type fakeErrorEventRepo struct {
	msgs    []string
	details []string
}

func (f *fakeErrorEventRepo) Upsert(ctx context.Context, in domain.ErrorEventUpsertInput) (*domain.ErrorEvent, bool, error) {
	f.msgs = append(f.msgs, in.Msg)
	f.details = append(f.details, in.Detail)
	return &domain.ErrorEvent{ID: "fake"}, false, nil
}

func (f *fakeErrorEventRepo) List(ctx context.Context, req domain.ErrorEventListRequest) ([]*domain.ErrorEvent, int, error) {
	return nil, 0, nil
}

func (f *fakeErrorEventRepo) GetByID(ctx context.Context, id string) (*domain.ErrorEvent, error) {
	return nil, nil
}

func (f *fakeErrorEventRepo) ApplyAction(ctx context.Context, id string, req domain.ErrorEventActionRequest) (*domain.ErrorEvent, string, error) {
	return nil, "", nil
}

func (f *fakeErrorEventRepo) Stats(ctx context.Context) (*domain.ErrorEventStats, error) {
	return nil, nil
}

// 续行聚合回归：栈帧回显不单独成事件，但必须并进紧随其后的错误锚点 Detail——
// 只滤不并会把根因的调用链丢光（过滤把信号一起滤掉，比噪音更糟）。
func TestProcessLines_AggregatesTracebackIntoAnchor(t *testing.T) {
	repo := &fakeErrorEventRepo{}
	w := &ErrorEventWorker{repo: repo, offsets: map[string]int64{}}
	lines := []string{
		`Traceback (most recent call last):`,
		`  File "/Users/x/venv/lib/python3.13/site-packages/starlette/middleware/exceptions.py", line 63, in __call__`,
		`    await wrap_app_handling_exceptions(app, request)(scope, receive, send)`,
		`       ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^`,
		`RecursionError: maximum recursion depth exceeded`,
	}
	w.processLines(context.Background(), LogTarget{Source: "v2", Path: "/tmp/v2-test.log"}, lines)
	if len(repo.msgs) != 2 {
		t.Fatalf("应只产出 2 条锚点事件（Traceback 头 + RecursionError），实际 %d 条: %v", len(repo.msgs), repo.msgs)
	}
	last := repo.details[len(repo.details)-1]
	if !strings.Contains(last, "wrap_app_handling_exceptions") {
		t.Errorf("锚点 Detail 未聚合栈帧（调用链丢失）: %q", last)
	}
	if !strings.Contains(last, "RecursionError") {
		t.Errorf("锚点 Detail 应含错误行: %q", last)
	}
}
