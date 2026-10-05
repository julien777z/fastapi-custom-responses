from enum import StrEnum
from functools import cached_property
from types import UnionType
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, GetCoreSchemaHandler, GetPydanticSchema
from pydantic_core.core_schema import CoreSchema, literal_schema


class DefaultErrorCode(StrEnum):
    """Codes for the conditions the library's own handlers detect."""

    VALIDATION_ERROR = "validation_error"
    INVALID_VALUE = "invalid_value"
    INTERNAL_ERROR = "internal_error"


class ErrorResponseModel[CodeT: str](BaseModel):
    """Body every error response carries, and the schema documenting it in OpenAPI."""

    success: Literal[False]
    error: str
    code: CodeT | None = None


class ConstraintRule(BaseModel):
    """Maps a Pydantic constraint error type to its `ctx` key, message template, and fallback."""

    ctx_key: str
    template: str
    fallback: str


class SelectedErrorCodes(BaseModel):
    """The enum members one error response admits and documents."""

    model_config = ConfigDict(frozen=True)

    codes: tuple[StrEnum, ...] = Field(min_length=1)

    @cached_property
    def code_metadata(self) -> GetPydanticSchema:
        """The native Pydantic metadata for the selected error-code values."""

        def _code_schema(_source_type: object, _handler: GetCoreSchemaHandler) -> CoreSchema:
            return literal_schema([code.value for code in self.codes])

        return GetPydanticSchema(_code_schema)


type ResponseSpec = type[StrEnum] | type[BaseModel] | UnionType | SelectedErrorCodes | None
