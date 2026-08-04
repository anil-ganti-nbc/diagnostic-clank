"""Runtime identity contract.

Stage 0.5 draft. Validation of static models only; no runtime enforcement.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from clank_runtime.contracts.enums import ReleaseChannel
from clank_runtime.version import RUNTIME_CONTRACT_VERSION


class RuntimeIdentity(BaseModel):
    """Identifies a running clank instance and its contract compatibility.

    Every clank must be able to expose these fields (Amendment 3).
    """

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    contract_version: str = Field(
        default=RUNTIME_CONTRACT_VERSION,
        description="Version of the runtime contract this identity conforms to.",
        min_length=1,
    )
    runtime_version: str = Field(
        ...,
        description="Version of the clank-runtime package or equivalent runtime library.",
        min_length=1,
    )
    clank_id: str = Field(
        ...,
        min_length=1,
        pattern=r"^[a-z][a-z0-9-]*$",
        description="Stable identifier of the clank (lowercase, hyphen-separated).",
    )
    clank_version: str = Field(
        ...,
        min_length=1,
        description="Version of the specific clank implementation.",
    )
    release_channel: ReleaseChannel = Field(
        ...,
        description="Deployment channel classification.",
    )

    @field_validator("clank_id")
    @classmethod
    def _clank_id_not_reserved(cls, value: str) -> str:
        reserved = {"fleet", "runtime", "desktop", "central", "ingestion"}
        if value in reserved:
            raise ValueError(f"clank_id '{value}' is reserved for platform services")
        return value
