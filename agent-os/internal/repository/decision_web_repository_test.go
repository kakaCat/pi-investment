package repository

import (
	"context"
	"database/sql"
	"testing"
	"time"

	"github.com/DATA-DOG/go-sqlmock"
	"github.com/lib/pq"
	"github.com/pi-investment/agent-os/internal/domain"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestDecisionWebRepository_List(t *testing.T) {
	db, mock, err := sqlmock.New()
	require.NoError(t, err)
	defer db.Close()

	repo := NewDecisionWebRepository(db)

	tests := []struct {
		name        string
		req         domain.DecisionListRequest
		setupMock   func()
		expectedLen int
		expectError bool
	}{
		{
			name: "success - list all decisions",
			req:  domain.DecisionListRequest{Limit: 10},
			setupMock: func() {
				rows := sqlmock.NewRows([]string{
					"id", "agent_id", "action", "targets", "target", "confidence",
					"status", "reason", "context", "outcome", "created_at",
					"executed_at", "pnl", "timeline", "data", "updated_at",
				}).
					AddRow(
						"550e8400-e29b-41d4-a716-446655440001", "agent-1", "buy", pq.Array([]string{"stock1"}),
						"stock1", 0.85, "executed", "good opportunity",
						[]byte(`{"market":"bullish"}`), []byte(`{"result":"success"}`),
						time.Now(), time.Now(), 100.5, "2h", []byte(`{}`), time.Now(),
					).
					AddRow(
						"550e8400-e29b-41d4-a716-446655440002", "agent-1", "sell", pq.Array([]string{"stock2"}),
						"stock2", 0.75, "pending", "risk management",
						[]byte(`{}`), []byte(`{}`),
						time.Now(), nil, nil, "", []byte(`{}`), time.Now(),
					)

				mock.ExpectQuery(`SELECT .+ FROM decisions WHERE 1=1 .+ LIMIT`).
					WithArgs(10).
					WillReturnRows(rows)
			},
			expectedLen: 2,
			expectError: false,
		},
		{
			name: "success - filter by action",
			req:  domain.DecisionListRequest{Action: "buy", Limit: 5},
			setupMock: func() {
				rows := sqlmock.NewRows([]string{
					"id", "agent_id", "action", "targets", "target", "confidence",
					"status", "reason", "context", "outcome", "created_at",
					"executed_at", "pnl", "timeline", "data", "updated_at",
				}).
					AddRow(
						"550e8400-e29b-41d4-a716-446655440001", "agent-1", "buy", pq.Array([]string{"stock1"}),
						"stock1", 0.85, "executed", "good opportunity",
						[]byte(`{}`), []byte(`{}`),
						time.Now(), time.Now(), 100.5, "2h", []byte(`{}`), time.Now(),
					)

				mock.ExpectQuery(`SELECT .+ FROM decisions WHERE 1=1 AND action = .+ LIMIT`).
					WithArgs("buy", 5).
					WillReturnRows(rows)
			},
			expectedLen: 1,
			expectError: false,
		},
		{
			name: "success - filter by status",
			req:  domain.DecisionListRequest{Status: "executed", Limit: 5},
			setupMock: func() {
				rows := sqlmock.NewRows([]string{
					"id", "agent_id", "action", "targets", "target", "confidence",
					"status", "reason", "context", "outcome", "created_at",
					"executed_at", "pnl", "timeline", "data", "updated_at",
				})

				mock.ExpectQuery(`SELECT .+ FROM decisions WHERE 1=1 AND status = .+ LIMIT`).
					WithArgs("executed", 5).
					WillReturnRows(rows)
			},
			expectedLen: 0,
			expectError: false,
		},
		{
			name: "error - query fails",
			req:  domain.DecisionListRequest{},
			setupMock: func() {
				mock.ExpectQuery(`SELECT .+ FROM decisions WHERE 1=1`).
					WillReturnError(sql.ErrConnDone)
			},
			expectedLen: 0,
			expectError: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			tt.setupMock()

			decisions, err := repo.List(context.Background(), tt.req)

			if tt.expectError {
				assert.Error(t, err)
				assert.Nil(t, decisions)
			} else {
				assert.NoError(t, err)
				assert.Len(t, decisions, tt.expectedLen)
			}

			assert.NoError(t, mock.ExpectationsWereMet())
		})
	}
}

