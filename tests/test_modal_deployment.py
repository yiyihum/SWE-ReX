import pytest
from pathlib import Path

from swerex.deployment.modal import ModalDeployment


async def test_modal_deployment():
    dockerfile = Path(__file__).parent / "swe_rex_test.Dockerfile"
    d = ModalDeployment(dockerfile=dockerfile, container_timeout=60)
    with pytest.raises(RuntimeError):
        await d.is_alive()
    await d.start()
    assert await d.is_alive()
    await d.stop()
