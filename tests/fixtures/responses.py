from http import HTTPStatus
from typing import Final, Literal

import pytest
from fastapi import FastAPI, HTTPException

from fastapi_custom_responses import (
    EXCEPTION_HANDLERS,
    EXCEPTION_RESPONSES,
    DefaultErrorCode,
    ErrorResponse,
    ErrorResponseModel,
    PaginatedResponse,
    Response,
    SuccessResponse,
)
from tests.fixtures.models import (
    AccessErrorCode,
    Color,
    ConstrainedPayload,
    RaisedErrorCase,
    ResponseMetadata,
    ValidationPayload,
    ValueErrorPayload,
)

SECRET_TOKEN: Final[str] = "sk-live-must-never-reach-the-wire"

SAMPLE_PAYLOAD: Final[ValidationPayload] = ValidationPayload(name="Alice", age=30, email="alice@example.com")

VALID_CONSTRAINED_PAYLOAD: Final[ConstrainedPayload] = ConstrainedPayload(
    username="alice", score=50, rating=2.5, color=Color.RED, tags=["a"]
)


VALUE_ERROR_PAYLOAD: Final[ValueErrorPayload] = ValueErrorPayload(code="1234")


RAISED_ERROR_CASES: Final[dict[str, RaisedErrorCase]] = {
    "default_status": RaisedErrorCase(
        build_exception=lambda: ErrorResponse("Custom error message"),
        status_code=HTTPStatus.BAD_REQUEST,
        expected_body=ErrorResponseModel(success=False, error="Custom error message"),
    ),
    "custom_status": RaisedErrorCase(
        build_exception=lambda: ErrorResponse("Item not found", HTTPStatus.NOT_FOUND),
        status_code=HTTPStatus.NOT_FOUND,
        expected_body=ErrorResponseModel(success=False, error="Item not found"),
    ),
    "with_code": RaisedErrorCase(
        build_exception=lambda: ErrorResponse(
            "Custom error message",
            HTTPStatus.FORBIDDEN,
            code=AccessErrorCode.PERMISSION_DENIED,
        ),
        status_code=HTTPStatus.FORBIDDEN,
        expected_body=ErrorResponseModel(
            success=False, error="Custom error message", code=AccessErrorCode.PERMISSION_DENIED
        ),
    ),
    "from_status_code": RaisedErrorCase(
        build_exception=lambda: ErrorResponse.from_status_code(HTTPStatus.FORBIDDEN),
        status_code=HTTPStatus.FORBIDDEN,
        expected_body=ErrorResponseModel(success=False, error="Forbidden"),
    ),
    "from_status_code_with_code": RaisedErrorCase(
        build_exception=lambda: ErrorResponse.from_status_code(
            HTTPStatus.FORBIDDEN, code=AccessErrorCode.PERMISSION_DENIED
        ),
        status_code=HTTPStatus.FORBIDDEN,
        expected_body=ErrorResponseModel(
            success=False, error="Forbidden", code=AccessErrorCode.PERMISSION_DENIED
        ),
    ),
    "http_exception": RaisedErrorCase(
        build_exception=lambda: HTTPException(
            status_code=HTTPStatus.UNAUTHORIZED, detail="Not authenticated"
        ),
        status_code=HTTPStatus.UNAUTHORIZED,
        expected_body=ErrorResponseModel(success=False, error="Not authenticated"),
    ),
    "http_exception_with_a_structured_detail": RaisedErrorCase(
        build_exception=lambda: HTTPException(status_code=HTTPStatus.CONFLICT, detail={"reason": "taken"}),
        status_code=HTTPStatus.CONFLICT,
        expected_body=ErrorResponseModel(success=False, error="{'reason': 'taken'}"),
    ),
    "value_error": RaisedErrorCase(
        build_exception=lambda: ValueError("Invalid value provided"),
        status_code=HTTPStatus.BAD_REQUEST,
        expected_body=ErrorResponseModel(
            success=False, error="Invalid value provided", code=DefaultErrorCode.INVALID_VALUE
        ),
    ),
    "unhandled_exception": RaisedErrorCase(
        build_exception=lambda: RuntimeError("Something went wrong"),
        status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
        expected_body=ErrorResponseModel(
            success=False, error="Internal Server Error", code=DefaultErrorCode.INTERNAL_ERROR
        ),
    ),
}


METADATA_BODY: Final[ErrorResponseModel] = ErrorResponseModel(
    success=False, error="Access denied", code=AccessErrorCode.PERMISSION_DENIED
)
METADATA: Final[ResponseMetadata] = ResponseMetadata(
    description="Access to this resource was refused",
    explicit_refusal="Explicit application refusal",
    cancelled="Request cancelled",
    client_failures="Other client failures",
    other_failures="Other failures",
    operation_id="read_resource",
)


