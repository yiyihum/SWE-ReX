import boto3
import json
import hashlib
from urllib.parse import quote


def get_fargate_family_name(image_name: str, port: int) -> str:
    image_name_sanitized = "".join(c for c in image_name if c.isalnum() or c in "-_")
    image_name_sanitized += f"-p{port}"
    if len(image_name_sanitized) <= 255:
        return image_name_sanitized
    # return a hash of the image name
    return hashlib.sha256(image_name_sanitized.encode()).hexdigest()[:255]


def get_execution_role_arn(role_name: str) -> str:
    iam_client = boto3.client('iam')
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
    execution_role_arn: str,
    
) -> str:
    ecs_client = boto3.client('ecs')
    family_name = get_fargate_family_name(image_name, port)
    # if family exists just return the task definition
    try:
        response = ecs_client.describe_task_definition(taskDefinition=family_name)
        return response['taskDefinition']
    except ecs_client.exceptions.ClientException:
        pass    
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
                    "echo 'hello world'"  # override command with run_task
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
        'requiresCompatibilities': ['FARGATE', 'EC2'],
    }
    response = ecs_client.register_task_definition(**task_definition)
    return response['taskDefinition']


def get_cluster_arn(cluster_name: str) -> str:
    ecs_client = boto3.client('ecs')
    response = ecs_client.create_cluster(clusterName=cluster_name)
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


def get_security_group(vpc_id: str, port: int, security_group_name: str) -> str:
    ec2_client = boto3.client('ec2')
    
    #if it exists, just return the id
    try:
        security_group = ec2_client.describe_security_groups(GroupNames=[security_group_name])
        return security_group['SecurityGroups'][0]['GroupId']
    except ec2_client.exceptions.ClientError:
        pass
    
    security_group = ec2_client.create_security_group(
        GroupName=security_group_name,
        Description='Security group swe rex',
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


def run_fargate_task(
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


def get_cloudwatch_log_url(task_arn: str, task_definition: dict, container_name: str, region: str = 'us-east-2') -> str:
    """
    Get the CloudWatch log URL for a running task.
    
    Args:
        task_arn (str): The ARN of the running task.
        task_definition (dict): The task definition for the running task.
        container_name (str): The name of the container in the task definition.
        
    Returns:
        str: The CloudWatch log URL.
    """
    container_def = task_definition['containerDefinitions'][0]
    log_config = container_def['logConfiguration']['options']
    log_group = log_config['awslogs-group']
    task_id = task_arn.split('/')[-1]
    log_stream = f"{log_config['awslogs-stream-prefix']}/{container_name}/{task_id}"
    
    # Use %25 instead of $25 for encoding
    encoded_log_group = quote(log_group, safe='')
    encoded_log_stream = quote(log_stream, safe='')
    
    return (
        f"https://{region}.console.aws.amazon.com/cloudwatch/home"
        f"?region={region}"
        f"#logsV2:log-groups/log-group/{encoded_log_group}"
        f"/log-events/{encoded_log_stream}"
    )
