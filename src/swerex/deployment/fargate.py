import hashlib
import time
import boto3
import uuid
import json

from swerex import REMOTE_EXECUTABLE_NAME
from swerex.deployment.abstract import AbstractDeployment
from swerex.runtime.abstract import IsAliveResponse
from swerex.runtime.remote import RemoteRuntime
from swerex.utils.log import get_logger
from swerex.utils.wait import _wait_until_alive

def get_family_name(image_name: str, port: int) -> str:
    image_name_sanitized = "".join(c for c in image_name if c.isalnum() or c in "-_")
    image_name_sanitized += f"-p{port}"
    if len(image_name_sanitized) <= 255:
        return image_name_sanitized
    # return a hash of the image name
    return hashlib.sha256(image_name_sanitized.encode()).hexdigest()[:255]


def get_execution_role_arn() -> str:
    iam_client = boto3.client('iam')
    role_name = f"swe-rex-execution-role"
    
    #if it exists, return the arn
    try:
        role = iam_client.get_role(RoleName=role_name)
        return role['Role']['Arn']
    except iam_client.exceptions.NoSuchEntityException:
        pass
    
    trust_relationship = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {
                    "Service": "ecs-tasks.amazonaws.com"
                },
                "Action": "sts:AssumeRole"
            }
        ]
    }
    role = iam_client.create_role(
        RoleName=role_name,
        AssumeRolePolicyDocument=json.dumps(trust_relationship)
    )
    iam_client.attach_role_policy(
        RoleName=role_name,
        PolicyArn='arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy'
    )
    iam_client.attach_role_policy(
        RoleName=role_name,
        PolicyArn='arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly'
    )
    cloudwatch_logs_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": [
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                    "logs:DescribeLogStreams"
                ],
                "Resource": [
                    f"arn:aws:logs:*:*:log-group:/ecs/swe-rex-deployment:*",
                    f"arn:aws:logs:*:*:log-group:/ecs/swe-rex-deployment"
                ]
            }
        ]
    }
    iam_client.put_role_policy(
        RoleName=role_name,
        PolicyName="CloudWatchLogsPolicy",
        PolicyDocument=json.dumps(cloudwatch_logs_policy)
    )
    waiter = iam_client.get_waiter('role_exists')
    waiter.wait(RoleName=role_name)
    return role['Role']['Arn']


def get_task_definition(
    image_name: str,
    port: int,
) -> str:
    ecs_client = boto3.client('ecs')
    family_name = get_family_name(image_name, port)
    # if family exists just return the task definition
    try:
        response = ecs_client.describe_task_definition(taskDefinition=family_name)
        return response['taskDefinition']
    except ecs_client.exceptions.ClientException:
        pass
    
    execution_role_arn = get_execution_role_arn()
    
    task_definition = {
        'family': family_name,
        'executionRoleArn': execution_role_arn,
        'networkMode': 'awsvpc',
        'memory': '2048',
        'cpu': '1 vCPU',
        'containerDefinitions': [
            {
                'name': family_name,
                'image': image_name,
                'portMappings': [
                    {
                        'containerPort': port,
                        'hostPort': port,
                        'protocol': 'tcp'
                    }
                ],
                'essential': True,
                'entryPoint': ['/bin/sh', '-c'],
                'command': [
                    f"timeout 1800s {REMOTE_EXECUTABLE_NAME} --port {port} 2>&1"
                ],
                'logConfiguration': {
                    'logDriver': 'awslogs',
                    'options': {
                        'awslogs-group': f'/ecs/swe-rex-deployment',
                        'awslogs-region': 'us-east-2',
                        'awslogs-stream-prefix': 'ecs',
                        'awslogs-create-group': 'true',
                    }
                },
            },
        ],
        'requiresCompatibilities': ['FARGATE']
    }
    response = ecs_client.register_task_definition(**task_definition)
    return response['taskDefinition']


def get_cluster_arn(cluster_name: str) -> str:
    # create if it doesn't exist
    ecs_client = boto3.client('ecs')
    response = ecs_client.create_cluster(clusterName="swe-rex-cluster")
    return response['cluster']['clusterArn']


def get_default_vpc_and_subnet() -> tuple[str, str]:
    ec2_client = boto3.client('ec2')
    vpcs = ec2_client.describe_vpcs(Filters=[{'Name': 'isDefault', 'Values': ['true']}])
    if not vpcs['Vpcs']:
        raise Exception("No default VPC found")
    vpc_id = vpcs['Vpcs'][0]['VpcId']
    subnets = ec2_client.describe_subnets(Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}])
    if not subnets['Subnets']:
        raise Exception("No subnets found in the default VPC")
    subnet_id = subnets['Subnets'][0]['SubnetId']
    return vpc_id, subnet_id


