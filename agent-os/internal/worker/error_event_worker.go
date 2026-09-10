package worker

import (
	"bufio"
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"sync"
	"time"

	"github.com/pi-investment/agent-os/internal/domain"
	"github.com/pi-investment/agent-os/internal/logger"
	"github.com/pi-investment/agent-os/internal/repository"
	"github.com/robfig/cron/v3"
)

// LogTarget 日志采集目标
type LogTarget struct {
	Source string // os / v2 / dsh
	Path   string // 日志文件绝对路径
}

// ErrorEventWorker 错误事件收集 worker（REQ-a42aa4）
// 职责：
//
//	① source=os：扫描 task_runs 中 failed/timeout 执行记录（executor 已把错误落库，
//	   此处轮询聚合，天然覆盖重试后的最终失败，无需侵入 executor）；
//	② source=v2/os/dsh：tail 三端日志，正则提取 error 级行，指纹去重写入。
//
// 处置（claim/resolve/ignore/reopen）走 HTTP API，本 worker 只收集。
type ErrorEventWorker struct {
	repo    repository.ErrorEventRepository
	db      *sql.DB
	targets []LogTarget
	cron    *cron.Cron

	mu           sync.Mutex
	offsets      map[string]int64 // 各日志文件已读偏移（持久化到 statePath；重启不再回扫重复行）
	statePath    string           // 偏移持久化文件路径（空=仅进程内维护）
	lastTaskScan time.Time        // task_runs 水位（随 statePath 持久化；仅首次运行回退 30 分钟）
}

// taskFailureRow 一次失败执行记录
type taskFailureRow struct {
	TaskID     string
	TaskName   string
	Error      string
	Status     string
	FinishedAt time.Time
}

// NewErrorEventWorker 创建错误事件收集 worker。db 用于扫描 task_runs。
// targets 为空时使用 defaultLogTargets()（三端日志）。
func NewErrorEventWorker(db *sql.DB, repo repository.ErrorEventRepository, targets []LogTarget) *ErrorEventWorker {
	if len(targets) == 0 {
		targets = defaultLogTargets()
	}
	w := &ErrorEventWorker{
		repo:      repo,
		db:        db,
		targets:   targets,
		cron:      cron.New(),
		offsets:   map[string]int64{},
		statePath: offsetsStatePath(targets),
	}
	w.loadState()
	return w
}

// Start 启动 worker（每 60s 收集一次）
func (w *ErrorEventWorker) Start() error {
	_, err := w.cron.AddFunc("@every 1m", func() {
		ctx, cancel := context.WithTimeout(context.Background(), 50*time.Second)
		defer cancel()
		if err := w.Collect(ctx); err != nil {
			logger.L().Error("Error event worker collect failed", logger.String("error", err.Error()))
		}
	})
	if err != nil {
		return fmt.Errorf("failed to schedule error event collect job: %w", err)
	}
	w.cron.Start()
	logger.L().Info("Error event worker started (os task failures + v2/os/dsh log errors every 1 min)")
	return nil
}

// Stop 停止 worker
func (w *ErrorEventWorker) Stop() {
	w.cron.Stop()
	logger.L().Info("Error event worker stopped")
}

// Collect 执行一轮收集：os task_runs 失败 + 三端日志错误行
func (w *ErrorEventWorker) Collect(ctx context.Context) error {
	var firstErr error
	if err := w.collectTaskFailures(ctx); err != nil {
		firstErr = err
		logger.L().Error("collectTaskFailures failed", logger.String("error", err.Error()))
	}
	if err := w.collectLogTail(ctx); err != nil && firstErr == nil {
		firstErr = err
	}
	return firstErr
}

