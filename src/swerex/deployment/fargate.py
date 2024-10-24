import hashlib
import time
import boto3
import uuid
import json

from urllib.parse import quote

from swerex import REMOTE_EXECUTABLE_NAME
from swerex.deployment.abstract import AbstractDeployment
from swerex.runtime.abstract import IsAliveResponse
from swerex.runtime.remote import RemoteRuntime
from swerex.utils.log import get_logger
from swerex.utils.wait import _wait_until_alive
from swerex.utils.aws import (
    get_cluster_arn,
    get_execution_role_arn,
    get_task_definition,
    get_default_vpc_and_subnet,
    get_security_group,
    get_fargate_family_name,
    run_fargate_task,
    get_cloudwatch_log_url,
    get_public_ip,
)


class FargateDeployment(AbstractDeployment):
    def __init__(
        self,
        image_name: str,
        port: int = 8880,
        cluster_name: str = "swe-rex-cluster",
        execution_role_name: str = "swe-rex-execution-role",
        security_group_name: str = "swe-rex-deployment-sg",
        fargate_args: dict | None = None,
        container_timeout: float = 60 * 15,
    ):
        self._image_name = image_name
        self._runtime: RemoteRuntime | None = None
        self._port = port
        self._container_process = None
        if fargate_args is None:
            fargate_args = {}
        self._fargate_args = fargate_args
        self._container_name = None
        self._container_timeout = container_timeout
        self._cluster_name = cluster_name
        self._execution_role_name = execution_role_name
        self._security_group_name = security_group_name
        self._cluster_arn = get_cluster_arn(self._cluster_name)
        self.logger = get_logger("deploy")
        # we need to setup ecs and ec2 to run containers
        self._task_definition_arn = None
        self._vpc_id = None
        self._subnet_id = None
        self._task_arn = None
        self._security_group_id = None
        self._init_task_definition()
    
    def _init_task_definition(self):
        self._execution_role_arn = get_execution_role_arn(role_name=self._execution_role_name)
        self._task_definition = get_task_definition(
            image_name=self._image_name,
            port=self._port,
            execution_role_arn=self._execution_role_arn,
        )
        self._task_definition_arn = self._task_definition['taskDefinitionArn']
        self._vpc_id, self._subnet_id = get_default_vpc_and_subnet()
        self._security_group_id = get_security_group(
            vpc_id=self._vpc_id,
            port=self._port,
            security_group_name=self._security_group_name,
        )

    def _get_container_name(self) -> str:
        return get_fargate_family_name(self._image_name, self._port)
    
    @property
    def container_name(self) -> str | None:
        return self._container_name

    async def is_alive(self, *, timeout: float | None = None) -> IsAliveResponse:
        if self._runtime is None:
            msg = "Runtime not started"
            raise RuntimeError(msg)
        if self._task_arn is None:
            msg = "Container process not started."
            raise RuntimeError(msg)
        else:
            # check if the task is running
            ecs_client = boto3.client('ecs')
            task_details = ecs_client.describe_tasks(cluster=self._cluster_arn, tasks=[self._task_arn])
            if task_details['tasks'][0]['lastStatus'] != "RUNNING":
                msg = f"Container process not running: {task_details['tasks'][0]['lastStatus']}"
                raise RuntimeError(msg)
        return await self._runtime.is_alive(timeout=timeout)

    async def _wait_until_alive(self, timeout: float | None = None):
        return await _wait_until_alive(self.is_alive, timeout=timeout, function_timeout=self._container_timeout)

    async def start(
        self,
        *,
        timeout: float | None = None,
    ):
        self._container_name = self._get_container_name()
        self.logger.info(f"Starting runtime with container name {self._container_name}")
        self._task_arn = run_fargate_task(
            command=f"timeout {self._container_timeout}s {REMOTE_EXECUTABLE_NAME} --port {self._port} 2>&1",
            name=self._container_name,
            task_definition_arn=self._task_definition_arn,
            subnet_id=self._subnet_id,
            security_group_id=self._security_group_id,
            cluster_arn=self._cluster_arn,
            **self._fargate_args,
        )
        self.logger.info(f"Container task submitted: {self._task_arn} - waiting for it to start...")
        # wait until the container is running
        t0 = time.time()
        ecs_client = boto3.client('ecs')
        waiter = ecs_client.get_waiter('tasks_running')
        waiter.wait(cluster=self._cluster_arn, tasks=[self._task_arn])
        self.logger.info(f"Fargate container started in {time.time() - t0:.2f}s")
        try:
            log_url = get_cloudwatch_log_url(
                task_arn=self._task_arn,
                task_definition=self._task_definition,
                container_name=self._container_name,
            )
            self.logger.info(f"Monitor logs at:\n{log_url}")
        except Exception as e:
            self.logger.warning(f"Failed to get CloudWatch Logs URL: {str(e)}")
        public_ip = get_public_ip(self._task_arn, self._cluster_arn)
        self.logger.info(f"Container public IP: {public_ip}")
        self._runtime = RemoteRuntime(host=public_ip, port=self._port)
        t0 = time.time()
        await self._wait_until_alive(timeout=timeout)
        self.logger.info(f"Runtime started in {time.time() - t0:.2f}s")

    async def stop(self):
        if self._runtime is not None:
            await self._runtime.close()
            self._runtime = None
        if self._task_arn is not None:
            ecs_client = boto3.client('ecs')
            ecs_client.stop_task(task=self._task_arn, cluster=self._cluster_arn)
        self._task_arn = None
        self._container_name = None

    @property
    def runtime(self) -> RemoteRuntime:
        if self._runtime is None:
            msg = "Runtime not started"
            raise RuntimeError(msg)
        return self._runtime
