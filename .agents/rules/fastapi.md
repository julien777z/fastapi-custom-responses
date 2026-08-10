---
description: Use APIRouter-based route organization, validate in models, and keep response handling consistent.
globs:
- '**/*.py'
alwaysApply: false
paths:
- '**/*.py'
---

# FastAPI Rules

## Layering: routes → services → lib

- Each app follows one dependency direction: `routes/` → `services/` → `lib/` → generated clients / ORM. Never invert it.
- Tier ownership:
  - `routes/`: `@<surface>_router.<verb>(...)` handlers, the `<surface>_router = APIRouter(...)` declaration, and dependency *wiring* (`Depends(...)`, `Annotated` aliases). No business logic.
  - `services/<surface>.py`: route-facing orchestration (multi-step flows, policy decisions that span calls, response assembly) and FastAPI dependency functions. Sub-split large surfaces into a `services/<surface>/` package with topic-named modules and an empty `__init__.py`; consumers import the specific submodule.
  - `lib/<domain>/`: gateways (internal-service transport), persistence helpers, caches, and policy/domain helpers with no route-facing signatures.
- **One call per handler**: a handler makes exactly one service call (for flows with policy or orchestration) or one lib-gateway call (pure pass-through). If a handler stitches two calls together, branches on an intermediate result, or shapes data between calls, that orchestration belongs in a service function (for example: fetch → transform → respond, reject → notify, or validate → perform).
- **No data access or response shaping in handlers**: a handler must not query or persist data directly, nor assemble response models from raw rows or records inline; extract a service function that returns the response model and keep the handler to wrap-and-return.
- Dependency factories may be *declared* in route files, but the policy body they invoke lives in `services/` or `lib/` (for example, a `RequireXxx = Depends(policy_module.ensure_xxx)` alias in the route file pointing at a lib policy function).

## Route Organization

- Use `APIRouter` for grouping related routes.
- Keep route handlers thin; delegate business logic to service modules in `services/`.
- Import the service functions a route file calls, by name. A route file that reaches through a service module hides which of its functions the file depends on, and a long symbol list is a signal the route file covers too many surfaces, not a reason to import the module.
- A handler that shares a name with the service function it calls is a naming defect. The handler name is the API contract (it becomes the OpenAPI operation id), so rename the service function for the domain operation it performs.
- Name every router for the surface it serves (`invoices_router`, not `router`), so the application entrypoint imports each one by name instead of reaching through its module.
- Include routers via a `for` loop over a tuple; for a single router, use a one-item tuple with a trailing comma.
- Route files should contain only `@<surface>_router.<verb>(...)` handlers, the router declaration, and module-level constants/dependency factories that wire those handlers; cache-key builders, response shapers, validation/transform helpers, and shared sub-handlers belong in `services/` or `lib/`.
- Do not place a non-routing module under `routes/` so other route files can import from it; helper modules belong in `services/` or `lib/`.

```python
for router in (resources_router, reports_router):
    app.include_router(router)
```

## Webhooks

- Inbound webhooks from external providers do not belong in `routes/` with the application's own API routers. Put them in a dedicated `webhooks/` package, organized by provider (for example `webhooks/provider_x.py`).
- Treat webhooks as a separate surface from the first-party API: they are authenticated by provider signature verification rather than the app's auth, carry provider-defined payloads, and follow different rate-limit rules (a per-user/per-IP limit would throttle a provider's single source IP). Keeping them out of `routes/` keeps that boundary clear.

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
if not payload.name or not payload.source_id:
    raise ApiError(status_code=HTTPStatus.BAD_REQUEST, detail="Missing required fields")


# Good: independently required fields are just required fields
class CreateResourcePayload(BaseModel):
    name: str
    source_id: str


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
async def verify_resource(payload: VerifyPayload) -> ApiEnvelope[VerifyResponse]:
    """Verify a resource and return status."""
```

## Response Types

- Use the repository's standard response envelope or response models consistently across handlers.
- Prefer one clear pattern for success, pagination, and error responses rather than mixing many response shapes in the same API surface.

### Success without a payload

- When an endpoint succeeds but has **no response body beyond `{ success: true }`**, use the project's standard no-payload success envelope with `response_model_exclude_unset=True`.
- Do **not** use a generic envelope specialized as `None` with `data=None`: it emits OpenAPI where `data` is typed as JSON `null` only, which breaks generated clients and is not a useful contract.
- Do **not** invent empty Pydantic models just to satisfy a generic response wrapper when there is no payload; use the project's standard no-payload success response instead.

## Response Construction

- Do not inline awaited service calls inside response construction.
- Fetch the data first, then return the response object.

```python
from application.services.resources import get_resource_status

# Bad
return ApiEnvelope(success=True, data=await get_resource_status(principal, session))

# Good
data = await get_resource_status(principal, session)

return ApiEnvelope(success=True, data=data)
```

## Error Handling

- Raise the project's standard API error response directly with an appropriate `HTTPStatus`. Do not wrap it in a helper (for example, `bad_request("...")` or `not_found("...")`) just to set the status code; the call site already states the failure mode, and the helper only adds indirection.
- This includes log-and-raise wrappers (for example a `raise_internal_api_error(...)` that logs then raises): log and `raise ApiError(...) from exc` inline at the failure site instead.
- Always pass `status_code=HTTPStatus.X` and `detail="..."` at the `raise` site so the status is visible without jumping to a helper.
- For bad or invalid client-provided data, raise the project's standard API error response with `HTTPStatus.BAD_REQUEST`.
- Do not use `HTTPStatus.UNPROCESSABLE_ENTITY` for bad-data validation errors.
- Service functions may raise the project's standard API error when a domain check maps directly to an HTTP error (e.g., returning a 403 for authorization failures). Do not force these cases into route-layer-only error raising.

```python
from http import HTTPStatus

from application.api.errors import ApiError

# Good: raise the standard API error directly at the failure site
raise ApiError(
    status_code=HTTPStatus.BAD_REQUEST,
    detail="Invalid payload",
)


# Bad: wrapping the API error in a status-specific helper
def bad_request(message: str) -> ApiError:
    return ApiError(status_code=HTTPStatus.BAD_REQUEST, detail=message)


raise bad_request("Invalid payload")
```

```python
# Good: log and raise inline at the failure site
try:
    response = await client.get_resource(...)
except third_party_client.ApiException as exc:
    logger.error("Resource fetch failed: %s", exc)

    raise ApiError(
        status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
        detail="Failed to fetch resource",
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
- Respect the project's central pagination limit — passing a larger limit should raise `ValueError`.
