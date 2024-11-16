from typing import Any, Self

from swerex.runtime.abstract import (
    AbstractRuntime,
    Action,
    BashObservation,
    CloseBashSessionResponse,
    CloseResponse,
    CloseSessionRequest,
    CloseSessionResponse,
    Command,
    CommandResponse,
    CreateBashSessionResponse,
    CreateSessionRequest,
    CreateSessionResponse,
    IsAliveResponse,
    Observation,
    ReadFileRequest,
    ReadFileResponse,
    UploadRequest,
    UploadResponse,
    WriteFileRequest,
    WriteFileResponse,
)
from swerex.runtime.config import DummyRuntimeConfig


class DummyRuntime(AbstractRuntime):
    def __init__(
        self,
        **kwargs: Any,
    ):
        """This runtime does nothing.
        Useful for testing.

        Args:
            **kwargs: Keyword arguments (see `DummyRuntimeConfig` for details).
        """
        self.run_in_session_outputs: list[BashObservation] | BashObservation = BashObservation(exit_code=0)
        """Predefine returns of run_in_session. If set to list, will pop from list, else will 
        return the same value.
        """
        self._config = DummyRuntimeConfig(**kwargs)

    @classmethod
    def from_config(cls, config: DummyRuntimeConfig) -> Self:
        return cls(**config.model_dump())

    async def is_alive(self, *, timeout: float | None = None) -> IsAliveResponse:
        return IsAliveResponse(is_alive=True)

    async def create_session(self, request: CreateSessionRequest) -> CreateSessionResponse:
        if request.session_type == "bash":
            return CreateBashSessionResponse()
        msg = f"Unknown session type: {request.session_type}"
        raise ValueError(msg)

    async def run_in_session(self, action: Action) -> Observation:
        if isinstance(self.run_in_session_outputs, list):
            return self.run_in_session_outputs.pop(0)
        return self.run_in_session_outputs

    async def close_session(self, request: CloseSessionRequest) -> CloseSessionResponse:
        if request.session_type == "bash":
            return CloseBashSessionResponse()
        msg = f"Unknown session type: {request.session_type}"
        raise ValueError(msg)

    async def execute(self, command: Command) -> CommandResponse:
        return CommandResponse(exit_code=0)

    async def read_file(self, request: ReadFileRequest) -> ReadFileResponse:
        return ReadFileResponse()

    async def write_file(self, request: WriteFileRequest) -> WriteFileResponse:
        return WriteFileResponse()

    async def upload(self, request: UploadRequest) -> UploadResponse:
        return UploadResponse()

    async def close(self) -> CloseResponse:
        return CloseResponse()
