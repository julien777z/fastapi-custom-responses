# FastAPI Custom Responses

Provides normalized response objects and error handling for FastAPI applications. All errors — validation, HTTP, and unhandled exceptions — are returned in a consistent `{ "success": false, "error": "..." }` format with human-readable messages.

## Installation

```bash
pip install fastapi-custom-responses
```

## Quick Start

```py
from http import HTTPStatus
from fastapi_custom_responses import EXCEPTION_HANDLERS, ErrorResponse, ErrorResponseModel, Response, SuccessResponse
from fastapi import APIRouter, FastAPI, Request

router = APIRouter()

app = FastAPI(
    title="API",
    description="My API",
    version="1.0.0",
    exception_handlers=EXCEPTION_HANDLERS,
)

class Data(Response):
    example: str

@router.get(
    "/",
    response_model=Response[Data],
    responses={
        400: {"model": ErrorResponseModel, "description": "Bad request"},
        500: {"model": ErrorResponseModel, "description": "Internal server error"},
    },
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

    raise ErrorResponse(error="Your request is invalid.", status_code=HTTPStatus.BAD_REQUEST)
```

**Note:** When using OpenAPI generators, use `SuccessResponse` instead of `Response` if your endpoint has no data to return.

## Error Normalization

Passing `EXCEPTION_HANDLERS` to your FastAPI app registers handlers that normalize **all** errors into a consistent JSON shape:

```json
{
  "success": false,
  "error": "Human-readable error message"
}
```

### Handled Exception Types

| Exception | Status Code | Behavior |
|-----------|-------------|----------|
| `ErrorResponse` | Custom (default `400`) | Uses the provided `error` message directly |
| `RequestValidationError` | `400` | Pydantic validation errors are converted to human-readable messages (see below) |
| `HTTPException` | From exception | Uses the exception `detail` as the error message |
| `ValueError` | `400` | Uses `str(exc)` as the error message |
| `Exception` (catch-all) | `500` | Returns a generic `"An unexpected error occurred"` message |

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
# → { "success": false, "error": "You don't have permission to perform this action" }
```

Default messages for common status codes:

| Status Code | Default Message |
|-------------|-----------------|
| `401` | `"Authentication required"` |
| `403` | `"You don't have permission to perform this action"` |
| `404` | `"Resource not found"` |
| `400` | `"Invalid request"` |
| `500` | `"An unexpected error occurred"` |

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
  "error": "Field 'email' is required"
}
```

When multiple fields fail validation, messages are joined with periods:

```json
{
  "success": false,
  "error": "Field 'email' is required. Field 'age' must be a valid integer"
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
| `enum` | `Field 'status' must be one of: active, inactive` |
| `uuid_type` / `uuid_parsing` | `Field 'id' must be a valid UUID` |
| `string_too_short` | `Field 'name' must be at least 3 characters` |
| `string_too_long` | `Field 'name' must be at most 50 characters` |
| `too_short` / `too_long` | `Field 'items' must have at least 1 item` |
| `greater_than` / `less_than` | `Field 'age' must be greater than 0` |
| `greater_than_equal` / `less_than_equal` | `Field 'age' must be at least 18` |
| `value_error` | `Field 'email': invalid email format` |
| `json_invalid` | `Invalid JSON in request body` |

Any unrecognized error types fall back to the Pydantic error message prefixed with the field name.
