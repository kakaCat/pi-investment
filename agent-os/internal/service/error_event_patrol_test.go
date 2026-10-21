package service

// 僵尸回收巡检单测（P1，2026-10-21 w-6224baac）。
//
// 覆盖：
//  · 仓储 SQL 面（sqlmock）：阈值以秒传参、命中条数如实返回、非 0 阈值兜底默认 2h；
//  · 巡检服务面：委托仓储、错误如实上抛（RunPeriodically 内部吞掉不影响宿主）。

import (
	"context"
	"database/sql"
	"errors"
	"testing"
	"time"

	"github.com/DATA-DOG/go-sqlmock"

	"github.com/pi-investment/agent-os/internal/repository"
)

func TestReclaimZombieProcessingSQL(t *testing.T) {
	db, mock, err := sqlmock.New(sqlmock.QueryMatcherOption(sqlmock.QueryMatcherRegexp))
	if err != nil {
		t.Fatalf("sqlmock: %v", err)
	}
	defer db.Close()

	repo := repository.NewErrorEventRepository(db)

	// 命中 3 条：阈值 2h → 7200 秒
	mock.ExpectExec("UPDATE error_events").
		WithArgs(int64((2 * time.Hour).Seconds())).
		WillReturnResult(sqlmock.NewResult(0, 3))

	n, err := repo.ReclaimZombieProcessing(context.Background(), 2*time.Hour)
	if err != nil {
		t.Fatalf("ReclaimZombieProcessing: %v", err)
	}
	if n != 3 {
		t.Fatalf("reclaimed = %d, want 3", n)
	}
	if err := mock.ExpectationsWereMet(); err != nil {
		t.Fatalf("unmet expectations: %v", err)
	}
}

func TestReclaimZombieProcessingDefaultThreshold(t *testing.T) {
	db, mock, err := sqlmock.New(sqlmock.QueryMatcherOption(sqlmock.QueryMatcherRegexp))
	if err != nil {
		t.Fatalf("sqlmock: %v", err)
	}
	defer db.Close()

	repo := repository.NewErrorEventRepository(db)

	// 非法/未设阈值 → 兜底默认 2h（7200s），绝不按 0 秒回收（那会把刚认领的也收走）
	mock.ExpectExec("UPDATE error_events").
		WithArgs(int64(repository.DefaultZombieThreshold.Seconds())).
		WillReturnResult(sqlmock.NewResult(0, 0))

	n, err := repo.ReclaimZombieProcessing(context.Background(), 0)
	if err != nil {
		t.Fatalf("ReclaimZombieProcessing: %v", err)
	}
	if n != 0 {
		t.Fatalf("reclaimed = %d, want 0", n)
	}
	if err := mock.ExpectationsWereMet(); err != nil {
		t.Fatalf("unmet expectations: %v", err)
	}
}

func TestReclaimZombieProcessingPropagatesError(t *testing.T) {
	db, mock, err := sqlmock.New(sqlmock.QueryMatcherOption(sqlmock.QueryMatcherRegexp))
	if err != nil {
		t.Fatalf("sqlmock: %v", err)
	}
	defer db.Close()

	repo := repository.NewErrorEventRepository(db)
	mock.ExpectExec("UPDATE error_events").WillReturnError(errors.New("db down"))

	if _, err := repo.ReclaimZombieProcessing(context.Background(), time.Hour); err == nil {
		t.Fatal("want error when db down, got nil（失败必须如实上抛，不得静默当成回收 0 条）")
	}
}

// fakeRepo 只实现被调用的方法，其余经嵌入接口透传（调用即 panic，正好当哨兵）。
type fakeRepo struct {
	repository.ErrorEventRepository
	n   int64
	err error
}

func (f *fakeRepo) ReclaimZombieProcessing(ctx context.Context, olderThan time.Duration) (int64, error) {
	return f.n, f.err
}

func TestPatrolRunDelegatesToRepo(t *testing.T) {
	p := NewErrorEventPatrol(&fakeRepo{n: 7}, 0, 0)
	n, err := p.Run(context.Background())
	if err != nil || n != 7 {
		t.Fatalf("Run = (%d, %v), want (7, nil)", n, err)
	}
}

func TestPatrolRunPropagatesError(t *testing.T) {
	p := NewErrorEventPatrol(&fakeRepo{err: errors.New("db down")}, time.Hour, time.Minute)
	if _, err := p.Run(context.Background()); err == nil {
		t.Fatal("want error propagated")
	}
}

var _ = sql.DB{} // 保持 database/sql 导入（sqlmock 返回 *sql.DB）
