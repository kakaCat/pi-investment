package scheduler

import (
	"errors"
	"fmt"
	"net"
	"net/url"
	"os"
	"syscall"
	"testing"
	"time"
)

type timeoutErr struct{}

func (timeoutErr) Error() string   { return "i/o timeout" }
func (timeoutErr) Timeout() bool   { return true }
func (timeoutErr) Temporary() bool { return true }

// The real failure seen in production (agent-brain-daily-audit, 2026-09-10 19:00):
// webhook request failed: Post "http://127.0.0.1:13080/agent-os-trigger":
// dial tcp 127.0.0.1:13080: connect: connection refused
func TestIsConnectionFailure(t *testing.T) {
	refused := &url.Error{
		Op:  "Post",
		URL: "http://127.0.0.1:13080/agent-os-trigger",
		Err: &net.OpError{Op: "dial", Net: "tcp", Err: &os.SyscallError{Syscall: "connect", Err: syscall.ECONNREFUSED}},
	}

	cases := []struct {
		name string
		err  error
		want bool
	}{
		{"nil", nil, false},
		{"real connection refused", fmt.Errorf("webhook request failed: %w", refused), true},
		{"bare syscall errno", syscall.ECONNREFUSED, true},
		{"timeout", timeoutErr{}, true},
		{"http 500", errors.New("webhook returned non-2xx status: 500 (body: boom)"), false},
		{"missing endpoint config", errors.New("task has neither webhook_url nor command"), false},
		{"string fallback", errors.New("dial tcp 127.0.0.1:13080: connect: connection refused"), true},
	}
	for _, c := range cases {
		if got := IsConnectionFailure(c.err); got != c.want {
			t.Errorf("IsConnectionFailure(%s) = %v, want %v", c.name, got, c.want)
		}
	}
}

// Regression guard: the retry window must span a service restart (~60s), which
// the previous fixed 5s + 5s window did not.
func TestRetryDelayFor(t *testing.T) {
	refused := errors.New("Post http://127.0.0.1:13080/agent-os-trigger: dial tcp 127.0.0.1:13080: connect: connection refused")
	other := errors.New("webhook returned non-2xx status: 500")

	if got := RetryDelayFor(0, refused, 5*time.Second); got != 0 {
		t.Errorf("first attempt must not sleep, got %v", got)
	}
	if got := RetryDelayFor(1, refused, 5*time.Second); got != 30*time.Second {
		t.Errorf("connection failure attempt 1 = %v, want 30s", got)
	}
	if got := RetryDelayFor(2, refused, 5*time.Second); got != 60*time.Second {
		t.Errorf("connection failure attempt 2 = %v, want 60s", got)
	}
	if got := RetryDelayFor(2, refused, 5*time.Second) + RetryDelayFor(1, refused, 5*time.Second); got < 60*time.Second {
		t.Errorf("total retry window %v is shorter than a service restart", got)
	}
	if got := RetryDelayFor(9, refused, 5*time.Second); got != 2*time.Minute {
		t.Errorf("backoff must be capped at 2m, got %v", got)
	}
	if got := RetryDelayFor(1, other, 7*time.Second); got != 7*time.Second {
		t.Errorf("non-connection failure must keep configured delay, got %v", got)
	}
	if got := RetryDelayFor(1, refused, 0); got != 30*time.Second {
		t.Errorf("zero base must fall back to 5s base, got %v", got)
	}
}
