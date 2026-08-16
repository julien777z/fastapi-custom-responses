from typing import Self

from pydantic_super_model import SuperModelPydanticMixin


class SuccessResponse(SuperModelPydanticMixin):
    """Success response without data."""

    success: bool


class Response[T](SuperModelPydanticMixin):
    """Success response carrying a data payload."""

    success: bool
    data: T | None = None


class PaginationMeta(SuperModelPydanticMixin):
    """Pagination metadata model."""

    offset: int
    limit: int
    total: int


class PaginatedResponse[T](Response[list[T]]):
    """Paginated response model."""

    meta: PaginationMeta

    @classmethod
    def build_page(cls, items: list[T], *, offset: int, limit: int, total: int) -> Self:
        """Build a paginated response from a page of items and the bounds it was read with."""

        return cls(
            success=True,
            data=items,
            meta=PaginationMeta(offset=offset, limit=limit, total=total),
        )
