"""
Error Handling and Transaction Management
Provides utilities for managing error handling and rollbacks in multi-step operations
"""
from contextlib import contextmanager
from typing import List, Callable, Any, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class RollbackAction:
    """Represents an action that should be executed to rollback a previous operation"""
    name: str
    action: Callable
    args: tuple = ()
    kwargs: dict = None
    
    def execute(self):
        """Execute the rollback action"""
        try:
            if self.kwargs is None:
                self.kwargs = {}
            self.action(*self.args, **self.kwargs)
            logger.info(f"Rollback executed: {self.name}")
        except Exception as e:
            logger.error(f"Rollback failed for {self.name}: {str(e)}")


class TransactionContext:
    """
    Manages a transaction with automatic rollback on error
    
    Usage:
        ctx = TransactionContext("evidence_intake")
        try:
            file_path = save_file(...)
            ctx.add_rollback(RollbackAction("delete_file", os.remove, (str(file_path),)))
            
            db_id = db.insert(...)
            ctx.add_rollback(RollbackAction("delete_db_record", db.delete, (db_id,)))
            
            # If anything fails after this point, rollbacks execute in reverse
            return result
        except Exception as e:
            ctx.rollback_all()
            raise
    """
    
    def __init__(self, operation_name: str):
        self.operation_name = operation_name
        self.rollback_stack: List[RollbackAction] = []
        self.completed_steps: List[str] = []
    
    def add_rollback(self, action: RollbackAction):
        """Add a rollback action to the stack"""
        self.rollback_stack.append(action)
        logger.debug(f"Added rollback action: {action.name}")
    
    def mark_step_complete(self, step_name: str):
        """Mark a step as completed for logging purposes"""
        self.completed_steps.append(step_name)
        logger.debug(f"Step completed: {step_name}")
    
    def rollback_all(self):
        """Execute all rollback actions in reverse order (LIFO)"""
        logger.warning(f"Rolling back operation '{self.operation_name}' (completed steps: {self.completed_steps})")
        
        while self.rollback_stack:
            action = self.rollback_stack.pop()
            action.execute()
    
    def get_status(self) -> dict:
        """Get current transaction status"""
        return {
            "operation": self.operation_name,
            "completed_steps": self.completed_steps,
            "pending_rollbacks": len(self.rollback_stack)
        }


@contextmanager
def managed_transaction(operation_name: str):
    """
    Context manager for automatic rollback on exception
    
    Usage:
        with managed_transaction("evidence_intake") as ctx:
            file_path = save_file(...)
            ctx.add_rollback(RollbackAction("delete_file", os.remove, (str(file_path),)))
            ctx.mark_step_complete("file_saved")
            
            db_id = db.insert(...)  # If this fails, file_path rollback executes
            ctx.add_rollback(RollbackAction("delete_db_record", db.delete, (db_id,)))
            ctx.mark_step_complete("db_record_inserted")
    """
    ctx = TransactionContext(operation_name)
    try:
        yield ctx
    except Exception as e:
        logger.error(f"Error in transaction '{operation_name}': {str(e)}")
        ctx.rollback_all()
        raise


class ErrorResponse:
    """Standardized error response format"""
    
    def __init__(self, error_type: str, message: str, details: Optional[dict] = None):
        self.error_type = error_type
        self.message = message
        self.details = details or {}
    
    def to_dict(self):
        return {
            "error": self.error_type,
            "message": self.message,
            "details": self.details
        }


# Error type constants
class ErrorTypes:
    VALIDATION_ERROR = "validation_error"
    AUTHENTICATION_ERROR = "authentication_error"
    AUTHORIZATION_ERROR = "authorization_error"
    NOT_FOUND_ERROR = "not_found_error"
    CONFLICT_ERROR = "conflict_error"
    RESOURCE_EXHAUSTED = "resource_exhausted"
    INTERNAL_ERROR = "internal_error"
    EXTERNAL_SERVICE_ERROR = "external_service_error"


def validate_input(data: Any, rules: dict) -> Optional[ErrorResponse]:
    """
    Validate input against rules
    
    Usage:
        error = validate_input(user_input, {
            'user_id': lambda x: len(x) >= 3,
            'password': lambda x: len(x) >= 8,
        })
        if error:
            raise HTTPException(status_code=400, detail=error.to_dict())
    """
    errors = {}
    
    for field, rule in rules.items():
        if hasattr(data, field):
            value = getattr(data, field)
        elif isinstance(data, dict):
            value = data.get(field)
        else:
            continue
        
        try:
            if not rule(value):
                errors[field] = f"Validation failed for {field}"
        except Exception as e:
            errors[field] = str(e)
    
    if errors:
        return ErrorResponse(
            error_type=ErrorTypes.VALIDATION_ERROR,
            message="Validation failed",
            details=errors
        )
    
    return None


def safe_operation(
    operation_name: str,
    operation_func: Callable,
    *args,
    **kwargs
) -> tuple[bool, Any, Optional[str]]:
    """
    Execute an operation safely with error handling
    
    Returns:
        (success: bool, result: Any, error_message: Optional[str])
    
    Usage:
        success, result, error = safe_operation(
            "search",
            search_engine.query,
            search_term,
            limit=10
        )
        if not success:
            logger.error(f"Search failed: {error}")
    """
    try:
        result = operation_func(*args, **kwargs)
        return (True, result, None)
    except Exception as e:
        logger.error(f"Error in {operation_name}: {str(e)}")
        return (False, None, str(e))
