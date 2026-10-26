"""计划领域层：状态机 + spec 校验（纯逻辑，无 I/O）。"""
from .spec import COMBINATORS, EXIT_TYPES, REQUIRED_SECTIONS, normalize_plan_spec, validate_plan_spec
from .state_machine import (
    LEGAL_TRANSITIONS, STATUSES,
    STATUS_ACTIVE, STATUS_ARCHIVED, STATUS_CLOSED, STATUS_CLOSING,
    STATUS_DRAFT, STATUS_HOLDING, STATUS_PAUSED,
    evaluate_plan_transition, is_legal_transition, next_close_status,
)

__all__ = [
    'LEGAL_TRANSITIONS', 'STATUSES', 'STATUS_DRAFT', 'STATUS_ACTIVE', 'STATUS_HOLDING',
    'STATUS_CLOSING', 'STATUS_CLOSED', 'STATUS_ARCHIVED', 'STATUS_PAUSED',
    'evaluate_plan_transition', 'is_legal_transition', 'next_close_status',
    'REQUIRED_SECTIONS', 'COMBINATORS', 'EXIT_TYPES',
    'validate_plan_spec', 'normalize_plan_spec',
]
