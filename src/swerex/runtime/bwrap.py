import logging
from pathlib import Path
import time
from typing import Any, List

import pexpect

from swerex.exceptions import (
    SessionExistsError,
    SessionNotInitializedError,
    NonZeroExitCodeError,
    CommandTimeoutError,
    BashIncorrectSyntaxError,
)
from swerex.runtime.abstract import (
    CreateSessionRequest,
    CreateSessionResponse,
    CloseSessionResponse,
    CreateBwrapBashSessionRequest,
    CreateBwrapBashSessionResponse,
    CloseBwrapBashSessionResponse,
    CreateBashSessionRequest,
    ReadFileRequest,
    ReadFileResponse,
    WriteFileRequest,
    WriteFileResponse,
    UploadRequest,
    UploadResponse,
    BashAction,
    BashInterruptAction,
    BashObservation
)
from swerex.runtime.local import LocalRuntime, BashSession, _strip_control_chars, _split_bash_command


class BwrapBashSession(BashSession):
    """A bash session that runs inside a bubblewrap sandbox."""

    def __init__(self, request: CreateBwrapBashSessionRequest, *, logger: logging.Logger | None = None):
        # Initialize parent with a converted request
        bash_request = CreateBashSessionRequest(
            startup_source=request.startup_source,
            session=request.session,
            session_type="bash",  # This is for the parent class
            startup_timeout=request.startup_timeout,
        )
        super().__init__(bash_request, logger=logger)
        self.bwrap_request = request

    def _build_bwrap_command(self) -> list[str]:
        """Build the bwrap command with all the necessary options."""
        cmd = ["bwrap"]
        cmd.extend(["--tmpfs", "/root", "--setenv", "HOME", "/root"])

        # Basic setup - always bind /usr, /bin, /lib, /lib64 for basic functionality
        basic_binds = [
            ("--ro-bind", "/usr", "/usr"),
            ("--ro-bind", "/bin", "/bin"),
            ("--ro-bind", "/lib", "/lib"),
            # Entries originally like ("/path", "/path") are interpreted as "--ro-bind" for system directories
            ("--ro-bind", "/bin/bash", "/bin/bash"),  # Original: ("/bin/bash", "/bin/bash")
            ("--ro-bind", "/bin", "/bin"),  # Original: ("/bin", "/bin")
            ("--ro-bind", "/usr/bin", "/usr/bin"),  # Original: ("/usr/bin", "/usr/bin")
            ("--ro-bind", "/usr/local/bin", "/usr/local/bin"),  # Original: ("/usr/local/bin", "/usr/local/bin")
            ("--ro-bind", "/lib", "/lib"),  # Original: ("/lib", "/lib")
            ("--ro-bind", "/usr/lib", "/usr/lib"),  # Original: ("/usr/lib", "/usr/lib")
            ("--ro-bind", "/lib64", "/lib64"),  # Original: ("/lib64", "/lib64")
            ("--ro-bind", "/sbin", "/sbin"),  # Original: ("/sbin", "/sbin")
            # Conditional entries
            ("--ro-bind", "/lib64", "/lib64") if Path("/lib64").exists() else None,
            ("--ro-bind", "/etc/alternatives", "/etc/alternatives") if Path("/etc/alternatives").exists() else None,
        ]

        # Add read-only bind mounts
        if self.bwrap_request.ro_bind_paths:
            for host_path, container_path in self.bwrap_request.ro_bind_paths:
                cmd.extend(["--ro-bind", host_path, container_path])

        for bind in basic_binds:
            if bind:
                cmd.extend(bind)

        # Process namespace options
        if self.bwrap_request.unshare_net:
            cmd.append("--unshare-net")
        if self.bwrap_request.unshare_pid:
            cmd.append("--unshare-pid")

        # Add custom bind mounts
        if self.bwrap_request.bind_paths:
            for host_path, container_path in self.bwrap_request.bind_paths:
                cmd.extend(["--bind", host_path, container_path])

        # Add tmpfs mounts
        if self.bwrap_request.tmpfs_paths:
            for tmpfs_path in self.bwrap_request.tmpfs_paths:
                cmd.extend(["--tmpfs", tmpfs_path])

        # Add /dev bindings for basic functionality
        cmd.extend(
            [
                "--dev",
                "/dev",
            ]
        )

        # Finally, add the bash command
        cmd.extend(["/usr/bin/env", "bash", "--norc", "--noprofile"])

        return cmd

    async def start(self) -> CreateBwrapBashSessionResponse:
        """Spawn the session inside a bwrap sandbox."""
        bwrap_cmd = self._build_bwrap_command()

        self._shell = pexpect.spawn(
            bwrap_cmd[0],
            args=bwrap_cmd[1:],
            encoding="utf-8",
            codec_errors="backslashreplace",
            echo=False,
            env={"PS1": self._ps1, "PS2": "", "PS0": ""},  # type: ignore
        )

        time.sleep(0.3)

        cmds = []
        if self.request.startup_source:
            cmds += [f"source {path}" for path in self.request.startup_source] + ["sleep 0.3"]
        
        cmds += self._get_reset_commands()
        cmd = " ; ".join(cmds)

        self.shell.sendline(cmd)
        self.shell.expect(self._ps1, timeout=self.request.startup_timeout)
        output = _strip_control_chars(self.shell.before)  # type: ignore

        return CreateBwrapBashSessionResponse(output=output)

    async def close(self) -> CloseSessionResponse:
        """Close the bwrap session."""
        if self._shell is None:
            return CloseBwrapBashSessionResponse()
        self.shell.close()
        self._shell = None
        return CloseBwrapBashSessionResponse()

