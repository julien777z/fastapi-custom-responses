from typing import Any

from pydantic_super_model import SuperModel


class SuccessResponse(SuperModel):
    """Success response without data."""

    success: bool
    error: str | None = None


class Response[T](SuperModel):
    """Response model."""

    success: bool
    data: T | None = None
    error: str | None = None


class PaginationMeta(SuperModel):
    """Pagination metadata model."""

    offset: int
    limit: int
    total: int


class PaginatedResponse[T: Any](Response[list[T]]):
    """Paginated response model."""

    meta: PaginationMeta
