from typing import Any, Self

from swerex.deployment.abstract import AbstractDeployment
from swerex.deployment.config import DummyDeploymentConfig
from swerex.runtime.abstract import IsAliveResponse
from swerex.runtime.dummy import DummyRuntime


class DummyDeployment(AbstractDeployment):
    def __init__(self, **kwargs: Any):
        """This deployment does nothing.
        Useful for testing.

        Args:
            **kwargs: Keyword arguments (see `DummyDeploymentConfig` for details).
        """
        self._config = DummyDeploymentConfig(**kwargs)
        self._runtime = DummyRuntime()  # type: ignore

    @classmethod
    def from_config(cls, config: DummyDeploymentConfig) -> Self:
        return cls(**config.model_dump())

    async def is_alive(self, *, timeout: float | None = None) -> IsAliveResponse:
        return IsAliveResponse(is_alive=True)

    async def start(self):
        pass

    async def stop(self):
        pass

    @property
    def runtime(self) -> DummyRuntime:
        return self._runtime

    @runtime.setter
    def runtime(self, runtime: DummyRuntime):
        self._runtime = runtime
