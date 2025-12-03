# FastAPI Custom Responses

Provides normalized response objects and error handling

## Example

```py
from http import HTTPStatus
from fastapi_custom_responses import EXCEPTION_HANDLERS, ErrorResponse, ErrorResponseModel, Response
from fastapi import APIRouter, FastAPI, Request

# Initialize FastAPI
router = APIRouter()

app = FastAPI(
    title="API",
    description="My API",
    version="1.0.0",
    exception_handlers=EXCEPTION_HANDLERS, # Use error handler from library
)

# Define data model
class Data(Response):
    example: str

# Routes
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

@router.get(
    "/return-error",
    response_model=Response[Data],
    responses={
        HTTPStatus.FORBIDDEN: {
            "description": "User belongs to a different organization",
            "model": ErrorResponseModel,
            "content": {
                "application/json": {
                    "example": {
                        "success": False,
                        "error": "User belongs to a different organization",
                    },
                },
            },
        },
    },
)
async def error_route(_: Request) -> Response:
    """Error route."""

    raise ErrorResponse(error="Your request is invalid.", status_code=HTTPStatus.BAD_REQUEST)
```