# FastAPI Custom Responses

Provides normalized response objects and error handling for FastAPI applications.

## Features

- One error envelope for every failure: validation, `HTTPException`, `ValueError`, and unhandled exceptions.
- Pydantic validation errors rewritten as human-readable messages instead of raw error arrays.
- A stable `code` naming the condition, typed as an enum you define.
- `fastapi_responses` to build FastAPI's `responses` mapping, documenting your codes in OpenAPI.
- Generic `Response[T]`, `SuccessResponse`, and `PaginatedResponse[T]` envelopes for success payloads.
- `ErrorResponseModel` for documenting error responses in OpenAPI.
- Default messages for common status codes via `ErrorResponse.from_status_code`.

## Installation

```bash
pip install fastapi-custom-responses
```

## Quick Start

```py
from http import HTTPStatus
from fastapi_custom_responses import EXCEPTION_HANDLERS, ErrorResponse, Response, SuccessResponse, fastapi_responses
from fastapi import APIRouter, FastAPI, Request
from enum import StrEnum
from pydantic import BaseModel

router = APIRouter()

app = FastAPI(
    title="API",
    description="My API",
    version="1.0.0",
    exception_handlers=EXCEPTION_HANDLERS,
)

class Data(BaseModel):
    example: str

class AccessErrorCode(StrEnum):
    PERMISSION_DENIED = "permission_denied"
    ACCOUNT_SUSPENDED = "account_suspended"

@router.get(
    "/",
    response_model=Response[Data],
    responses=fastapi_responses({
        HTTPStatus.FORBIDDEN: AccessErrorCode,
        HTTPStatus.INTERNAL_SERVER_ERROR: None,
    }),
)
async def index(_: Request) -> Response[Data]:
    """Index route."""

    return Response(
        success=True,
        data=Data(example="hello"),
    )

@router.get("/return-error")
async def error_route(_: Request) -> Response:
    """Error route."""

    raise ErrorResponse(
        error="Your account is suspended.",
        status_code=HTTPStatus.FORBIDDEN,
        code=AccessErrorCode.ACCOUNT_SUSPENDED,
    )
```

## Response Envelopes

| Envelope | Body |
|----------|------|
| `Response[T]` | `{ "success": true, "data": { ... } }` |
| `SuccessResponse` | `{ "success": true }` |
| `PaginatedResponse[T]` | `{ "success": true, "data": [ ... ], "meta": { "offset": 0, "limit": 10, "total": 1 } }` |

When using OpenAPI generators, use `SuccessResponse` instead of `Response` if your endpoint has no data to return.

Build a paginated response from a page of items and the bounds it was read with:

```py
return PaginatedResponse.build_page(items, offset=offset, limit=limit, total=total)
```

## Error Normalization

Register the handlers when you create the app:

```py
from fastapi import FastAPI
from fastapi_custom_responses import EXCEPTION_HANDLERS

app = FastAPI(exception_handlers=EXCEPTION_HANDLERS)
```

Every error then normalizes into one JSON shape:

```json
{
  "success": false,
  "error": "Human-readable error message",
  "code": "stable_error_identifier"
}
```

### Handled Exception Types

| Exception | Status Code | Code | Behavior |
|-----------|-------------|------|----------|
| `ErrorResponse` | Custom (default `400`) | Yours, if you pass one | Uses the provided `error` message directly |
| `RequestValidationError` | `400` | `validation_error` | Pydantic validation errors are converted to human-readable messages (see below) |
| `HTTPException` | From exception | None | Uses the exception `detail` as the error message |
| `ValueError` | `400` | `invalid_value` | Uses `str(exc)` as the error message |
| `Exception` (catch-all) | `500` | `internal_error` | Returns a generic `"An unexpected error occurred"` message |

`code` is present when a condition was named — by you, or by one of the library's own handlers. It is absent otherwise, rather than restating the status.

### Raising Errors

Raise `ErrorResponse` with a message and status code:

```py
from http import HTTPStatus
from fastapi_custom_responses import ErrorResponse

raise ErrorResponse(error="Resource not found", status_code=HTTPStatus.NOT_FOUND)
```

You can also create one from a status code alone, which maps to a default message:

```py
raise ErrorResponse.from_status_code(HTTPStatus.FORBIDDEN)
# { "success": false, "error": "You don't have permission to perform this action" }
```

Default messages for common status codes:

| Status Code | Default Message |
|-------------|-----------------|
| `401` | `"Authentication required"` |
| `403` | `"You don't have permission to perform this action"` |
| `404` | `"Resource not found"` |
| `400` | `"Invalid request"` |
| `500` | `"An unexpected error occurred"` |

