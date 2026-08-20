package scheduler

import (
	"context"
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"sync/atomic"
	"testing"
	"time"

	"github.com/pi-investment/agent-os/pkg/types"
)

func TestServiceManager_HealthyServiceNotStarted(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	}))
	defer server.Close()

	m := NewServiceManager(nil)
	m.RegisterService("test-svc", types.ServiceDefinition{
		HealthURL: server.URL + "/health",
	})

	started, err := m.EnsureRunning(context.Background(), "test-svc")
	if err != nil {
		t.Fatalf("expected no error, got %v", err)
	}
	if started {
		t.Fatal("expected started=false for an already-healthy service")
	}
}

func TestServiceManager_UnknownService(t *testing.T) {
	m := NewServiceManager(nil)

	_, err := m.EnsureRunning(context.Background(), "no-such-service")
	if err == nil {
		t.Fatal("expected error for unregistered service")
	}
}

func TestServiceManager_DownWithoutStartCommand(t *testing.T) {
	// Nothing listens on this URL.
	m := NewServiceManager(nil)
	m.RegisterService("dead-svc", types.ServiceDefinition{
		HealthURL: "http://127.0.0.1:1/health",
	})

	_, err := m.EnsureRunning(context.Background(), "dead-svc")
	if err == nil {
		t.Fatal("expected error when service is down and no start command is configured")
	}
}

func TestServiceManager_StartsDownService(t *testing.T) {
	// Health endpoint starts failing, then flips to healthy once the start
	// command has been executed.
	var healthy atomic.Bool
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if healthy.Load() {
			w.WriteHeader(http.StatusOK)
			return
		}
		w.WriteHeader(http.StatusServiceUnavailable)
	}))
	defer server.Close()

	marker := filepath.Join(t.TempDir(), "started.marker")

	m := NewServiceManager(nil)
	m.RegisterService("flaky-svc", types.ServiceDefinition{
		HealthURL:             server.URL + "/health",
		StartCommand:          "touch " + marker,
		StartupTimeoutSeconds: 20,
	})
	m.startFunc = func(def types.ServiceDefinition) error {
		if err := os.WriteFile(marker, []byte("started"), 0o644); err != nil {
			return err
		}
		healthy.Store(true)
		return nil
	}

	started, err := m.EnsureRunning(context.Background(), "flaky-svc")
	if err != nil {
		t.Fatalf("expected no error, got %v", err)
	}
	if !started {
		t.Fatal("expected started=true when the service had to be started")
	}
	if _, err := os.Stat(marker); err != nil {
		t.Fatalf("expected start command to run, marker missing: %v", err)
	}
}

func TestServiceManager_StartTimeout(t *testing.T) {
	// Health endpoint never becomes healthy.
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusServiceUnavailable)
	}))
	defer server.Close()

	m := NewServiceManager(nil)
	m.RegisterService("stuck-svc", types.ServiceDefinition{
		HealthURL:             server.URL + "/health",
		StartCommand:          "true",
		StartupTimeoutSeconds: 3,
	})
	m.startFunc = func(def types.ServiceDefinition) error { return nil }

	start := time.Now()
	_, err := m.EnsureRunning(context.Background(), "stuck-svc")
	if err == nil {
		t.Fatal("expected timeout error when service never becomes healthy")
	}
	if elapsed := time.Since(start); elapsed > 10*time.Second {
		t.Fatalf("expected timeout around 3s, took %v", elapsed)
	}
}

func TestServiceManager_StartFailurePropagates(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusServiceUnavailable)
	}))
	defer server.Close()

	m := NewServiceManager(nil)
	m.RegisterService("bad-start", types.ServiceDefinition{
		HealthURL:    server.URL + "/health",
		StartCommand: "anything",
	})
	m.startFunc = func(def types.ServiceDefinition) error {
		return fmt.Errorf("boom")
	}

	_, err := m.EnsureRunning(context.Background(), "bad-start")
	if err == nil {
		t.Fatal("expected start failure to propagate")
	}
}

func TestServiceManager_DefaultsRegistered(t *testing.T) {
	m := NewServiceManager(nil)
	if _, ok := m.GetService("quantsys-v2"); !ok {
		t.Fatal("expected built-in quantsys-v2 service definition")
	}

	// Overrides by name win over defaults.
	m2 := NewServiceManager(map[string]types.ServiceDefinition{
		"quantsys-v2": {HealthURL: "http://example.com/health"},
	})
	def, _ := m2.GetService("quantsys-v2")
	if def.HealthURL != "http://example.com/health" {
		t.Fatalf("expected override to win, got %s", def.HealthURL)
	}
}
