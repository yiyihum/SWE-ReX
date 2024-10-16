from swebridge.local import RemoteRuntime


def test_server_alive(remote_runtime: RemoteRuntime):
    assert remote_runtime.is_alive()
