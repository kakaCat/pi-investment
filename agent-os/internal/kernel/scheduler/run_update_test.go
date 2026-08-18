package scheduler

import (
	"testing"

	"github.com/pi-investment/agent-os/pkg/types"
)

func TestParseRunStatus(t *testing.T) {
	tests := []struct {
		input   string
		want    types.TaskStatus
		wantOK  bool
	}{
		{"success", types.TaskStatusSuccess, true},
		{"failed", types.TaskStatusFailed, true},
		{"timeout", types.TaskStatusTimeout, true},
		{"canceled", types.TaskStatusCanceled, true},
		{"running", types.TaskStatusRunning, true},
		{"pending", types.TaskStatusPending, true},
		{"bogus", "", false},
		{"", "", false},
		{"SUCCESS", "", false}, // strict: contract is lowercase
	}

	for _, tt := range tests {
		got, ok := parseRunStatus(tt.input)
		if ok != tt.wantOK {
			t.Errorf("parseRunStatus(%q) ok = %v, want %v", tt.input, ok, tt.wantOK)
			continue
		}
		if ok && got != tt.want {
			t.Errorf("parseRunStatus(%q) = %v, want %v", tt.input, got, tt.want)
		}
	}
}

func TestIsTerminalRunStatus(t *testing.T) {
	terminal := []types.TaskStatus{types.TaskStatusSuccess, types.TaskStatusFailed, types.TaskStatusTimeout, types.TaskStatusCanceled}
	for _, s := range terminal {
		if !isTerminalRunStatus(s) {
			t.Errorf("isTerminalRunStatus(%q) = false, want true", s)
		}
	}
	for _, s := range []types.TaskStatus{types.TaskStatusRunning, types.TaskStatusPending} {
		if isTerminalRunStatus(s) {
			t.Errorf("isTerminalRunStatus(%q) = true, want false", s)
		}
	}
}