// collectTaskFailures 扫描 task_runs 中 failed/timeout 执行记录
func (w *ErrorEventWorker) collectTaskFailures(ctx context.Context) error {
	since := w.lastTaskScan
	if since.IsZero() {
		since = time.Now().Add(-30 * time.Minute)
	}
	rows, err := w.scanFailedTaskRuns(ctx, since)
	if err != nil {
		return fmt.Errorf("failed to scan failed task runs: %w", err)
	}
	if len(rows) == 0 {
		return nil
	}
	maxFinished := since
	for _, r := range rows {
		if r.FinishedAt.After(maxFinished) {
			maxFinished = r.FinishedAt
		}
		if strings.TrimSpace(r.Error) == "" {
			continue
		}
		msg := firstErrorLine(r.Error)
		fp := repository.FingerprintOf(string(domain.ErrorSourceOS), r.TaskID, msg)
		_, _, err := w.repo.Upsert(ctx, domain.ErrorEventUpsertInput{
			Source:      string(domain.ErrorSourceOS),
			TaskID:      r.TaskID,
			TaskName:    r.TaskName,
			Level:       "error",
			Msg:         msg,
			Detail:      truncate(r.Error, 2000),
			Fingerprint: fp,
			Metadata: map[string]interface{}{
				"run_status":      r.Status,
				"finished_at":     r.FinishedAt.UTC().Format(time.RFC3339),
				"collect_channel": "task_runs",
			},
		})
		if err != nil {
			logger.L().Error("Failed to upsert os error event", logger.String("task_id", r.TaskID), logger.String("error", err.Error()))
		}
	}
	w.lastTaskScan = maxFinished
	w.persistState() // 水位一并持久化，重启后不再重扫历史失败
	return nil
}

// collectLogTail 增量 tail 三端日志
func (w *ErrorEventWorker) collectLogTail(ctx context.Context) error {
	for _, t := range w.targets {
		if err := w.tailOne(ctx, t); err != nil {
			logger.L().Error("Log tail failed", logger.String("source", t.Source), logger.String("path", t.Path), logger.String("error", err.Error()))
		}
	}
	return nil
}

const tailWindow = 256 * 1024 // 重启后回扫窗口：只处理末 256KB，避免重扫超大文件

func (w *ErrorEventWorker) tailOne(ctx context.Context, t LogTarget) error {
	f, err := os.Open(t.Path)
	if err != nil {
		if os.IsNotExist(err) {
			return nil // 文件不存在不算错误
		}
		return err
	}
	defer f.Close()

	info, err := f.Stat()
	if err != nil {
		return err
	}
	size := info.Size()

	w.mu.Lock()
	offset := resolveOffset(w.offsets, t.Path, size)
	if offset >= size {
		w.mu.Unlock()
		return nil // 无新增
	}
	if _, err := f.Seek(offset, 0); err != nil {
		w.mu.Unlock()
		return err
	}
	w.offsets[t.Path] = size // 先推进游标，防止同一行被下一轮重复处理
	w.mu.Unlock()
	w.persistState() // 落盘：重启后不再回扫已处理过的历史行

	scanner := bufio.NewScanner(f)
	scanner.Buffer(make([]byte, 0, 64*1024), 1024*1024)
	pending := []string{}
	for scanner.Scan() {
		line := strings.TrimRight(scanner.Text(), "\r\n")
		if line == "" {
			continue
		}
		pending = append(pending, line)
		if len(pending) >= 200 {
			w.processLines(ctx, t, pending)
			pending = nil
		}
	}
	if len(pending) > 0 {
		w.processLines(ctx, t, pending)
	}
	return scanner.Err()
}

