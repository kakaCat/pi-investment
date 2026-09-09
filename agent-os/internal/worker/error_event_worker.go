package worker

import (
	"bufio"
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"os"
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
	offsets      map[string]int64 // 各日志文件已读偏移（进程内游标；重启回退到末 tailWindow）
	lastTaskScan time.Time        // task_runs 水位（进程内；重启后最多重扫最近 30 分钟）
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
	return &ErrorEventWorker{
		repo:    repo,
		db:      db,
		targets: targets,
		cron:    cron.New(),
		offsets: map[string]int64{},
	}
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
	offset, seen := w.offsets[t.Path]
	if !seen {
		offset = size - tailWindow
		if offset < 0 {
			offset = 0
		}
	} else if offset > size {
		// 日志被轮转/截断：重置到文件尾窗口
		offset = size - tailWindow
		if offset < 0 {
			offset = 0
		}
	}
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
	re := errorLineRe(source)
	if !re.MatchString(ln) {
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
func defaultLogTargets() []LogTarget {
	home, _ := os.UserHomeDir()
	return []LogTarget{
		{Source: string(domain.ErrorSourceV2), Path: "/Users/yunpeng/pi-investment/quantsys-v2/logs/launchd-stderr.log"},
		{Source: string(domain.ErrorSourceV2), Path: "/Users/yunpeng/pi-investment/quantsys-v2/logs/launchd-stdout.log"},
		{Source: string(domain.ErrorSourceOS), Path: "/Users/yunpeng/pi-investment/agent-os/logs/launchd-stderr.log"},
		{Source: string(domain.ErrorSourceDSH), Path: home + "/.dsh-agent-dh/profile-13080.log"},
	}
}