func TestDecisionWebRepository_GetByID(t *testing.T) {
	db, mock, err := sqlmock.New()
	require.NoError(t, err)
	defer db.Close()

	repo := NewDecisionWebRepository(db)

	tests := []struct {
		name        string
		id          string
		setupMock   func()
		expectError bool
	}{
		{
			name: "success - get decision by id",
			id:   "550e8400-e29b-41d4-a716-446655440001",
			setupMock: func() {
				rows := sqlmock.NewRows([]string{
					"id", "agent_id", "action", "targets", "target", "confidence",
					"status", "reason", "context", "outcome", "created_at",
					"executed_at", "pnl", "timeline", "data", "updated_at",
				}).
					AddRow(
						"550e8400-e29b-41d4-a716-446655440001", "agent-1", "buy", pq.Array([]string{"stock1"}),
						"stock1", 0.85, "executed", "good opportunity",
						[]byte(`{"market":"bullish"}`), []byte(`{"result":"success"}`),
						time.Now(), time.Now(), 100.5, "2h", []byte(`{}`), time.Now(),
					)

				mock.ExpectQuery(`SELECT .+ FROM decisions WHERE id = `).
					WithArgs("550e8400-e29b-41d4-a716-446655440001").
					WillReturnRows(rows)
			},
			expectError: false,
		},
		{
			name: "error - decision not found",
			id:   "550e8400-e29b-41d4-a716-446655440099",
			setupMock: func() {
				mock.ExpectQuery(`SELECT .+ FROM decisions WHERE id = `).
					WithArgs("550e8400-e29b-41d4-a716-446655440099").
					WillReturnError(sql.ErrNoRows)
			},
			expectError: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			tt.setupMock()

			decision, err := repo.GetByID(context.Background(), tt.id)

			if tt.expectError {
				assert.Error(t, err)
				assert.Nil(t, decision)
			} else {
				assert.NoError(t, err)
				assert.NotNil(t, decision)
				assert.Equal(t, tt.id, decision.ID.String())
			}

			assert.NoError(t, mock.ExpectationsWereMet())
		})
	}
}

func TestDecisionWebRepository_GetStatistics(t *testing.T) {
	db, mock, err := sqlmock.New()
	require.NoError(t, err)
	defer db.Close()

	repo := NewDecisionWebRepository(db)

	tests := []struct {
		name        string
		setupMock   func()
		expectError bool
		checkResult func(t *testing.T, stats *domain.DecisionStatistics)
	}{
		{
			name: "success - get statistics",
			setupMock: func() {
				// Mock main statistics query
				statsRows := sqlmock.NewRows([]string{
					"total", "executed", "pending", "avg_confidence",
				}).
					AddRow(100, 80, 15, 75.0)

				mock.ExpectQuery(`SELECT\s+COUNT\(\*\) as total`).
					WillReturnRows(statsRows)

				// Mock type distribution query
				typeRows := sqlmock.NewRows([]string{"name", "value"}).
					AddRow("buy", 60).
					AddRow("sell", 40)

				mock.ExpectQuery(`SELECT action as name, COUNT\(\*\) as value`).
					WillReturnRows(typeRows)

				// Mock status distribution query
				statusRows := sqlmock.NewRows([]string{"name", "value"}).
					AddRow("executed", 80).
					AddRow("pending", 15).
					AddRow("failed", 5)

				mock.ExpectQuery(`SELECT status as name, COUNT\(\*\) as value`).
					WillReturnRows(statusRows)
			},
			expectError: false,
			checkResult: func(t *testing.T, stats *domain.DecisionStatistics) {
				assert.Equal(t, 100, stats.Total)
				assert.Equal(t, 80, stats.Executed)
				assert.Equal(t, 15, stats.Pending)
				assert.InDelta(t, 75.0, stats.AvgConfidence, 0.01)
				assert.Len(t, stats.TypeDistribution, 2)
				assert.Len(t, stats.StatusDistribution, 3)
			},
		},
		{
			name: "error - query fails",
			setupMock: func() {
				mock.ExpectQuery(`SELECT COUNT\(\*\) as total`).
					WillReturnError(sql.ErrConnDone)
			},
			expectError: true,
			checkResult: func(t *testing.T, stats *domain.DecisionStatistics) {},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			tt.setupMock()

			stats, err := repo.GetStatistics(context.Background())

			if tt.expectError {
				assert.Error(t, err)
				assert.Nil(t, stats)
			} else {
				assert.NoError(t, err)
				assert.NotNil(t, stats)
				tt.checkResult(t, stats)
			}

			assert.NoError(t, mock.ExpectationsWereMet())
		})
	}
}
