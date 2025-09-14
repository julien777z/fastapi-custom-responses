# FastAPI Custom Responses

Provides normalized response objects and error handling

## Example

```py
from http import HTTPStatus
from fastapi_custom_responses import EXCEPTION_HANDLERS, Response
from fastapi import APIRouter

# Initialize FastAPI
router = APIRouter()

app = FastAPI(
    title="API",
    description="My API",
    version="1.0.0",
    lifespan=lifespan,
    exception_handlers=EXCEPTION_HANDLERS, # Use error handler from library
)

# Define data model
class Data(Response):
    example: str

# Routes
@router.get(
    "/",
    response_model=Response[Data], # Use Data model
)
async def index(_: FastAPIRequest) -> Response[Data]:
    """Index route."""

    return Response(
        success=True,
        data=Data(example="hello"),
    )

@router.get(
    "/return-error",
    response_model=Response[Data], # Use Data model
)
async def error_route(_: FastAPIRequest) -> Response:
    """Index route."""

    raise ErrorResponse(error="Your request is invalid.", status_code=HTTPStatus.BAD_REQUEST)
```