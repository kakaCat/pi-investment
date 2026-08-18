package api

import (
	"encoding/json"
	"net/http"

	"github.com/pi-investment/agent-os/internal/errors"
	"github.com/pi-investment/agent-os/pkg/logger"
)

// ErrorResponse represents an error response
type ErrorResponse struct {
	Code    errors.ErrorCode       `json:"code"`
	Message string                 `json:"message"`
	Details map[string]interface{} `json:"details,omitempty"`
}

// SuccessResponse represents a success response
type SuccessResponse struct {
	Data interface{} `json:"data,omitempty"`
}

// respondJSON sends a JSON response
func respondJSON(w http.ResponseWriter, status int, data interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)

	if data != nil {
		if err := json.NewEncoder(w).Encode(data); err != nil {
			logger.Error("Failed to encode JSON response", "error", err)
		}
	}
}

// respondSuccess sends a successful JSON response
func respondSuccess(w http.ResponseWriter, status int, data interface{}) {
	respondJSON(w, status, SuccessResponse{Data: data})
}

// respondError sends an error JSON response
func respondError(w http.ResponseWriter, status int, message string) {
	respondJSON(w, status, ErrorResponse{
		Code:    errors.ErrCodeInternal,
		Message: message,
	})
}

// respondAppError sends an AppError as JSON response
func respondAppError(w http.ResponseWriter, err *errors.AppError) {
	// Log internal error details
	if err.Err != nil {
		logger.Error("Application error",
			"code", err.Code,
			"message", err.Message,
			"internal", err.InternalMsg,
			"wrapped_error", err.Err)
	}

	respondJSON(w, err.HTTPStatus, ErrorResponse{
		Code:    err.Code,
		Message: err.Message,
		Details: err.Details,
	})
}

// handleError handles different types of errors and sends appropriate response
func handleError(w http.ResponseWriter, err error) {
	if appErr, ok := err.(*errors.AppError); ok {
		respondAppError(w, appErr)
		return
	}

	// Generic error
	logger.Error("Unexpected error", "error", err)
	respondError(w, http.StatusInternalServerError, "An internal error occurred")
}
