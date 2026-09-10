package repository

import (
	"strings"
	"testing"
)

// P0 指纹归一化（2026-09-10 w-f4aa1f6a）：同根因不同易变段 → 同指纹；不同根因 → 不同指纹。
func TestFingerprintOf_NormalizesVolatileSegments(t *testing.T) {
	m1 := `{"pool_name":"default","error":"ThreadPoolExecutor.shutdown() got an unexpected keyword argument 'timeout'","event":"failed_to_shutdown_pool","trace_id":"7753157e","logger":"infrastructure.threading.thread_pool","timestamp":"2026-09-09T18:41:07.593580Z"}`
	m2 := `{"pool_name":"default","error":"ThreadPoolExecutor.shutdown() got an unexpected keyword argument 'timeout'","event":"failed_to_shutdown_pool","trace_id":"45ab6233","logger":"infrastructure.threading.thread_pool","timestamp":"2026-09-10T02:11:22.000000Z"}`
	m3 := `{"pool_name":"default","error":"Connection refused","event":"db_connect_failed","trace_id":"7753157e","timestamp":"2026-09-09T18:41:07Z"}`

	if FingerprintOf("v2", "", m1) != FingerprintOf("v2", "", m2) {
		t.Fatal("同根因不同 trace_id/timestamp 应同指纹")
	}
	if FingerprintOf("v2", "", m1) == FingerprintOf("v2", "", m3) {
		t.Fatal("不同根因应不同指纹")
	}
	if FingerprintOf("v2", "t1", m1) == FingerprintOf("v2", "t2", m1) {
		t.Fatal("task_id 应参与指纹")
	}
}

func TestNormalizeMsg_Text(t *testing.T) {
	a := NormalizeMsg("req 550e8400-e29b-41d4-a716-446655440000 at 2026-09-10T03:00:00 failed")
	b := NormalizeMsg("req 6ba7b810-9dad-11d1-80b4-00c04fd430c8 at 2026-09-11T09:00:00 failed")
	if a != b {
		t.Fatalf("uuid/ts 归一不一致: %q vs %q", a, b)
	}
}

func TestNormalizeMsg_JSONKeepsSemanticKeys(t *testing.T) {
	n := NormalizeMsg(`{"error":"boom","event":"x_failed","trace_id":"abc12345","timestamp":"2026-09-09T00:00:00Z"}`)
	if !strings.Contains(n, "boom") || !strings.Contains(n, "x_failed") {
		t.Fatalf("归一应保留 error/event: %s", n)
	}
	if strings.Contains(n, "abc12345") {
		t.Fatalf("归一应删 trace_id: %s", n)
	}
}

// P1 note 必填校验（2026-09-10 w-f4aa1f6a）
func TestValidateActionNote(t *testing.T) {
	cases := []struct {
		action, note string
		wantErr      bool
	}{
		{"resolve", "", true},
		{"resolve", "已解决", true},            // 空话：3 字 < 10
		{"resolve", "根因=x;动作=y", true},     // 9 字仍不足
		{"resolve", "根因=3.13移除timeout；动作=改cancel_futures；证据=pytest过", false},
		{"ignore", "", true},
		{"ignore", "误报，无需处理", true},     // 8 字不足
		{"ignore", "误报：该告警源自测试环境数据，线上无影响", false},
		{"claim", "", false},                   // claim 不要求 note
		{"reopen", "", false},                  // reopen 不要求 note
	}
	for _, c := range cases {
		err := validateActionNote(c.action, c.note)
		if (err != nil) != c.wantErr {
			t.Errorf("validateActionNote(%q, %q) err=%v, wantErr=%v", c.action, c.note, err, c.wantErr)
		}
	}
}
