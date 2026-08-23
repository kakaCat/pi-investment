package validator

import (
	"fmt"
	"regexp"

	"github.com/go-playground/validator/v10"
)

var (
	validate *validator.Validate
	// cronRegex validates exactly 6 fields separated by single spaces
	cronRegex = regexp.MustCompile(`^(\S+) (\S+) (\S+) (\S+) (\S+) (\S+)$`)
)

func init() {
	validate = validator.New()

	// Register custom validators
	validate.RegisterValidation("cron", validateCron)
}

// Validate validates a struct using validator tags
func Validate(s interface{}) error {
	if err := validate.Struct(s); err != nil {
		if validationErrors, ok := err.(validator.ValidationErrors); ok {
			return formatValidationErrors(validationErrors)
		}
		return err
	}
	return nil
}

// validateCron validates a 6-field cron expression
func validateCron(fl validator.FieldLevel) bool {
	cronExpr := fl.Field().String()
	if cronExpr == "" {
		return true // empty is valid (optional field)
	}
	return cronRegex.MatchString(cronExpr)
}

// formatValidationErrors formats validation errors into a user-friendly message
func formatValidationErrors(errs validator.ValidationErrors) error {
	var msg string
	for _, err := range errs {
		switch err.Tag() {
		case "required":
			msg += fmt.Sprintf("%s is required; ", err.Field())
		case "min":
			msg += fmt.Sprintf("%s must be at least %s; ", err.Field(), err.Param())
		case "max":
			msg += fmt.Sprintf("%s must be at most %s; ", err.Field(), err.Param())
		case "cron":
			msg += fmt.Sprintf("%s must be a valid 6-field cron expression; ", err.Field())
		default:
			msg += fmt.Sprintf("%s is invalid; ", err.Field())
		}
	}
	return fmt.Errorf("validation failed: %s", msg)
}
