"""
Common pagination and request validation utilities.
Enforces consistent limits and defaults across all list/query endpoints.
"""
from typing import Tuple

# Pagination constants
DEFAULT_LIMIT = 50
MAX_LIMIT = 500
DEFAULT_OFFSET = 0

# Rate limiting constants
DEFAULT_RATE_LIMIT = 100  # requests per minute
ADMIN_RATE_LIMIT = 200

# File upload limits
MAX_UPLOAD_SIZE_MB = 100
MAX_UPLOAD_SIZE_BYTES = MAX_UPLOAD_SIZE_MB * 1024 * 1024


def validate_pagination(
    limit: int = DEFAULT_LIMIT,
    offset: int = DEFAULT_OFFSET,
) -> Tuple[int, int]:
    """
    Validate and normalize pagination parameters.
    
    Returns:
        (normalized_limit, normalized_offset)
    """
    # Enforce limits
    if limit < 1:
        limit = DEFAULT_LIMIT
    elif limit > MAX_LIMIT:
        limit = MAX_LIMIT
    
    if offset < 0:
        offset = DEFAULT_OFFSET
    
    return limit, offset


def get_pagination_headers(
    limit: int,
    offset: int,
    total: int,
) -> dict:
    """
    Create pagination response metadata for headers/response body.
    
    Returns:
        Dict with pagination info
    """
    has_next = (offset + limit) < total
    has_prev = offset > 0
    
    return {
        "limit": limit,
        "offset": offset,
        "total": total,
        "has_next": has_next,
        "has_prev": has_prev,
        "current_page": (offset // limit) + 1 if limit > 0 else 1,
    }