// processLines 对一批新行做 error 提取与 upsert
func (w *ErrorEventWorker) processLines(ctx context.Context, t LogTarget, lines []string) {
	if t.Source == string(domain.ErrorSourceOS) {
		// os：zap JSON 结构化；跳过 Task execution failed/timeout（task_runs 已聚合）
		for _, ln := range lines {
			msg, ok := parseZapErrorLine(ln)
			if !ok {
				continue
			}
			if strings.Contains(msg, "Task execution failed") || strings.Contains(msg, "Task execution timeout") {
				continue
			}
			fp := repository.FingerprintOf(string(domain.ErrorSourceOS), "", msg)
			_, _, err := w.repo.Upsert(ctx, domain.ErrorEventUpsertInput{
				Source:      string(domain.ErrorSourceOS),
				Level:       "error",
				Msg:         msg,
				Detail:      truncate(ln, 2000),
				Fingerprint: fp,
				Metadata:    map[string]interface{}{"collect_channel": "log_tail", "log_path": t.Path},
			})
			if err != nil {
				logger.L().Error("Failed to upsert os log error event", logger.String("error", err.Error()))
			}
		}
		return
	}
	// v2/dsh：优先结构化 JSON（稳定 msg/指纹）。合法 JSON 只收 error 级，
	// 非 error 级 JSON 直接跳过——不得掉进非结构化正则（JSON 内容里的
	// error/critical 子串会误命中：all_critical_ok、detail 里 "Error 61
	// connecting"、event 文案 CRITICAL，曾把 v2 启动 INFO/warning 当错误入库）。
	// 决策逻辑收敛在 classifyLogLine（纯函数，见 error_event_worker_test.go 回归用例）。
	for _, ln := range lines {
		msg, ok := classifyLogLine(ln, t.Source)
		if !ok {
			continue
		}
		fp := repository.FingerprintOf(t.Source, "", msg)
		_, _, err := w.repo.Upsert(ctx, domain.ErrorEventUpsertInput{
			Source:      t.Source,
			Level:       "error",
			Msg:         msg,
			Detail:      truncate(ln, 2000),
			Fingerprint: fp,
			Metadata:    map[string]interface{}{"collect_channel": "log_tail", "log_path": t.Path},
		})
		if err != nil {
			logger.L().Error("Failed to upsert log error event", logger.String("source", t.Source), logger.String("error", err.Error()))
		}
	}
}

// startupBannerRe 启动/常规 banner 白名单：无 level 前缀的纯文本行即使含
// error/exception 词（FastAPI "Exception handlers registered successfully"、
// reporter 启用行里的 error-events URL）也不是错误，直接跳过。
var startupBannerRe = regexp.MustCompile(`(?i)(registered successfully|startup complete|Application startup complete|Uvicorn running|Agent OS 结构化错误上报已启用)`)

// zeroErrorMetricRe 取值为 0 的"错误计数"字段：{'errors': 0} / failed=0 / error_count: 0 / 失败=0。
// 这类"零失败汇总行"本身不是错误——判定前先在探针副本里剥掉，否则裸子串
// v2ErrRe 会把汇总行里的 error 字样当错误。回归事件 363337b4：v2 daily_orchestrator
// 每次 REVIEW 阶段都打 "决策打分完成: {'scanned': 0, ..., 'errors': 0}"，
// 9-10 一天被误采 19 次（0 扫描空跑的 INFO 行）。
// 只剥"为 0"的字段：非 0 计数（errors=3）与行内真正的 level 前缀（[error]/ERROR）不受影响。
var zeroErrorMetricRe = regexp.MustCompile(`(?i)(['"]?(?:errors?|error_count|exceptions?|failures?|failed_count)['"]?\s*[:=]\s*0\b|失败\s*[:=]\s*0\b)`)

// tracebackContinuationRe 纯 traceback 续行：栈帧源码回显/收尾提示，本身不含根因，
// 单独采集成事件只会污染板面（真正有意义的是 traceback 末尾的异常类型+消息行，
// 由 v2ErrRe 单独采集）。
// 取证（2026-09-10 事件族快照，w-8f2c4cc5）：一次 SQLAlchemy 连接异常在 log_tail 通道被
// 逐行切碎成 8 个事件族共 91 次上报（raise translated_error from error /
// self._handle_exception(error) / self._adapt_connection._handle_exception(error) /
// self._handle_dbapi_exception( / raise sqlalchemy_exception.with_traceback(exc_info[2]) from e /
// File "<path>/sqlalchemy/engine/base.py", line ... / raise HTTPStatusError(message, request=..., response=...) /
// (Background on this error at: https://sqlalche.me/e/20/f405)），每个族的指纹都不同，
// 去重完全失效。只滤"续行"，不滤 "Traceback (most recent call last):" 首行
// （保留 traceback 锚点，回归用例 TestClassifyLogLine_AcceptsError 仍覆盖该行）。
var tracebackContinuationRe = regexp.MustCompile(`^(?:raise\s+[\w\.]+|self\.[\w\.]+\(|File "|During handling of the above exception|\(Background on this error at:)`)

