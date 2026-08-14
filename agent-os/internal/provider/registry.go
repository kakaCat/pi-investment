package provider

import (
	"fmt"
	"sync"
)

var (
	registry = &Registry{
		providers: make(map[string]Provider),
	}
)

// Registry 提供商注册中心
type Registry struct {
	mu        sync.RWMutex
	providers map[string]Provider
}

// Register 注册提供商
func Register(provider Provider) {
	registry.mu.Lock()
	defer registry.mu.Unlock()
	registry.providers[provider.Name()] = provider
}

// Get 获取提供商
func Get(name string) (Provider, error) {
	registry.mu.RLock()
	defer registry.mu.RUnlock()

	provider, ok := registry.providers[name]
	if !ok {
		return nil, fmt.Errorf("provider %s not found", name)
	}
	return provider, nil
}

// List 列出所有提供商
func List() []string {
	registry.mu.RLock()
	defer registry.mu.RUnlock()

	names := make([]string, 0, len(registry.providers))
	for name := range registry.providers {
		names = append(names, name)
	}
	return names
}

// Has 检查提供商是否存在
func Has(name string) bool {
	registry.mu.RLock()
	defer registry.mu.RUnlock()
	_, ok := registry.providers[name]
	return ok
}
