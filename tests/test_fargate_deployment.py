import os
import pytest

from swerex.deployment.fargate import FargateDeployment


@pytest.mark.skipif(os.getenv("GITHUB_ACTIONS") == "true", reason="Skipping modal tests in github actions")
async def test_docker_deployment():
    d = FargateDeployment(
        image_name="039984708918.dkr.ecr.us-east-2.amazonaws.com/swe-rex-test",
        port=8880,
        container_timeout=60 * 15,
    )
    with pytest.raises(RuntimeError):
        await d.is_alive()
    await d.start()
    assert await d.is_alive()
    await d.stop()