@pytest.fixture
def app() -> FastAPI:
    """Minimal FastAPI app with the library's exception handlers registered."""

    app = FastAPI(exception_handlers=EXCEPTION_HANDLERS, responses=EXCEPTION_RESPONSES)

    @app.post("/validate")
    async def validate_endpoint(payload: ValidationPayload) -> dict:
        return {"success": True, "data": payload.model_dump()}

    @app.post("/validate-constrained")
    async def validate_constrained_endpoint(payload: ConstrainedPayload) -> dict:
        return {"success": True, "data": payload.model_dump()}

    @app.post("/validate-value-error")
    async def validate_value_error_endpoint(payload: ValueErrorPayload) -> dict:
        return {"success": True, "data": payload.model_dump()}

    @app.get("/response-with-data")
    async def response_with_data_endpoint() -> Response[ValidationPayload]:
        return Response(success=True, data=SAMPLE_PAYLOAD)

    @app.get("/success-response")
    async def success_response_endpoint() -> SuccessResponse:
        return SuccessResponse(success=True)

    @app.get("/paginated-response")
    async def paginated_response_endpoint() -> PaginatedResponse[ValidationPayload]:
        return PaginatedResponse.build_page([SAMPLE_PAYLOAD], offset=0, limit=10, total=1)

    @app.get("/invalid-model")
    async def invalid_model_endpoint() -> SuccessResponse:
        ValidationPayload.model_validate({"token": SECRET_TOKEN})

        return SuccessResponse(success=True)

    @app.get("/raise/{case_name}")
    async def raise_error_endpoint(case_name: str) -> None:
        raise RAISED_ERROR_CASES[case_name].build_exception()

    return app


@pytest.fixture
def documented_app() -> FastAPI:
    """App whose routes document their responses."""

    app = FastAPI()

    @app.post(
        "/reports",
        status_code=HTTPStatus.CREATED,
        response_model=Response[ValidationPayload],
        responses={
            HTTPStatus.BAD_REQUEST: {"model": ErrorResponseModel[AccessErrorCode | DefaultErrorCode]},
            HTTPStatus.FORBIDDEN: {"model": ErrorResponseModel[AccessErrorCode]},
            HTTPStatus.NOT_FOUND: {"model": ErrorResponseModel},
        },
    )
    async def reports() -> Response[ValidationPayload]:
        return Response(success=True, data=SAMPLE_PAYLOAD)

    @app.post(
        "/selected",
        responses={
            HTTPStatus.FORBIDDEN: {
                "model": ErrorResponseModel[
                    Literal[AccessErrorCode.PERMISSION_DENIED, DefaultErrorCode.INVALID_VALUE]
                ]
            },
            HTTPStatus.CONFLICT: {"model": ErrorResponseModel[Literal[AccessErrorCode.ACCOUNT_SUSPENDED]]},
        },
    )
    async def selected() -> SuccessResponse:
        return SuccessResponse(success=True)

    return app


@pytest.fixture
def response_metadata_app() -> FastAPI:
    """App combining handler documentation with native response metadata and explicit statuses."""

    app = FastAPI(exception_handlers=EXCEPTION_HANDLERS, responses=EXCEPTION_RESPONSES)

    @app.get(
        "/metadata",
        operation_id=METADATA.operation_id,
        response_model=SuccessResponse,
        responses={
            HTTPStatus.FORBIDDEN: {
                "model": ErrorResponseModel[Literal[AccessErrorCode.PERMISSION_DENIED]],
                "description": METADATA.description,
                "headers": {"Retry-After": {"schema": {"type": "integer"}}},
                "content": {
                    "application/json": {
                        "examples": {
                            "denied": {"value": METADATA_BODY.model_dump(mode="json", exclude_none=True)}
                        }
                    },
                    "text/plain": {"schema": {"type": "string"}},
                },
                "links": {"resource": {"operationId": METADATA.operation_id}},
            },
            HTTPStatus.UNPROCESSABLE_ENTITY: {
                "model": ErrorResponseModel,
                "description": METADATA.explicit_refusal,
            },
            499: {"description": METADATA.cancelled},
            "4XX": {"model": ErrorResponseModel, "description": METADATA.client_failures},
            "default": {"model": ErrorResponseModel, "description": METADATA.other_failures},
        },
    )
    async def metadata(count: int) -> SuccessResponse:
        """Expose request validation and a deliberately raised documented-status error."""

        if count == 0:
            raise ErrorResponse(
                METADATA_BODY.error, HTTPStatus.FORBIDDEN, code=AccessErrorCode.ACCOUNT_SUSPENDED
            )

        return SuccessResponse(success=True)

    return app
