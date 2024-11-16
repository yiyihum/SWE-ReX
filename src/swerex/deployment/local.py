from typing import Any, Self

from swerex.deployment.abstract import AbstractDeployment
from swerex.deployment.config import LocalDeploymentConfig
from swerex.exceptions import DeploymentNotStartedError
from swerex.runtime.abstract import IsAliveResponse
from swerex.runtime.config import LocalRuntimeConfig
from swerex.runtime.local import LocalRuntime
from swerex.utils.log import get_logger

__all__ = ["LocalDeployment", "LocalDeploymentConfig"]


class LocalDeployment(AbstractDeployment):
    def __init__(
        self,
        **kwargs: Any,
    ):
        """The most boring of the deployment classes.
        This class does nothing but wrap around `Runtime` so you can switch out
        your deployment method.

        Args:
            **kwargs: Keyword arguments (see `LocalDeploymentConfig` for details).
        """
        self._runtime = None
        self.logger = get_logger("deploy")  # type: ignore
        self._config = LocalDeploymentConfig(**kwargs)

    @classmethod
    def from_config(cls, config: LocalDeploymentConfig) -> Self:
        return cls(**config.model_dump())

    async def is_alive(self, *, timeout: float | None = None) -> IsAliveResponse:
        """Checks if the runtime is alive. The return value can be
        tested with bool().

        Raises:
            DeploymentNotStartedError: If the deployment was not started.
        """
        if self._runtime is None:
            return IsAliveResponse(is_alive=False, message="Runtime is None.")
        return await self._runtime.is_alive(timeout=timeout)

    async def start(self):
        """Starts the runtime."""
        self._runtime = LocalRuntime.from_config(LocalRuntimeConfig())

    async def stop(self):
        """Stops the runtime."""
        if self._runtime is not None:
            await self._runtime.close()
            self._runtime = None

    @property
    def runtime(self) -> LocalRuntime:
        """Returns the runtime if running.

        Raises:
            DeploymentNotStartedError: If the deployment was not started.
        """
        if self._runtime is None:
            raise DeploymentNotStartedError()
        return self._runtime
