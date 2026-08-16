from typing import Tuple, Protocol, List
import asyncio
import os
import platform
import shutil
from abc import ABC, abstractmethod


class CommandExecutor(Protocol):
    async def execute(self, cmd: str | List[str]) -> Tuple[int, str, str]:
        pass


class WindowsExecutor:
    async def execute(self, cmd: str) -> Tuple[int, str, str]:
        process = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            shell=True
        )
        stdout, stderr = await process.communicate()
        return process.returncode, stdout.decode(), stderr.decode()


class UnixExecutor:
    async def execute(self, cmd: List[str]) -> Tuple[int, str, str]:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        return process.returncode, stdout.decode(), stderr.decode()


class DockerExecutorBase(ABC):
    def __init__(self):
        self.docker_cmd = self._initialize_docker_cmd()
        self.executor = WindowsExecutor() if platform.system() == 'Windows' else UnixExecutor()

    @abstractmethod
    async def run_command(self, command: str, *args) -> Tuple[int, str, str]:
        pass

    def _initialize_docker_cmd(self) -> str:
        if platform.system() == 'Windows':
            docker_dir = r"C:\Program Files\Docker\Docker\resources\bin"
            docker_paths = [
                os.path.join(docker_dir, "docker-compose.exe"),
                os.path.join(docker_dir, "docker.exe")
            ]
            for path in docker_paths:
                if os.path.exists(path):
                    return path

        docker_cmd = shutil.which('docker')
        if not docker_cmd:
            raise RuntimeError("Docker executable not found")
        return docker_cmd


class DockerComposeExecutor(DockerExecutorBase):
    def __init__(self, compose_file: str, project_name: str, docker_host: str | None = None):
        super().__init__()
        self.compose_file = os.path.abspath(compose_file)
        self.project_name = project_name
        if docker_host and not docker_host.startswith("ssh://"):
            raise ValueError(
                f"docker_host must use the ssh:// scheme (got: {docker_host!r}). "
                "TCP+TLS targets are not supported here since that would require "
                "passing certificate/key material as tool arguments."
            )
        self.docker_host = docker_host

    async def run_command(self, command: str, *args) -> Tuple[int, str, str]:
        if platform.system() == 'Windows':
            cmd = self._build_windows_command(command, *args)
        else:
            cmd = self._build_unix_command(command, *args)
        return await self.executor.execute(cmd)

    def _build_windows_command(self, command: str, *args) -> str:
        compose_file = self.compose_file.replace('\\', '/')
        host_flag = f'-H "{self.docker_host}" ' if self.docker_host else ''
        return (f'cd "{os.path.dirname(compose_file)}" && docker {host_flag}compose '
                f'-f "{os.path.basename(compose_file)}" '
                f'-p {self.project_name} {command} {" ".join(args)}')

    def _build_unix_command(self, command: str, *args) -> list[str]:
        cmd = [self.docker_cmd]
        if self.docker_host:
            cmd += ["-H", self.docker_host]
        cmd += [
            "compose",
            "-f", self.compose_file,
            "-p", self.project_name,
            command,
            *args
        ]
        return cmd

    async def down(self) -> Tuple[int, str, str]:
        return await self.run_command("down", "--volumes")

    async def pull(self) -> Tuple[int, str, str]:
        return await self.run_command("pull")

    async def up(self) -> Tuple[int, str, str]:
        return await self.run_command("up", "-d")

    async def ps(self) -> Tuple[int, str, str]:
        return await self.run_command("ps")
