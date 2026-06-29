---
name: fastapi
description: Use APIRouter-based route organization, validate in models, and keep response handling consistent.
---

# FastAPI Rules

## Route Organization

- Use `APIRouter` for grouping related routes.
- Keep route handlers thin; delegate business logic to service modules in `services/`.
- Services should be imported as modules when that keeps route files clearer and avoids large symbol import lists.
- Include routers via a `for` loop over a tuple; for a single router, use a one-item tuple with a trailing comma.
- Route files should contain only `@router.<verb>(...)` handlers, the `router = APIRouter(...)` declaration, and module-level constants/dependency factories that wire those handlers; cache-key builders, response shapers, validation/transform helpers, and shared sub-handlers belong in `services/` or `lib/`.
- Do not place a non-routing module under `routes/` so other route files can import from it; helper modules belong in `services/` or `lib/`.

```python
for router in (orders_router, customers_router):
    app.include_router(router)
```

## Parameters

- Use `Depends()` for dependency injection (database sessions, auth, etc.).
- Use `Body(...)` for request body parameters.
- Use `Path(...)` for path parameters.
- Use `Query(...)` for query parameters with defaults and validation.

## Request Validation

- Validate lengths/types in Pydantic request models, not in route handlers.
- Prefer dedicated field types from the project's shared model layer or from `pydantic` / `pydantic_extra_types` when they express the constraint clearly.
- Do not add runtime field-presence checks in route handlers or route-facing services for request-shape validation.
- Make required request fields required on the Pydantic model.
- Use `model_validator(...)` only when validity depends on multiple fields together. Do not add a model validator just to restate that independently required fields are required.

```python
from typing import Self

from pydantic import BaseModel, Field, model_validator
from pydantic_extra_types.phone_numbers import PhoneNumber

class VerifyPayload(BaseModel):
    phone_number: PhoneNumber
    retry_count: int = Field(ge=0, le=5)


# Bad: runtime request-shape validation in the route/service layer
if not payload.email or not payload.name:
    raise ErrorResponse(status_code=HTTPStatus.BAD_REQUEST, error="Missing required fields")


# Good: independently required fields are just required fields
class CreateUserPayload(BaseModel):
    email: str
    name: str
    external_id: str


# Good: use model_validator only for cross-field rules
class InvitePayload(BaseModel):
    email: str
    name: str
    team_name: str | None = None
    is_team_invite: bool = False

    @model_validator(mode="after")
    def validate_team_fields(self) -> Self:
        if self.is_team_invite and not self.team_name:
            raise ValueError("team_name is required for team invites")

        return self
```

## Route Metadata

- Do not pass `name`, `summary`, or `description` to route decorators; FastAPI uses the handler docstring.

```python
@router.post("/verify")
async def verify_phone(payload: VerifyPayload) -> ApiResponse[VerifyResponse]:
    """Verify a phone number and return status."""
```

## Response Types

- Use the repository's standard response envelope or response models consistently across handlers.
- Prefer one clear pattern for success, pagination, and error responses rather than mixing many response shapes in the same API surface.

### Success without a payload

- When an endpoint succeeds but has **no response body beyond `{ success: true }`**, use the project's standard `SuccessResponse` envelope (`return SuccessResponse(success=True)` with `response_model=SuccessResponse` and `response_model_exclude_unset=True`).
- Do **not** use `Response[None]` with `data=None`: it emits OpenAPI where `data` is typed as JSON `null` only, which breaks the Python OpenAPI Generator client and is not a useful contract.
- Do **not** invent empty Pydantic models just to satisfy `Response[...]` when there is no domain payload; use `SuccessResponse` instead.

## Response Construction

- Do not inline awaited service calls inside response construction.
- Fetch the data first, then return the response object.

```python
# Bad
return ApiResponse(success=True, data=await order_service.get_status(current_user, session))

# Good
data = await order_service.get_status(current_user, session)

return ApiResponse(success=True, data=data)
```

## Error Handling

- Raise `ErrorResponse` from `fastapi_custom_responses` directly with an appropriate `HTTPStatus`. Do not wrap it in a helper (for example, `bad_request("...")` or `not_found("...")`) just to set the status code; the call site already states the failure mode, and the helper only adds indirection.
- This includes log-and-raise wrappers (for example a `raise_internal_error_response(...)` that logs then raises): log and `raise ErrorResponse(...) from exc` inline at the failure site instead.
- Always pass `status_code=HTTPStatus.X` and `error="..."` (or `detail=...` for the few endpoints that already use that key) at the `raise` site so the status is visible without jumping to a helper.
- For bad or invalid client-provided data, raise `ErrorResponse` with `HTTPStatus.BAD_REQUEST`.
- Do not use `HTTPStatus.UNPROCESSABLE_ENTITY` for bad-data validation errors.
- Service functions may raise `ErrorResponse` when a domain check maps directly to an HTTP error (e.g., returning a 403 for authorization failures). This is an established pattern in the codebase; do not refactor these to route-layer-only error raising.

```python
from http import HTTPStatus

from fastapi_custom_responses import ErrorResponse

# Good: raise ErrorResponse directly at the failure site
raise ErrorResponse(
    status_code=HTTPStatus.BAD_REQUEST,
    error="Invalid payload",
)

# Bad: wrapping ErrorResponse in a status-specific helper
def bad_request(message: str) -> ErrorResponse:
    return ErrorResponse(status_code=HTTPStatus.BAD_REQUEST, error=message)

raise bad_request("Invalid payload")
```

```python
# Good: log and raise inline at the failure site
try:
    response = await client.get_resource(...)
except third_party_client.ApiException as exc:
    logger.error("Resource fetch failed: %s", exc)

    raise ErrorResponse(
        status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
        error="Failed to fetch resource",
    ) from exc

# Bad: routing the log + raise through a shared wrapper
except third_party_client.ApiException as exc:
    raise_internal_error_response(error="Failed to fetch resource", log_message="...", exc=exc)
```

## Pagination

- Never have unbounded query endpoints; always paginate if an endpoint can return more than 100 entries.
- Always add `offset` and `limit` query parameters to list/export endpoints.
- `limit=10000` or any hardcoded large limit is a code smell — paginate instead.
- When consuming paginated internal endpoints, implement a fetch-all loop in the gateway layer rather than requesting an unreasonably large limit.
- Respect `BaseTable.MAX_PAGINATION_LIMIT` (currently 100) — passing a larger limit raises `ValueError`.
