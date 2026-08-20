package scheduler

import (
	"context"
	"fmt"
	"net/http"
	"os"
	"os/exec"
	"sync"
	"syscall"
	"time"

	"github.com/pi-investment/agent-os/pkg/logger"
	"github.com/pi-investment/agent-os/pkg/types"
)

const (
	defaultStartupTimeout  = 60 * time.Second
	defaultHealthCheckHTTP = 5 * time.Second
	healthPollInterval     = 2 * time.Second
)

// ServiceManager knows how to health-check and start the local services a
// scheduled task can bind to (e.g. quantsys-v2). When a bound task fires
// while its service is down, the manager starts the service and waits until
// it reports healthy before letting the task execute.
type ServiceManager struct {
	services map[string]types.ServiceDefinition
	client   *http.Client

	// mu guards startLocks; startLocks serializes concurrent start attempts
	// per service so several tasks bound to the same service don't race.
	mu         sync.Mutex
	startLocks map[string]*sync.Mutex

	// startFunc is replaceable in tests; it must launch the command detached.
	startFunc func(def types.ServiceDefinition) error
}

// NewServiceManager creates a ServiceManager. The provided definitions
// override the built-in defaults by name; pass nil to use only defaults.
func NewServiceManager(overrides map[string]types.ServiceDefinition) *ServiceManager {
	services := DefaultServiceDefinitions()
	for name, def := range overrides {
		services[name] = def
	}

	m := &ServiceManager{
		services:   services,
		client:     &http.Client{Timeout: defaultHealthCheckHTTP},
		startLocks: make(map[string]*sync.Mutex),
	}
	m.startFunc = m.startDetached
	return m
}

// DefaultServiceDefinitions returns the built-in service registry. Values
// can be overridden via environment variables or config.yaml (services:).
func DefaultServiceDefinitions() map[string]types.ServiceDefinition {
	healthURL := os.Getenv("QUANTSYS_V2_HEALTH_URL")
	if healthURL == "" {
		base := os.Getenv("QUANTSYS_V2_API_URL")
		if base == "" {
			base = "http://127.0.0.1:5001"
		}
		healthURL = base + "/health"
	}

	startCommand := os.Getenv("QUANTSYS_V2_START_COMMAND")
	if startCommand == "" {
		startCommand = "python adapters/inbound/fastapi_app/main.py"
	}

	workDir := os.Getenv("QUANTSYS_V2_DIR")
	if workDir == "" {
		workDir = "../quantsys-v2" // relative to the agent-os working directory
	}

	return map[string]types.ServiceDefinition{
		"quantsys-v2": {
			HealthURL:             healthURL,
			StartCommand:          startCommand,
			WorkDir:               workDir,
			StartupTimeoutSeconds: 90,
		},
	}
}

// RegisterService adds or replaces a service definition at runtime.
func (m *ServiceManager) RegisterService(name string, def types.ServiceDefinition) {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.services[name] = def
}

// GetService returns the definition for a registered service.
func (m *ServiceManager) GetService(name string) (types.ServiceDefinition, bool) {
	m.mu.Lock()
	defer m.mu.Unlock()
	def, ok := m.services[name]
	return def, ok
}

// ListServices returns a copy of the service registry.
func (m *ServiceManager) ListServices() map[string]types.ServiceDefinition {
	m.mu.Lock()
	defer m.mu.Unlock()
	out := make(map[string]types.ServiceDefinition, len(m.services))
	for k, v := range m.services {
		out[k] = v
	}
	return out
}

// IsHealthy reports whether the named service currently answers its health
// endpoint with a 2xx status. Unknown services report an error.
func (m *ServiceManager) IsHealthy(ctx context.Context, name string) (bool, error) {
	def, ok := m.GetService(name)
	if !ok {
		return false, fmt.Errorf("service %q is not registered", name)
	}
	return m.checkHealth(ctx, def), nil
}

