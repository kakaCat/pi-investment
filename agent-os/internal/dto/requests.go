package dto

// CreateTaskRequest represents the request to create a task
type CreateTaskRequest struct {
	Name        string                 `json:"name" validate:"required,min=1,max=100"`
	Owner       string                 `json:"owner" validate:"required,min=1,max=100"`
	Description string                 `json:"description" validate:"max=500"`
	Schedule    string                 `json:"schedule" validate:"omitempty,cron"`
	Cron        string                 `json:"cron" validate:"omitempty,cron"`
	Command     string                 `json:"command" validate:"max=1000"`
	WebhookURL  string                 `json:"webhook_url" validate:"omitempty,url,max=500"`
	Payload     map[string]interface{} `json:"payload"`
	Timeout     int                    `json:"timeout" validate:"min=1,max=3600"`
	RetryCount  int                    `json:"retry_count" validate:"min=0,max=10"`
	Enabled     bool                   `json:"enabled"`
}

// UpdateTaskRequest represents the request to update a task
type UpdateTaskRequest struct {
	Description string                 `json:"description" validate:"max=500"`
	Schedule    string                 `json:"schedule" validate:"omitempty,cron"`
	Cron        string                 `json:"cron" validate:"omitempty,cron"`
	Command     string                 `json:"command" validate:"max=1000"`
	WebhookURL  string                 `json:"webhook_url" validate:"omitempty,url,max=500"`
	Payload     map[string]interface{} `json:"payload"`
	Timeout     int                    `json:"timeout" validate:"omitempty,min=1,max=3600"`
	RetryCount  int                    `json:"retry_count" validate:"omitempty,min=0,max=10"`
	Enabled     bool                   `json:"enabled"`
}

// CreateSkillRequest represents the request to create a skill
type CreateSkillRequest struct {
	Name        string                 `json:"name" validate:"required,min=1,max=100"`
	Description string                 `json:"description" validate:"required,max=500"`
	Category    string                 `json:"category" validate:"required,max=50"`
	Owner       string                 `json:"owner" validate:"required,max=100"`
	Content     string                 `json:"content" validate:"required"`
	Metadata    map[string]interface{} `json:"metadata"`
}

// UpdateSkillRequest represents the request to update a skill
type UpdateSkillRequest struct {
	Description string                 `json:"description" validate:"max=500"`
	Category    string                 `json:"category" validate:"max=50"`
	Content     string                 `json:"content"`
	Status      string                 `json:"status" validate:"omitempty,oneof=active inactive deprecated"`
	Metadata    map[string]interface{} `json:"metadata"`
}
