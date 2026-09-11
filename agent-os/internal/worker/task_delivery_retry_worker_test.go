package worker

import (
	"testing"
	"time"
)

// 2026-09-11（w-f4aa1f6a）：投递积压的退避策略——覆盖 DSH 长时间不可达场景
func TestNextBackoffEscalatesAndCaps(t *testing.T) {
	cases := []struct {
		attempts int
		want     time.Duration
	}{
		{1, 30 * time.Second},
		{2, time.Minute},
		{3, 2 * time.Minute},
		{4, 4 * time.Minute},
		{5, 8 * time.Minute},
		{6, 16 * time.Minute},
		{7, 30 * time.Minute},  // 封顶
		{12, 30 * time.Minute}, // 超过上限仍封顶
		{0, 30 * time.Second},  // 非法输入按首次处理
	}
	for _, c := range cases {
		if got := nextBackoff(c.attempts); got != c.want {
			t.Errorf("nextBackoff(%d) = %v, want %v", c.attempts, got, c.want)
		}
	}
}

// 10 次尝试的总覆盖时长应远超任何内存重试窗口（旧行为 ≈90s）
func TestNextBackoffTotalCoverageExceedsNinetySeconds(t *testing.T) {
	total := time.Duration(0)
	for i := 1; i <= 10; i++ {
		total += nextBackoff(i)
	}
	if total < 30*time.Minute {
		t.Fatalf("总覆盖时长 %v 过短，无法覆盖对端长时间不可达", total)
	}
}
