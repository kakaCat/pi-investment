package errors

import "fmt"

// ErrorCode represents an application error code
type ErrorCode string

const (
	// General errors
	ErrCodeInternal        ErrorCode = "INTERNAL_ERROR"
	ErrCodeNotFound        ErrorCode = "NOT_FOUND"
	ErrCodeAlreadyExists   ErrorCode = "ALREADY_EXISTS"
	ErrCodeInvalidInput    ErrorCode = "INVALID_INPUT"
	ErrCodeUnauthorized    ErrorCode = "UNAUTHORIZED"
	ErrCodeForbidden       ErrorCode = "FORBIDDEN"
	ErrCodeConflict        ErrorCode = "CONFLICT"
	ErrCodeTooManyRequests ErrorCode = "TOO_MANY_REQUESTS"

	// Task errors
	ErrCodeTaskNotFound      ErrorCode = "TASK_NOT_FOUND"
	ErrCodeTaskAlreadyExists ErrorCode = "TASK_ALREADY_EXISTS"
	ErrCodeTaskDisabled      ErrorCode = "TASK_DISABLED"
	ErrCodeTaskRunning       ErrorCode = "TASK_RUNNING"
	ErrCodeInvalidSchedule   ErrorCode = "INVALID_SCHEDULE"

	// Execution errors
	ErrCodeExecutionNotFound ErrorCode = "EXECUTION_NOT_FOUND"
	ErrCodeExecutionFailed   ErrorCode = "EXECUTION_FAILED"
	ErrCodeExecutionTimeout  ErrorCode = "EXECUTION_TIMEOUT"

	// Skill errors
	ErrCodeSkillNotFound      ErrorCode = "SKILL_NOT_FOUND"
	ErrCodeSkillAlreadyExists ErrorCode = "SKILL_ALREADY_EXISTS"
	ErrCodeInvalidSkill       ErrorCode = "INVALID_SKILL"
)

// AppError represents an application error with code and user-friendly message
type AppError struct {
	Code        ErrorCode `json:"code"`
	Message     string    `json:"message"`           // User-visible message
	InternalMsg string    `json:"-"`                 // Internal logging message
	Err         error     `json:"-"`                 // Wrapped error
	HTTPStatus  int       `json:"-"`                 // HTTP status code
	Details     map[string]interface{} `json:"details,omitempty"` // Additional details
}

// Error implements the error interface
func (e *AppError) Error() string {
	if e.InternalMsg != "" {
		return e.InternalMsg
	}
	return e.Message
}

// Unwrap returns the wrapped error
func (e *AppError) Unwrap() error {
	return e.Err
}

// UserMessage returns the user-visible message
func (e *AppError) UserMessage() string {
	return e.Message
}

// WithDetails adds details to the error
func (e *AppError) WithDetails(key string, value interface{}) *AppError {
	if e.Details == nil {
		e.Details = make(map[string]interface{})
	}
	e.Details[key] = value
	return e
}

// New creates a new AppError
func New(code ErrorCode, message string, httpStatus int) *AppError {
	return &AppError{
		Code:       code,
		Message:    message,
		HTTPStatus: httpStatus,
	}
}

// Wrap wraps an error with application error context
func Wrap(err error, code ErrorCode, message string, httpStatus int) *AppError {
	return &AppError{
		Code:        code,
		Message:     message,
		InternalMsg: fmt.Sprintf("%s: %v", message, err),
		Err:         err,
		HTTPStatus:  httpStatus,
	}
}

// WrapWithInternal wraps an error with separate user and internal messages
func WrapWithInternal(err error, code ErrorCode, userMsg, internalMsg string, httpStatus int) *AppError {
	return &AppError{
		Code:        code,
		Message:     userMsg,
		InternalMsg: internalMsg,
		Err:         err,
		HTTPStatus:  httpStatus,
	}
}

// Common error constructors
func NotFound(resource string) *AppError {
	return New(ErrCodeNotFound, fmt.Sprintf("%s not found", resource), 404)
}

func AlreadyExists(resource string) *AppError {
	return New(ErrCodeAlreadyExists, fmt.Sprintf("%s already exists", resource), 409)
}

func InvalidInput(message string) *AppError {
	return New(ErrCodeInvalidInput, message, 400)
}

func Internal(message string) *AppError {
	return New(ErrCodeInternal, message, 500)
}

func InternalWrap(err error, userMsg string) *AppError {
	return WrapWithInternal(err, ErrCodeInternal, userMsg, fmt.Sprintf("%s: %v", userMsg, err), 500)
}
