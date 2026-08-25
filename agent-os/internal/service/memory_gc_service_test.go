package service

import (
	"context"
	"database/sql"
	"testing"

	"github.com/DATA-DOG/go-sqlmock"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestMemoryGCService_archiveClosedMemories(t *testing.T) {
	db, mock, err := sqlmock.New()
	require.NoError(t, err)
	defer db.Close()
	
	service := NewMemoryGCService(db)
	ctx := context.Background()
	
	// 预期执行的 SQL
	mock.ExpectExec(`UPDATE memories SET metadata = jsonb_set`).
		WillReturnResult(sqlmock.NewResult(0, 5)) // 5 条记录被归档
	
	count, err := service.archiveClosedMemories(ctx)
	
	assert.NoError(t, err)
	assert.Equal(t, int64(5), count)
	assert.NoError(t, mock.ExpectationsWereMet())
}

func TestMemoryGCService_deleteArchivedMemories(t *testing.T) {
	db, mock, err := sqlmock.New()
	require.NoError(t, err)
	defer db.Close()
	
	service := NewMemoryGCService(db)
	ctx := context.Background()
	
	// 模拟分批删除：第一批 1000 条，第二批 500 条，第三批 0 条
	mock.ExpectExec(`DELETE FROM memories WHERE id IN`).
		WillReturnResult(sqlmock.NewResult(0, 1000))
	mock.ExpectExec(`DELETE FROM memories WHERE id IN`).
		WillReturnResult(sqlmock.NewResult(0, 500))
	mock.ExpectExec(`DELETE FROM memories WHERE id IN`).
		WillReturnResult(sqlmock.NewResult(0, 0))
	
	count, err := service.deleteArchivedMemories(ctx)
	
	assert.NoError(t, err)
	assert.Equal(t, int64(1500), count)
	assert.NoError(t, mock.ExpectationsWereMet())
}

func TestMemoryGCService_Run(t *testing.T) {
	db, mock, err := sqlmock.New()
	require.NoError(t, err)
	defer db.Close()
	
	service := NewMemoryGCService(db)
	ctx := context.Background()
	
	// 预期两个阶段的 SQL
	mock.ExpectExec(`UPDATE memories SET metadata = jsonb_set`).
		WillReturnResult(sqlmock.NewResult(0, 3)) // 阶段 1: 归档 3 条
	mock.ExpectExec(`DELETE FROM memories WHERE id IN`).
		WillReturnResult(sqlmock.NewResult(0, 10)) // 阶段 2: 删除 10 条
	mock.ExpectExec(`DELETE FROM memories WHERE id IN`).
		WillReturnResult(sqlmock.NewResult(0, 0)) // 第二批为空
	
	err = service.Run(ctx)
	
	assert.NoError(t, err)
	assert.NoError(t, mock.ExpectationsWereMet())
}

func TestMemoryGCService_archiveClosedMemories_Error(t *testing.T) {
	db, mock, err := sqlmock.New()
	require.NoError(t, err)
	defer db.Close()
	
	service := NewMemoryGCService(db)
	ctx := context.Background()
	
	// 模拟数据库错误
	mock.ExpectExec(`UPDATE memories SET metadata = jsonb_set`).
		WillReturnError(sql.ErrConnDone)
	
	count, err := service.archiveClosedMemories(ctx)
	
	assert.Error(t, err)
	assert.Equal(t, int64(0), count)
	assert.Contains(t, err.Error(), "failed to execute archive query")
}
