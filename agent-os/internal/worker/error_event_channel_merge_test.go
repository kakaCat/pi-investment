package worker

import (
	"context"
	"encoding/json"
	"testing"

	"github.com/pi-investment/agent-os/internal/repository"
)

// 回归（2026-09-11, w-8f2c4cc5）：同一异常经两条通道落盘时曾经生成两条看板事件——
// 通道 A（日志文件 structlog JSON 行，Go worker 采集）的指纹取「去易变键后的整段 JSON」，
// 通道 B（Python logging ERROR → agent_os_reporter 上报）的指纹取「带 logger 前缀的文本行」，
// 两者永不相等。实测 00:52 SchedulerService.add_task TypeError：f5341905(JSON 通道 A)
// + 9e7070cc(上报通道 B) + 584abd31(5xx 访问日志)。
//
// 说明：通道 B 的文本行本身不被 worker 采集（v2 纯文本行需命中 error 关键字，中文事件文案
// 不含 error/exception，故 worker 侧无该事件）；两通道归并靠的是「指纹相同」——A 端由 Go
// 计算、B 端由 Python 计算，跨语言一致性由 error_event_crosslang_test.go 的向量保证。
// 本用例锁定 A 端行为：JSON 行取事件文案指纹（= Python 端对带前缀文本行算出的同一值），
// 5xx 访问日志行口径不同（含 HTTP 路径与状态），保持独立事件，不强行归并。
func TestProcessLines_CrossChannelFingerprintParity(t *testing.T) {
	payload := map[string]any{
		"event":     "API错误: SchedulerService.add_task() got an unexpected keyword argument 'task_type'",
		"trace_id":  "95509f30",
		"logger":    "adapters.inbound.fastapi_app.shared",
		"level":     "error",
		"timestamp": "2026-09-10T16:52:06.189571Z",
	}
	raw, err := json.Marshal(payload)
	if err != nil {
		t.Fatalf("构造 JSON 行失败: %v", err)
	}
	lines := []string{
		string(raw), // 通道 A：日志文件里的 structlog JSON 行（worker 采集）
		`INFO:     127.0.0.1:65290 - "POST /api/scheduler/tasks HTTP/1.1" 500 Internal Server Error`, // 通道 C：5xx 访问日志
	}
	repo := &fakeErrorEventRepo{}
	w := &ErrorEventWorker{repo: repo, offsets: map[string]int64{}}
	w.processLines(context.Background(), LogTarget{Source: "v2", Path: "/tmp/v2-crosschannel.log"}, lines)

	if len(repo.fps) != 2 {
		t.Fatalf("应产出 2 条事件（异常行 + 5xx 访问行），实际 %d 条: msgs=%v fps=%v", len(repo.fps), repo.msgs, repo.fps)
	}
	// 该值 = Python 端对「带 logger 前缀的同一事件文本」算出的指纹（见跨语言向量用例），
	// 两通道因此归并到同一条事件。
	const wantExceptionFP = "b48a75eeed631a95d4be041e530b088409644bac"
	if repo.fps[0] != wantExceptionFP {
		t.Errorf("异常行指纹应与 Python 上报通道一致: got %s want %s", repo.fps[0], wantExceptionFP)
	}
	if repo.fps[1] == repo.fps[0] {
		t.Error("5xx 访问日志行不得与异常行归并（口径不同）")
	}
}

// 反向护栏：logger 前缀规则只能剥「模块路径」形态，异常名开头不能被剥。
func TestNormalizeMsg_LoggerPrefixSafety(t *testing.T) {
	if got := repository.NormalizeMsg("TypeError: boom"); got != "TypeError: boom" {
		t.Errorf("异常名开头不得被剥离: %q", got)
	}
	if got := repository.NormalizeMsg("adapters.inbound.fastapi_app.shared: API错误: x"); got != "API错误: x" {
		t.Errorf("模块路径前缀应被剥离: %q", got)
	}
	if repository.NormalizeMsg("adapters.inbound.fastapi_app.shared: API错误: x") !=
		repository.NormalizeMsg("API错误: x") {
		t.Error("剥前缀后必须与裸文案同指纹输入")
	}
}