// classifyLogLine 判定单行 v2/dsh 日志是否应收为 error 事件并提取稳定 msg。
// 合法结构化 JSON：parseStructuredLogLine 内按 level 白名单（error/fatal/critical/exception）
// 判定，非 error 级返回 false——绝不拿 JSON 内容去跑非结构化正则。
// 非 JSON 文本行：先排除启动/常规 banner，再按 error 级正则（errorLineRe）匹配后剥前缀。
func classifyLogLine(ln, source string) (string, bool) {
	trimmed := strings.TrimSpace(ln)
	if strings.HasPrefix(trimmed, "{") {
		return parseStructuredLogLine(ln)
	}
	if startupBannerRe.MatchString(ln) {
		return "", false
	}
	// traceback 续行（栈帧回显）单独成事件无信息量，见 tracebackContinuationRe 注释
	if tracebackContinuationRe.MatchString(trimmed) {
		return "", false
	}
	re := errorLineRe(source)
	// 剥掉零值错误计数后再判定（见 zeroErrorMetricRe 注释）
	if !re.MatchString(zeroErrorMetricRe.ReplaceAllString(ln, "")) {
		return "", false
	}
	return stripLogPrefix(ln), true
}

// --- 解析辅助 ---

// parseZapErrorLine 解析 agent-os zap JSON 日志行，返回 (msg, 是否 error 级)
func parseZapErrorLine(line string) (string, bool) {
	var entry struct {
		Level string `json:"level"`
		Msg   string `json:"msg"`
	}
	if err := json.Unmarshal([]byte(line), &entry); err != nil {
		return "", false
	}
	if entry.Level == "" || entry.Msg == "" {
		return "", false
	}
	switch entry.Level {
	case "error", "fatal", "critical", "panic", "dpanic":
		return entry.Msg, true
	default:
		return "", false
	}
}

// parseStructuredLogLine 解析 v2/dsh 的结构化 JSON 日志行（Python logging / structlog 等）。
// 返回 (稳定 msg, 是否 error 级)。msg 只取 event/msg/error 等稳定字段 + logger，
// 丢弃 timestamp/session_id/thread_id 等易变字段，保证同源错误指纹稳定可去重。
func parseStructuredLogLine(line string) (string, bool) {
	trimmed := strings.TrimSpace(line)
	if trimmed == "" || !strings.HasPrefix(trimmed, "{") {
		return "", false
	}
	var rec struct {
		Level   string `json:"level"`
		Event   string `json:"event"`
		Msg     string `json:"msg"`
		Message string `json:"message"`
		Error   string `json:"error"`
		Logger  string `json:"logger"`
	}
	if err := json.Unmarshal([]byte(trimmed), &rec); err != nil {
		return "", false
	}
	if rec.Level == "" {
		return "", false
	}
	switch strings.ToLower(rec.Level) {
	case "error", "fatal", "critical", "exception":
	default:
		return "", false
	}
	// 组装稳定 msg：优先 error 首行 → event/msg/message → logger 兜底
	msg := rec.Error
	if i := strings.IndexByte(msg, '\n'); i >= 0 {
		msg = msg[:i]
	}
	msg = strings.TrimSpace(msg)
	if msg == "" {
		msg = rec.Event
	}
	if msg == "" {
		msg = rec.Msg
	}
	if msg == "" {
		msg = rec.Message
	}
	if msg == "" {
		msg = rec.Logger
	}
	if msg == "" {
		msg = "structured error"
	}
	if rec.Logger != "" && msg != rec.Error {
		msg = rec.Logger + ": " + msg
	}
	if len(msg) > 300 {
		msg = msg[:300]
	}
	return msg, true
}

