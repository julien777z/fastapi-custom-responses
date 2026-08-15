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