class BwrapRuntime(LocalRuntime):
    def __init__(self, *, logger: logging.Logger | None = None, **kwargs: Any):
        super().__init__(logger=logger, **kwargs)
        self._path_map = list()

    def _resolve_path(self, container_path: str) -> str:
        """Resolves a path from inside the bwrap container to the host path."""
        container_path_obj = Path(container_path)

        for host_path, c_path in self._path_map:
            c_path_obj = Path(c_path)
            if container_path_obj == c_path_obj or c_path_obj in container_path_obj.parents:
                relative_path = container_path_obj.relative_to(c_path_obj)
                return str(Path(host_path) / relative_path)

        return container_path

    async def read_file(self, request: ReadFileRequest) -> ReadFileResponse:
        """Reads a file from within the bwrap sandbox."""
        request.path = self._resolve_path(request.path)
        return await super().read_file(request)

    async def write_file(self, request: WriteFileRequest) -> WriteFileResponse:
        """Writes a file to a path inside the bwrap sandbox."""
        request.path = self._resolve_path(request.path)
        return await super().write_file(request)

    async def upload(self, request: UploadRequest) -> UploadResponse:
        """Uploads a file to a path inside the bwrap sandbox."""
        request.target_path = self._resolve_path(request.target_path)
        return await super().upload(request)

    async def create_session(self, request: CreateSessionRequest) -> CreateSessionResponse:
        """Creates a new session."""
        if request.session in self.sessions:
            msg = f"session {request.session} already exists"
            raise SessionExistsError(msg)
        if isinstance(request, CreateBwrapBashSessionRequest):
            session = BwrapBashSession(request, logger=self.logger)
            self.sessions[request.session] = session
            # Update path map
            if hasattr(request, "bind_paths") and request.bind_paths:
                for host_path, container_path in request.bind_paths:
                    if host_path != container_path:
                        self._path_map.append((host_path, container_path))
            if hasattr(request, "ro_bind_paths") and request.ro_bind_paths:
                for host_path, container_path in request.ro_bind_paths:
                    if host_path != container_path:
                        self._path_map.append((host_path, container_path))
            self._path_map = list(set(self._path_map))  # Remove duplicates
            self._path_map = sorted(self._path_map, key=lambda x: len(x[1]), reverse=True)

            return await session.start()
        else:
            raise ValueError(
                f"Unsupported session type: {request.session_type}. "
                "Use CreateBwrapBashSessionRequest for bwrap bash sessions."
            )

__all__ = ["BwrapRuntime", "BwrapBashSession"]