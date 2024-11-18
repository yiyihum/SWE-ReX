from typing import Callable

from swerex.deployment.hooks.abstract import DeploymentHook


class SetStatusDeploymentHook(DeploymentHook):
    def __init__(self, id: str, callable: Callable[[str], None]):
        self._callable = callable
        self._id = id

    def _update(self, message: str):
        self._callable(f"{self._id}: {message}")

    def on_custom_step(self, message: str):
        self._update(message)