var (
	v2ErrRe   = regexp.MustCompile(`(?i)(error|critical|exception|traceback|panic)`)
	dshErrRe  = regexp.MustCompile(`(?i)(error|fatal|critical|exception|panic)`)
	logPrefix = regexp.MustCompile(`^.*?\b(ERROR|CRITICAL|EXCEPTION|PANIC|FATAL|Error)\b\s*[: ]*\s*`)
)

func errorLineRe(source string) *regexp.Regexp {
	if source == string(domain.ErrorSourceV2) {
		return v2ErrRe
	}
	return dshErrRe
}

// firstErrorLine 取错误文本首行作为 msg
func firstErrorLine(s string) string {
	s = strings.TrimSpace(s)
	if i := strings.IndexByte(s, '\n'); i >= 0 {
		s = s[:i]
	}
	if len(s) > 300 {
		s = s[:300]
	}
	return strings.TrimSpace(s)
}

// stripLogPrefix 去掉常见日志前缀，保留核心错误信息
func stripLogPrefix(line string) string {
	msg := logPrefix.ReplaceAllString(line, "")
	if i := strings.Index(msg, "Traceback"); i >= 0 {
		msg = msg[i:]
	}
	if len(msg) > 300 {
		msg = msg[:300]
	}
	msg = strings.TrimSpace(msg)
	if msg == "" {
		msg = truncate(line, 300)
	}
	return msg
}

func truncate(s string, n int) string {
	if len(s) <= n {
		return s
	}
	return s[:n] + "..."
}

// scanFailedTaskRuns 查询自 since 以来失败的 task_runs（关联 tasks 取名称）
func (w *ErrorEventWorker) scanFailedTaskRuns(ctx context.Context, since time.Time) ([]taskFailureRow, error) {
	query := `SELECT tr.task_id::text, COALESCE(t.name, ''), tr.error, tr.status, tr.finished_at
		FROM task_runs tr
		LEFT JOIN tasks t ON t.id = tr.task_id
		WHERE tr.status IN ('failed','timeout') AND tr.error IS NOT NULL AND tr.error <> ''
		  AND tr.finished_at > $1
		ORDER BY tr.finished_at ASC`
	rows, err := w.db.QueryContext(ctx, query, since)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []taskFailureRow
	for rows.Next() {
		var taskID, taskName, errMsg, status string
		var finished time.Time
		if err := rows.Scan(&taskID, &taskName, &errMsg, &status, &finished); err != nil {
			return nil, err
		}
		out = append(out, taskFailureRow{TaskID: taskID, TaskName: taskName, Error: errMsg, Status: status, FinishedAt: finished})
	}
	return out, rows.Err()
}

// defaultLogTargets 默认三端日志采集目标（与本实例部署一致）
// ---------- 日志游标持久化（2026-09-10，w-8f2c4cc5）----------
//
// 背景：offsets 原为纯进程内游标，进程重启后 w.offsets 为空 → tailOne 从
// size-tailWindow 回扫末 256KB 并逐行 Upsert。Upsert 对已 resolved/ignored 的
// 同指纹事件会 reopen（设计如此，用于真"复发"场景），于是每次 agent-os 重启
// 都把历史已关闭的错误当成新发生重新翻开、occurrenceCount 虚增：
// 2026-09-10 23:46 重启后 open 事件由 216 涨到 222、已关闭族 lastSeenAt 被刷新，
// 处置动作被自己的重启撤销（错误看板 4f0f770c / 893a7da3 现场）。
// 修法：把游标持久化到 agent-os/logs/.error_event_offsets.json，重启后接着上次
// 位置读；仅当"首次见到该文件"或"offset>size（轮转/截断）"才回退到末窗口。

const offsetsStateFileName = ".error_event_offsets.json"

