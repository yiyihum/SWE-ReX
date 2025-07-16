import logging
from typing import Any

from typing_extensions import Self

from swerex.deployment.abstract import AbstractDeployment
from swerex.deployment.config import BwrapDeploymentConfig
from swerex.deployment.hooks.abstract import CombinedDeploymentHook, DeploymentHook
from swerex.exceptions import DeploymentNotStartedError
from swerex.runtime.abstract import IsAliveResponse
from swerex.runtime.bwrap import BwrapRuntime
from swerex.utils.log import get_logger

__all__ = ["BwrapDeployment", "BwrapDeploymentConfig"]


class BwrapDeployment(AbstractDeployment):
    def __init__(
        self,
        *,
        logger: logging.Logger | None = None,
        **kwargs: Any,
    ):
        self._runtime = None
        self.logger = logger or get_logger("rex-deploy")
        self._config = BwrapDeploymentConfig(**kwargs)
        self._hooks = CombinedDeploymentHook()

    def add_hook(self, hook: DeploymentHook):
        self._hooks.add_hook(hook)

    @classmethod
    def from_config(cls, config: BwrapDeploymentConfig) -> Self:
        return cls(**config.model_dump())

    async def is_alive(self, *, timeout: float | None = None) -> IsAliveResponse:
        if self._runtime is None:
            return IsAliveResponse(is_alive=False, message="Runtime is None.")
        return await self._runtime.is_alive(timeout=timeout)

    async def start(self):
        """Starts the runtime."""
        self._runtime = BwrapRuntime(logger=self.logger)

    async def stop(self):
        if self._runtime is not None:
            await self._runtime.close()
            self._runtime = None

    @property
    def runtime(self) -> BwrapRuntime:
        if self._runtime is None:
            raise DeploymentNotStartedError()
        return self._runtime