// EnsureRunning makes sure the named service is healthy, starting it via its
// configured start command when necessary. It returns started=true when the
// service had to be (re)started during this call.
func (m *ServiceManager) EnsureRunning(ctx context.Context, name string) (bool, error) {
	def, ok := m.GetService(name)
	if !ok {
		return false, fmt.Errorf("service %q is not registered", name)
	}
	if def.HealthURL == "" {
		return false, fmt.Errorf("service %q has no health_url configured", name)
	}

	if m.checkHealth(ctx, def) {
		return false, nil
	}

	if def.StartCommand == "" {
		return false, fmt.Errorf("service %q is down (health check failed: %s) and no start_command is configured", name, def.HealthURL)
	}

	// Serialize start attempts for this service; a concurrent task may have
	// started it while we were health-checking.
	lock := m.lockFor(name)
	lock.Lock()
	defer lock.Unlock()

	// Re-check after acquiring the lock: another goroutine may have started it.
	if m.checkHealth(ctx, def) {
		return false, nil
	}

	logger.Info("Bound service is down, starting it",
		"service", name,
		"health_url", def.HealthURL,
		"start_command", def.StartCommand,
		"work_dir", def.WorkDir)

	if err := m.startFunc(def); err != nil {
		return false, fmt.Errorf("failed to start service %q: %w", name, err)
	}

	if err := m.waitHealthy(ctx, name, def); err != nil {
		return true, err
	}

	logger.Info("Bound service started and healthy",
		"service", name,
		"health_url", def.HealthURL)

	return true, nil
}

// checkHealth performs a single health probe. Any 2xx response is healthy.
func (m *ServiceManager) checkHealth(ctx context.Context, def types.ServiceDefinition) bool {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, def.HealthURL, nil)
	if err != nil {
		return false
	}
	resp, err := m.client.Do(req)
	if err != nil {
		return false
	}
	defer resp.Body.Close()
	return resp.StatusCode >= 200 && resp.StatusCode < 300
}

// waitHealthy polls the health endpoint until the service is up or the
// startup timeout (or ctx) expires.
func (m *ServiceManager) waitHealthy(ctx context.Context, name string, def types.ServiceDefinition) error {
	timeout := time.Duration(def.StartupTimeoutSeconds) * time.Second
	if timeout <= 0 {
		timeout = defaultStartupTimeout
	}

	deadline := time.Now().Add(timeout)
	for {
		if m.checkHealth(ctx, def) {
			return nil
		}
		if time.Now().After(deadline) {
			return fmt.Errorf("service %q did not become healthy within %v (health_url: %s)", name, timeout, def.HealthURL)
		}

		select {
		case <-ctx.Done():
			return fmt.Errorf("canceled while waiting for service %q: %w", name, ctx.Err())
		case <-time.After(healthPollInterval):
		}
	}
}

// lockFor returns the per-service start mutex.
func (m *ServiceManager) lockFor(name string) *sync.Mutex {
	m.mu.Lock()
	defer m.mu.Unlock()
	lock, ok := m.startLocks[name]
	if !ok {
		lock = &sync.Mutex{}
		m.startLocks[name] = lock
	}
	return lock
}

// startDetached launches the start command in its own process group so the
// service keeps running after Agent OS returns from this call (or exits).
func (m *ServiceManager) startDetached(def types.ServiceDefinition) error {
	// NOTE: deliberately NOT exec.CommandContext — the service must outlive
	// the triggering request context.
	cmd := exec.Command("sh", "-c", def.StartCommand)
	if def.WorkDir != "" {
		cmd.Dir = def.WorkDir
	}
	cmd.SysProcAttr = &syscall.SysProcAttr{Setpgid: true}

	if err := cmd.Start(); err != nil {
		return fmt.Errorf("failed to launch start command: %w", err)
	}

	// Detach: do not Wait; release the process resources.
	if err := cmd.Process.Release(); err != nil {
		logger.Error("Failed to release service process", "error", err)
	}

	logger.Info("Service start command launched",
		"pid", cmd.Process.Pid,
		"command", def.StartCommand,
		"work_dir", def.WorkDir)

	return nil
}