Statuses outside the table fall back to the `500` message, so pass `error` explicitly for any other status:

```py
raise ErrorResponse(error="That name is already taken", status_code=HTTPStatus.CONFLICT)
# { "success": false, "error": "That name is already taken" }
```

### Error Codes

`error` is human-readable and may be reworded or localized. `code` is the stable identifier clients branch on. Declare your codes as a `StrEnum`, so a module that never imports this package can own them:

```py
from enum import StrEnum

class AccessErrorCode(StrEnum):
    PERMISSION_DENIED = "permission_denied"
    ACCOUNT_SUSPENDED = "account_suspended"
```

The library's own handlers name their conditions too; import `DefaultErrorCode` to branch on `validation_error`, `invalid_value`, and `internal_error`.

Pass a member when raising; both `ErrorResponse` and `from_status_code` accept it:

```py
raise ErrorResponse(
    error="Your account is suspended",
    status_code=HTTPStatus.FORBIDDEN,
    code=AccessErrorCode.ACCOUNT_SUSPENDED,
)
# { "success": false, "error": "Your account is suspended", "code": "account_suspended" }

raise ErrorResponse.from_status_code(HTTPStatus.FORBIDDEN, code=AccessErrorCode.PERMISSION_DENIED)
```

### Validation Error Normalization

When a request fails Pydantic validation, FastAPI normally returns a verbose JSON array of raw Pydantic errors. With `EXCEPTION_HANDLERS`, these are automatically converted into concise, human-readable messages.

**Before (default FastAPI):**

```json
{
  "detail": [
    {
      "type": "missing",
      "loc": ["body", "email"],
      "msg": "Field required",
      "input": {}
    }
  ]
}
```

**After (with `EXCEPTION_HANDLERS`):**

```json
{
  "success": false,
  "error": "Field 'email' is required",
  "code": "validation_error"
}
```

When multiple fields fail validation, messages are joined with periods:

```json
{
  "success": false,
  "error": "Field 'email' is required. Field 'age' must be a valid integer",
  "code": "validation_error"
}
```

Supported Pydantic error types and their human-readable formats:

| Error Type | Example Message |
|------------|-----------------|
| `missing` | `Field 'name' is required` |
| `string_type` | `Field 'name' must be a string` |
| `int_type` / `int_parsing` | `Field 'age' must be a valid integer` |
| `float_type` / `float_parsing` | `Field 'price' must be a valid number` |
| `bool_type` / `bool_parsing` | `Field 'active' must be a boolean` |
| `enum` | `Field 'status' must be one of: 'active' or 'inactive'` |
| `uuid_type` / `uuid_parsing` | `Field 'id' must be a valid UUID` |
| `string_too_short` | `Field 'name' must be at least 3 characters` |
| `string_too_long` | `Field 'name' must be at most 50 characters` |
| `too_short` / `too_long` | `Field 'items' must have at least 1 item` |
| `greater_than` / `less_than` | `Field 'age' must be greater than 0` |
| `greater_than_equal` / `less_than_equal` | `Field 'age' must be at least 18` |
| `value_error` | `Invalid email format` (uses the validator message directly) |
| `json_invalid` | `Invalid JSON in request body` |

Any unrecognized error types fall back to the Pydantic error message prefixed with the field name.

## Documenting Responses

`fastapi_responses` builds FastAPI's `responses` mapping. Give it an error code enum, `None` for the bare error envelope, or a success envelope:

```py
from fastapi_custom_responses import Response, SuccessResponse, fastapi_responses

@router.post(
    "/reports",
    responses=fastapi_responses({
        HTTPStatus.CREATED: Response[Report],
        HTTPStatus.ACCEPTED: SuccessResponse,
        HTTPStatus.FORBIDDEN: AccessErrorCode,
        HTTPStatus.NOT_FOUND: None,
    }),
)
```

Each error code enum becomes its own named schema in the OpenAPI document, so generated clients get a real union type per domain rather than a bare string:

```json
"AccessErrorCode": { "type": "string", "enum": ["permission_denied", "account_suspended"], "title": "AccessErrorCode" }
```

The statuses with default messages are described with the library's own message; the rest keep FastAPI's status phrase. Entries needing `headers`, custom media types, or `links` are written directly and merge with the result:

```py
responses={**fastapi_responses({HTTPStatus.FORBIDDEN: AccessErrorCode}), HTTPStatus.NOT_MODIFIED: {"headers": {...}}}
```

## Local Development

Install the project with its development dependencies:

```bash
poetry install -E dev
```

Run the test suite:

```bash
poetry run pytest tests/ -v
```

Format and lint:

```bash
poetry run black .
poetry run isort .
poetry run pylint fastapi_custom_responses/
```