// offsetsState 采集游标持久化结构：日志文件偏移 + task_runs 扫描水位。
// 两者都是"重启后必须接着上次位置继续"的游标，缺任何一个都会在重启时把
// 已处置的历史错误当成新发生重新 Upsert（reopen + occurrenceCount 虚增）。
type offsetsState struct {
	Offsets      map[string]int64 `json:"offsets"`
	LastTaskScan time.Time        `json:"last_task_scan,omitempty"`
}

// offsetsStatePath 选一个随日志目录走的稳定位置：优先 os 目标所在目录（agent-os/logs）
func offsetsStatePath(targets []LogTarget) string {
	dir := ""
	for _, t := range targets {
		if t.Source == string(domain.ErrorSourceOS) {
			dir = filepath.Dir(t.Path)
			break
		}
	}
	if dir == "" && len(targets) > 0 {
		dir = filepath.Dir(targets[0].Path)
	}
	if dir == "" {
		return ""
	}
	return filepath.Join(dir, offsetsStateFileName)
}

// resolveOffset 计算本次读取起点（纯函数，回归用）
func resolveOffset(offsets map[string]int64, path string, size int64) int64 {
	win := size - tailWindow
	if win < 0 {
		win = 0
	}
	offset, seen := offsets[path]
	if !seen || offset > size {
		return win
	}
	return offset
}

// loadState 启动时恢复游标（失败只告警，退化为"回扫末窗口"的原行为，不影响采集）
func (w *ErrorEventWorker) loadState() {
	if w.statePath == "" {
		return
	}
	raw, err := os.ReadFile(w.statePath)
	if err != nil {
		if !os.IsNotExist(err) {
			logger.L().Warn("Error event state load failed", logger.String("path", w.statePath), logger.String("error", err.Error()))
		}
		return
	}
	state := offsetsState{}
	if err := json.Unmarshal(raw, &state); err != nil {
		logger.L().Warn("Error event state parse failed", logger.String("path", w.statePath), logger.String("error", err.Error()))
		return
	}
	w.mu.Lock()
	for k, v := range state.Offsets {
		w.offsets[k] = v
	}
	if !state.LastTaskScan.IsZero() {
		w.lastTaskScan = state.LastTaskScan
	}
	w.mu.Unlock()
	logger.L().Info("Error event state restored",
		logger.Int("files", len(state.Offsets)),
		logger.String("last_task_scan", state.LastTaskScan.Format(time.RFC3339)),
		logger.String("path", w.statePath))
}

// persistState 原子落盘（临时文件 + rename）
func (w *ErrorEventWorker) persistState() {
	if w.statePath == "" {
		return
	}
	w.mu.Lock()
	state := offsetsState{Offsets: make(map[string]int64, len(w.offsets)), LastTaskScan: w.lastTaskScan}
	for k, v := range w.offsets {
		state.Offsets[k] = v
	}
	w.mu.Unlock()

	raw, err := json.Marshal(state)
	if err != nil {
		return
	}
	tmp := w.statePath + ".tmp"
	if err := os.WriteFile(tmp, raw, 0644); err != nil {
		logger.L().Warn("Error event offsets persist failed", logger.String("error", err.Error()))
		return
	}
	if err := os.Rename(tmp, w.statePath); err != nil {
		logger.L().Warn("Error event offsets rename failed", logger.String("error", err.Error()))
	}
}

func defaultLogTargets() []LogTarget {
	home, _ := os.UserHomeDir()
	return []LogTarget{
		{Source: string(domain.ErrorSourceV2), Path: "/Users/yunpeng/pi-investment/quantsys-v2/logs/launchd-stderr.log"},
		{Source: string(domain.ErrorSourceV2), Path: "/Users/yunpeng/pi-investment/quantsys-v2/logs/launchd-stdout.log"},
		{Source: string(domain.ErrorSourceOS), Path: "/Users/yunpeng/pi-investment/agent-os/logs/launchd-stderr.log"},
		{Source: string(domain.ErrorSourceDSH), Path: home + "/.dsh-agent-dh/profile-13080.log"},
	}
}
