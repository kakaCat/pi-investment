package repository

// 错误事件状态机 claim 转移矩阵（2026-10-21 修复"僵尸处理中"死角，w-6224baac）
//
// 为什么要有这份测试：ApplyAction 需要真实 DB，历史测试只覆盖到 happy path，
// 于是 claim 只收 open / reopen 只收终态这组约束构成的死角（processing 且
// assignee 为空 → 无任何出口）从未被证伪，直到 error_events a6780ec3（×1124，
// 2026-09-11 起卡 processing、assignee 为空）在看板上躺了 40 天。
// 把转移判定收敛成纯函数 claimTransitionAllowed 后，用状态 × assignee 的
// 穷举矩阵钉住边界——任何新增状态/放宽都必须先改这张表。

import (
	"testing"

	"github.com/pi-investment/agent-os/internal/domain"
)

func strPtr(s string) *string { return &s }

func TestClaimTransitionAllowed(t *testing.T) {
	cases := []struct {
		name     string
		status   string
		assignee *string
		want     bool
	}{
		// 正常路径
		{"open 无人 → 可认领", string(domain.ErrorStatusOpen), nil, true},
		{"open 有 actor 请求 → 可认领", string(domain.ErrorStatusOpen), nil, true},
		// 死角回归：processing 但无人负责（a6780ec3 形态）
		{"processing 且 assignee=nil → 可认领（僵尸回收）", string(domain.ErrorStatusProcessing), nil, true},
		{"processing 且 assignee 空串 → 可认领（僵尸回收）", string(domain.ErrorStatusProcessing), strPtr(""), true},
		// 防抢单：有责任人时不得抢
		{"processing 且已有 assignee → 拒绝（防抢单）", string(domain.ErrorStatusProcessing), strPtr("w-8e45ad2a"), false},
		// 终态必须先 reopen
		{"resolved → 拒绝（须 reopen）", string(domain.ErrorStatusResolved), nil, false},
		{"resolved 有 note 残留 → 拒绝", string(domain.ErrorStatusResolved), strPtr("w-x"), false},
		{"ignored → 拒绝（须 reopen）", string(domain.ErrorStatusIgnored), nil, false},
		// 未知状态一律拒绝（防御：非法值不得被认领）
		{"未知状态 → 拒绝", "bogus", nil, false},
		{"空状态 → 拒绝", "", nil, false},
	}

	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			got := claimTransitionAllowed(c.status, c.assignee)
			if got != c.want {
				t.Fatalf("claimTransitionAllowed(%q, %v) = %v, want %v",
					c.status, deref(c.assignee), got, c.want)
			}
		})
	}
}

// 不变式：从每个状态出发都存在一条"可认领或可到终态"的路径（死角探测）。
// 处置动作 claim/resolve/ignore/reopen 全部不被允许的状态 = 死角。
func TestNoDeadlockStateForClaimPath(t *testing.T) {
	statuses := []string{
		string(domain.ErrorStatusOpen),
		string(domain.ErrorStatusProcessing),
		string(domain.ErrorStatusResolved),
		string(domain.ErrorStatusIgnored),
	}
	for _, st := range statuses {
		claimable := claimTransitionAllowed(st, nil)
		// resolved/ignored 可经 reopen 回 open 后认领；open/processing 必须直接可认领
		// （processing 的口径是"无责任人"——有责任人的 processing 不需要出口，人正在处理）
		reopenable := st == string(domain.ErrorStatusResolved) || st == string(domain.ErrorStatusIgnored)
		if !claimable && !reopenable {
			t.Fatalf("状态 %q 既不可认领也不可 reopen —— 死角回归", st)
		}
	}
}

func deref(p *string) string {
	if p == nil {
		return "<nil>"
	}
	return *p
}
