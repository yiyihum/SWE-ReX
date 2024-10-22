import subprocess
import time
import uuid
import modal
import os
import boto3
import asyncio
from botocore.exceptions import NoCredentialsError
from pathlib import Path

import swerex
from swerex import REMOTE_EXECUTABLE_NAME
from swerex.deployment.abstract import AbstractDeployment
from swerex.runtime.abstract import IsAliveResponse
from swerex.runtime.remote import RemoteRuntime
from swerex.utils.log import get_logger
from swerex.utils.wait import _wait_until_alive

__all__ = ["ModalDeployment"]


def _get_image(image_name: str | None = None, dockerfile: str | None = None) -> modal.Image:
    # assert only one of image_name or dockerfile is provided
    assert image_name is not None or dockerfile is not None, "Either image_name or dockerfile must be provided"
    # assert not both image_name and dockerfile are provided
    assert not (image_name is not None and dockerfile is not None), "Both image_name and dockerfile cannot be provided"
    if dockerfile is not None:
        context_mount = modal.Mount.from_local_dir(
            local_path=Path(swerex.__file__).parent.parent.parent,
            remote_path=".",  # to current WORKDIR
        )
        return modal.Image.from_dockerfile(dockerfile, context_mount=context_mount)
    if "amazonaws.com" in image_name:
        try:
            session = boto3.Session()
            credentials = session.get_credentials()
            aws_access_key_id = credentials.access_key
            aws_secret_access_key = credentials.secret_key
            secret = modal.Secret.from_dict(
                {
                    "AWS_ACCESS_KEY_ID": aws_access_key_id,
                    "AWS_SECRET_ACCESS_KEY": aws_secret_access_key,
                }
            )
            return modal.Image.from_ecr(
                image_name,
                secrets=[secret],
            )
        except NoCredentialsError:
            raise ValueError("AWS credentials not found. Please configure your AWS credentials.")
    else:
        if os.environ.get("DOCKER_USERNAME") and os.environ.get("DOCKER_PASSWORD"):
            secret = modal.Secret.from_dict(
                {
                    "DOCKER_USERNAME": os.environ["DOCKER_USERNAME"],
                    "DOCKER_PASSWORD": os.environ["DOCKER_PASSWORD"],
                }
            )
            secrets = [secret]
        else:
            secrets = None
        return modal.Image.from_registry(image_name, secrets=secrets)


class ModalDeployment(AbstractDeployment):
    def __init__(
        self,
        image_name: str | None = None,
        dockerfile: str | None = None,
        port: int = 8880,  # this is only used internally by the container, the runtime will connect to the modal tunnel url without the port
        container_timeout: float = 1800,
        runtime_timeout: float = 0.4,
        **modal_args,
    ):
        self._dockerfile = dockerfile
        self._image = _get_image(image_name, dockerfile)
        self._image_name = image_name
        self._runtime: RemoteRuntime | None = None
        self._container_timeout = container_timeout
        self._sandbox: modal.Sandbox | None = None
        self._port = port
        self._container_name = None
        self.logger = get_logger("deploy")
        self._app = modal.App.lookup("swe-rex", create_if_missing=True)
        self._runtime_timeout = runtime_timeout
        self._modal_args = modal_args

    @property
    def container_name(self) -> str | None:
        return self._container_name

    async def is_alive(self, *, timeout: float | None = None) -> IsAliveResponse:
        if self._runtime is None:
            msg = "Runtime not started"
            raise RuntimeError(msg)
        if self._sandbox is None:
            msg = "Container process not started"
            raise RuntimeError(msg)
        if self._sandbox.poll() is not None:
            msg = "Container process terminated."
            output = "stdout:\n" + self._sandbox.stdout.read()  # type: ignore
            output += "\nstderr:\n" + self._sandbox.stderr.read()  # type: ignore
            msg += "\n" + output
            raise RuntimeError(msg)
        return await self._runtime.is_alive(timeout=timeout)
    
    def _get_container_name(self) -> str:
        if self._image_name is None:
            return self._dockerfile
        return self._image_name

    async def _wait_until_alive(self, timeout: float | None = None):
        return await _wait_until_alive(self.is_alive, timeout=timeout, function_timeout=self._runtime._timeout)

    async def start(
        self,
        *,
        timeout: float | None = None,
    ):
        self.logger.info(f"Starting modal sandbox with image from {self._get_container_name()}")
        self._sandbox = modal.Sandbox.create(
            "/bin/bash",
            "-c",
            f"""{REMOTE_EXECUTABLE_NAME} --port {self._port} 2>&1""",  # forward stderr to stdout since modal doesn't support non-multiplexed ports
            image=self._image,
            timeout=timeout,
            unencrypted_ports=[self._port],
            app=self._app,
            **self._modal_args,
        )
        tunnel = self._sandbox.tunnels()[self._port]
        self.logger.info(f"Sandbox created with id {self._sandbox.object_id}")
        await asyncio.sleep(0.1)
        self.logger.info(f"Starting runtime at {tunnel.url}")
        self._runtime = RemoteRuntime(host=tunnel.url, timeout=self._runtime_timeout)
        t0 = time.time()
        await self._wait_until_alive(timeout=timeout)
        self.logger.info(f"Runtime started in {time.time() - t0:.2f}s")

    async def stop(self):
        if self._runtime is not None:
            await self._runtime.close()
            self._runtime = None
        if self._sandbox is not None and not self._sandbox.poll():
            self._sandbox.terminate()
        self._sandbox = None
        self._container_name = None

    @property
    def runtime(self) -> RemoteRuntime:
        if self._runtime is None:
            msg = "Runtime not started"
            raise RuntimeError(msg)
        return self._runtime
