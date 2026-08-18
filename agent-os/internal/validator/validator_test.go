package validator

import (
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

type TestStruct struct {
	Name     string `validate:"required,min=1,max=10"`
	Age      int    `validate:"min=0,max=150"`
	Email    string `validate:"omitempty,email"`
	CronExpr string `validate:"omitempty,cron"`
}

func TestValidate_Success(t *testing.T) {
	tests := []struct {
		name   string
		input  TestStruct
	}{
		{
			name: "valid with all fields",
			input: TestStruct{
				Name:     "John",
				Age:      30,
				Email:    "john@example.com",
				CronExpr: "0 0 9 * * *",
			},
		},
		{
			name: "valid with minimum fields",
			input: TestStruct{
				Name: "Jane",
				Age:  25,
			},
		},
		{
			name: "valid with edge cases",
			input: TestStruct{
				Name: "A",
				Age:  0,
			},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := Validate(&tt.input)
			assert.NoError(t, err)
		})
	}
}

func TestValidate_Failures(t *testing.T) {
	tests := []struct {
		name      string
		input     TestStruct
		wantError string
	}{
		{
			name: "missing required name",
			input: TestStruct{
				Age: 30,
			},
			wantError: "Name is required",
		},
		{
			name: "name too long",
			input: TestStruct{
				Name: "ThisNameIsTooLong",
				Age:  30,
			},
			wantError: "Name must be at most 10",
		},
		{
			name: "age too high",
			input: TestStruct{
				Name: "John",
				Age:  200,
			},
			wantError: "Age must be at most 150",
		},
		{
			name: "invalid email",
			input: TestStruct{
				Name:  "John",
				Age:   30,
				Email: "invalid-email",
			},
			wantError: "Email is invalid",
		},
		{
			name: "invalid cron expression",
			input: TestStruct{
				Name:     "John",
				Age:      30,
				CronExpr: "invalid cron",
			},
			wantError: "CronExpr must be a valid 6-field cron expression",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := Validate(&tt.input)
			require.Error(t, err)
			assert.Contains(t, err.Error(), tt.wantError)
		})
	}
}

func TestValidateCron(t *testing.T) {
	tests := []struct {
		name      string
		cronExpr  string
		wantValid bool
	}{
		{
			name:      "valid 6-field cron",
			cronExpr:  "0 0 9 * * *",
			wantValid: true,
		},
		{
			name:      "valid with ranges",
			cronExpr:  "0 0 9-17 * * 1-5",
			wantValid: true,
		},
		{
			name:      "valid with steps",
			cronExpr:  "0 */15 * * * *",
			wantValid: true,
		},
		{
			name:      "invalid 5-field cron",
			cronExpr:  "0 9 * * *",
			wantValid: false,
		},
		{
			name:      "invalid with extra spaces",
			cronExpr:  "0 0  9 * * *",
			wantValid: false,
		},
		{
			name:      "empty string",
			cronExpr:  "",
			wantValid: true, // empty is valid (optional)
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			type CronTest struct {
				Cron string `validate:"cron"`
			}

			input := CronTest{Cron: tt.cronExpr}
			err := Validate(&input)

			if tt.wantValid {
				assert.NoError(t, err)
			} else {
				assert.Error(t, err)
			}
		})
	}
}
