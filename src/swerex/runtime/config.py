from pydantic import BaseModel

from swerex.runtime.abstract import AbstractRuntime


class LocalRuntimeConfig(BaseModel):
    """Configuration for a local runtime."""


class RemoteRuntimeConfig(BaseModel):
    auth_token: str
    """The token to use for authentication."""
    host: str = "http://127.0.0.1"
    """The host to connect to."""
    port: int | None = None
    """The port to connect to."""
    timeout: float = 0.15


class DummyRuntimeConfig(BaseModel):
    """Configuration for a dummy runtime."""


RuntimeConfig = LocalRuntimeConfig | RemoteRuntimeConfig | DummyRuntimeConfig


def get_runtime(config: RuntimeConfig) -> AbstractRuntime:
    if isinstance(config, LocalRuntimeConfig):
        from swerex.runtime.local import LocalRuntime

        return LocalRuntime.from_config(config)
    if isinstance(config, RemoteRuntimeConfig):
        from swerex.runtime.remote import RemoteRuntime

        return RemoteRuntime.from_config(config)
    if isinstance(config, DummyRuntimeConfig):
        from swerex.runtime.dummy import DummyRuntime

        return DummyRuntime.from_config(config)

    msg = f"Unknown runtime type: {type(config)}"
    raise ValueError(msg)
