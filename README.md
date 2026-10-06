# FastAPI Custom Responses

Provides normalized response objects and error handling for FastAPI applications.

## Features

- One error envelope for every failure: validation, `HTTPException`, `ValueError`, and unhandled exceptions.
- Pydantic validation errors rewritten as human-readable messages instead of raw error arrays.
- A stable `code` naming the condition, typed as an enum.
- Native FastAPI response declarations for error codes, descriptions, examples, headers, media types and links.
- Generic `Response[T]`, `SuccessResponse`, and `PaginatedResponse[T]` envelopes for success payloads.
- `ErrorResponseModel` as both the error body the handlers emit and the schema documenting it.
- `ErrorResponse.from_status_code` for an error carrying a status's standard HTTP phrase.

## Quick Start

```bash
pip install fastapi-custom-responses
```

```py
from http import HTTPStatus
from fastapi_custom_responses import (
    EXCEPTION_HANDLERS,
    DefaultErrorCode,
    ErrorResponse,
    Response,
    ErrorResponseModel,
    EXCEPTION_RESPONSES,
)
from fastapi import APIRouter, FastAPI
from enum import StrEnum
from pydantic import BaseModel

router = APIRouter()

app = FastAPI(
    title="API",
    description="My API",
    version="1.0.0",
    exception_handlers=EXCEPTION_HANDLERS,
    responses=EXCEPTION_RESPONSES,
)

class Data(BaseModel):
    example: str

class OrderErrorCode(StrEnum):
    ORDER_LOCKED = "order_locked"
    PAYMENT_DECLINED = "payment_declined"

@router.get(
    "/",
    operation_id="read_example",
    response_model=Response[Data],
    responses={HTTPStatus.FORBIDDEN: {"model": ErrorResponseModel[OrderErrorCode]}},
)
async def index() -> Response[Data]:
    """Index route."""

    return Response(
        success=True,
        data=Data(example="hello"),
    )

@router.get(
    "/return-error",
    responses={HTTPStatus.FORBIDDEN: {"model": ErrorResponseModel[OrderErrorCode]}},
)
async def error_route() -> Response[Data]:
    """Error route."""

    raise ErrorResponse(
        error="This order is locked.",
        status_code=HTTPStatus.FORBIDDEN,
        code=OrderErrorCode.ORDER_LOCKED,
    )

app.include_router(router)
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
from fastapi_custom_responses import EXCEPTION_HANDLERS, EXCEPTION_RESPONSES

app = FastAPI(exception_handlers=EXCEPTION_HANDLERS, responses=EXCEPTION_RESPONSES)
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
| `HTTPException` | From exception | None | Uses the exception `detail`; also covers the `404` and `405` the router raises itself |
| `ValueError` | `400` | `invalid_value` | Uses `str(exc)` as the error message |
| `ValidationError` (Pydantic) | `500` | `internal_error` | A model failed to validate inside your app; logged and reported generically so its details stay out of the body |
| `Exception` (catch-all) | `500` | `internal_error` | Reports the status phrase so the exception stays out of the body |

`code` is present when a condition was named — by you, or by one of the library's own handlers. It is absent otherwise, rather than restating the status.

### Raising Errors

Raise `ErrorResponse` with a message and status code:

```py
from http import HTTPStatus
from fastapi_custom_responses import ErrorResponse

raise ErrorResponse(error="Resource not found", status_code=HTTPStatus.NOT_FOUND)
```

Or create one from the status alone, which carries that status's standard HTTP phrase:

```py
raise ErrorResponse.from_status_code(HTTPStatus.FORBIDDEN)
# { "success": false, "error": "Forbidden" }
```

The library ships no wording of its own, so pass `error` whenever the phrase is too terse for the reader:

```py
raise ErrorResponse(error="That name is already taken", status_code=HTTPStatus.CONFLICT)
# { "success": false, "error": "That name is already taken" }
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

## Error Codes

`error` is human-readable and may be reworded or localized. `code` is the stable identifier clients branch on. Declare your codes as a `StrEnum`, so a module that never imports this package can own them:

```py
from enum import StrEnum

class OrderErrorCode(StrEnum):
    ORDER_LOCKED = "order_locked"
    PAYMENT_DECLINED = "payment_declined"
```

The library's own handlers name their conditions too; import `DefaultErrorCode` to branch on `validation_error`, `invalid_value`, and `internal_error`.

Pass a member when raising; both `ErrorResponse` and `from_status_code` accept it:

```py
raise ErrorResponse(
    error="This order is locked",
    status_code=HTTPStatus.FORBIDDEN,
    code=OrderErrorCode.ORDER_LOCKED,
)
# { "success": false, "error": "This order is locked", "code": "order_locked" }

raise ErrorResponse.from_status_code(HTTPStatus.FORBIDDEN, code=OrderErrorCode.ORDER_LOCKED)
```

## Documenting Responses

Use FastAPI's native `response_model` for the main success response and `responses` for additional responses:

```py
from typing import Literal
from fastapi_custom_responses import ErrorResponseModel, Response

@router.post(
    "/reports",
    status_code=HTTPStatus.CREATED,
    response_model=Response[Data],
    responses={
        HTTPStatus.FORBIDDEN: {
            "model": ErrorResponseModel[Literal[OrderErrorCode.ORDER_LOCKED]],
            "description": "This order is locked",
            "headers": {"Retry-After": {"schema": {"type": "integer"}}},
            "content": {
                "application/json": {
                    "examples": {"locked": {"value": {
                        "success": False,
                        "error": "This order is locked",
                        "code": "order_locked",
                    }}}
                },
                "text/plain": {"schema": {"type": "string"}},
            },
            "links": {"example": {"operationId": "read_example"}},
        },
    },
)
async def reports() -> Response[Data]:
    return Response(success=True, data=Data(example="hello"))
```

An entire enum can be used as `ErrorResponseModel[OrderErrorCode]`. Union enum types to document
several domains, or use `Literal[OrderErrorCode.ORDER_LOCKED, DefaultErrorCode.INVALID_VALUE]` to
select individual members. Pydantic produces the selected-value schema and rejects other values
when that model validates a body. The `code` field remains optional and nullable.

FastAPI accepts integer response codes, `HTTPStatus` values, status ranges such as `"4XX"`, and
`"default"`. Keep metadata and the model in the same response entry: replacing an entry with
`{403: {"description": "..."}}` also discards its model. Native response declarations preserve
these fields together without a separate conversion helper.

`response_model` validates and serializes the main response. Additional `responses` declarations
only document alternatives; they do not validate a body returned by an exception handler or a
`Response` object. The handler remains responsible for emitting the documented code.

### Handler Documentation

Configure the matching native declarations alongside the handlers:

```py
app = FastAPI(exception_handlers=EXCEPTION_HANDLERS, responses=EXCEPTION_RESPONSES)
```

`EXCEPTION_RESPONSES` documents the handlers' `400` and `500` models and the general `4XX`/`5XX`
error envelopes. FastAPI's native `4XX` declaration suppresses its automatic standard `422`
validation response, matching this package's runtime `400` envelope. Explicitly declared `422`
responses are preserved. Register both mappings before adding routes; registering handlers alone
does not change FastAPI's OpenAPI document.

Route and router response declarations override matching application entries. When a route raises
its own codes at `400` or `500`, document the union of its codes and the handler codes there.

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
poetry run pylint fastapi_custom_responses/ .github/scripts/
```