def get_security_group(vpc_id: str, port: int) -> str:
    ec2_client = boto3.client('ec2')
    
    #if it exists, just return the id
    try:
        security_group = ec2_client.describe_security_groups(GroupNames=['swe-rex-deployment-sg'])
        return security_group['SecurityGroups'][0]['GroupId']
    except ec2_client.exceptions.ClientError:
        pass
    
    security_group = ec2_client.create_security_group(
        GroupName='swe-rex-deployment-sg',
        Description='Security group for swe-rex-deployment',
        VpcId=vpc_id
    )
    security_group_id = security_group['GroupId']

    # Add an inbound rule to allow traffic on the port
    ec2_client.authorize_security_group_ingress(
        GroupId=security_group_id,
        IpPermissions=[
            {
                'IpProtocol': 'tcp',
                'FromPort': port,
                'ToPort': port,
                'IpRanges': [{'CidrIp': '0.0.0.0/0'}]
            }
        ]
    )
    return security_group_id


def run_task(
    command: str,
    name: str,
    task_definition_arn: str,
    subnet_id: str,
    security_group_id: str,
    cluster_arn: str,
    vcpus: int = 1,
    memory: int = 2048,
    ephemeral_storage: int = 21,
    **fargate_args,
) -> str:
    run_task_args = {
        'taskDefinition': task_definition_arn,
        'launchType': 'FARGATE',
        'cluster': cluster_arn,
        'networkConfiguration': {
            'awsvpcConfiguration': {
                'subnets': [subnet_id],
                'securityGroups': [security_group_id],
                'assignPublicIp': 'ENABLED'
            }
        }
    }
    overrides = {
        'containerOverrides': [
            {
                'name': name,
                'command': [
                    command,
                ],
            },
        ],
        'cpu': f'{vcpus}vCPU',
        'memory': str(memory),
        'ephemeralStorage': {
            'sizeInGiB': ephemeral_storage,
        },
    }
    if fargate_args:
        overrides.update(fargate_args)
        
    if overrides:
        run_task_args['overrides'] = overrides

    ecs_client = boto3.client('ecs')
    response = ecs_client.run_task(**run_task_args)
    return response['tasks'][0]['taskArn']
    

def get_public_ip(task_arn: str, cluster_arn: str) -> str:
    ecs_client = boto3.client('ecs')
    task_details = ecs_client.describe_tasks(cluster=cluster_arn, tasks=[task_arn])
    eni_id = task_details['tasks'][0]['attachments'][0]['details'][1]['value']
    ec2_client = boto3.client('ec2')
    eni_details = ec2_client.describe_network_interfaces(NetworkInterfaceIds=[eni_id])
    return eni_details['NetworkInterfaces'][0]['Association']['PublicIp']


class FargateDeployment(AbstractDeployment):
    def __init__(
        self,
        image_name: str,
        port: int = 8880,
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
        self._cluster_name = "swe-rex-cluster"
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
        self._task_definition = get_task_definition(self._image_name, self._port)
        self._task_definition_arn = self._task_definition['taskDefinitionArn']
        self._vpc_id, self._subnet_id = get_default_vpc_and_subnet()

    def _get_container_name(self) -> str:
        return get_family_name(self._image_name, self._port)
    
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
        self._security_group_id = get_security_group(self._vpc_id, self._port)
        self._container_name = self._get_container_name()
        self.logger.info(f"Starting runtime with container name {self._container_name}")
        self._task_arn = run_task(
            command=f"timeout {self._container_timeout}s {REMOTE_EXECUTABLE_NAME} --port {self._port} 2>&1",
            name=self._container_name,
            task_definition_arn=self._task_definition_arn,
            subnet_id=self._subnet_id,
            security_group_id=self._security_group_id,
            cluster_arn=self._cluster_arn,
            **self._fargate_args,
        )
        # wait until the container is running
        ecs_client = boto3.client('ecs')
        waiter = ecs_client.get_waiter('tasks_running')
        # try:
            # TODO: get the cloudwatch logs url
            # # Get the CloudWatch log stream for the task
            # logs_client = boto3.client('logs')
            # task_details = ecs_client.describe_tasks(cluster=self._cluster_arn, tasks=[self._task_arn])
            # container = task_details['tasks'][0]['containers'][0]
            # log_stream_name = container.get('name', '')
            # log_group = f"/ecs/{self._container_name}"

            # # aws_region = boto3.session.Session().region_name
            # cloudwatch_url = (
            #     f"https://us-east-2.console.aws.amazon.com/cloudwatch/home"
            #     f"?region=us-east-2#logsV2:log-groups/log-group/$252Fecs$252Fswe-rex-deployment"
            #     f"/log-events/ecs$252F/{log_stream_name}"
            # )
            # self.logger.info(f"CloudWatch Logs URL: {cloudwatch_url}")
        # except Exception as e:
            # self.logger.warning(f"Failed to get CloudWatch Logs URL: {str(e)}")
                
        waiter.wait(cluster=self._cluster_arn, tasks=[self._task_arn])
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
