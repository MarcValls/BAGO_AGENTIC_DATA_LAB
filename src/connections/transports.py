"""Fixed Docker stdio and MCP Streamable HTTP sessions, without host callbacks."""
from __future__ import annotations

import asyncio
import os
import shutil
import json
import subprocess
import re
from contextlib import asynccontextmanager
from datetime import timedelta

import anyio
from mcp import ClientSession
from mcp.shared.message import SessionMessage
from mcp.types import JSONRPCMessage
from mcp.client.streamable_http import streamable_http_client

from .security import ConnectionError, TIMEOUT, MAX_RESPONSE, client_for

MAX_TOOLS = 128


def docker_command(profile):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}", profile or ""):
        raise ConnectionError("invalid_docker_profile", "El identificador del perfil no es válido.")
    executable = shutil.which("docker")
    if not executable:
        raise ConnectionError("docker_unavailable", "No se ha encontrado Docker CLI.", 503)
    return executable, ["mcp", "gateway", "run", "--profile", profile, "--watch=false", "--log-calls=false"]


def docker_preflight(command, profile):
    """Never let the gateway silently fetch an absent server image."""
    try:
        result = subprocess.run([command, "mcp", "profile", "show", profile, "--format", "json"],
                                shell=False, capture_output=True, timeout=8, check=True)
        if len(result.stdout) > 512 * 1024:
            raise ValueError("profile too large")
        config = json.loads(result.stdout)
        servers = config.get("servers", [])
        if not isinstance(servers, list) or not servers or len(servers) > 32:
            raise ValueError("unsupported server list")
        for server in servers:
            snapshot = (server.get("snapshot") or {}).get("server") or {}
            image = server.get("image") or snapshot.get("image")
            if snapshot.get("remote") or not isinstance(image, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/:-]*@sha256:[a-f0-9]{64}", image):
                raise ConnectionError("docker_profile_unsupported", "El perfil debe contener servidores de imagen local; configura los remotos mediante MCP HTTP.")
            snapshot_image = snapshot.get("image")
            if snapshot_image and snapshot_image != image:
                raise ConnectionError("docker_profile_unsupported", "La imagen efectiva no coincide con el snapshot del perfil.")
            checked = subprocess.run([command, "image", "inspect", image], shell=False,
                                     capture_output=True, timeout=8)
            if checked.returncode:
                raise ConnectionError("docker_image_missing", "Falta una imagen del perfil. Instálala explícitamente en Docker antes de conectar.", 409)
    except ConnectionError:
        raise
    except (OSError, ValueError, subprocess.SubprocessError):
        raise ConnectionError("docker_preflight_failed", "No se pudo comprobar el perfil y sus imágenes locales.", 503) from None


@asynccontextmanager
async def bounded_stdio(command, args, env):
    """SDK session streams with a bounded wire frame before JSON parsing.

    This lower-level stdio wrapper avoids the SDK's unbounded line buffer.
    Only the fixed Docker command calls it in product code; stderr is discarded.
    """
    process = await asyncio.create_subprocess_exec(command, *args, stdin=asyncio.subprocess.PIPE,
                                                 stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
                                                 env=env, limit=MAX_RESPONSE,
                                                 creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    incoming, reader = anyio.create_memory_object_stream(0)
    writer, outgoing = anyio.create_memory_object_stream(0)

    async def read_output():
        async with incoming:
            try:
                while line := await process.stdout.readline():
                    if len(line) > MAX_RESPONSE:
                        raise ValueError("frame too large")
                    await incoming.send(SessionMessage(JSONRPCMessage.model_validate_json(line)))
            except Exception:
                await incoming.send(ConnectionError("stdio_invalid_response", "Docker envió una respuesta inválida o superior a 2 MiB.", 502))

    async def write_input():
        async with outgoing:
            async for message in outgoing:
                raw = message.message.model_dump_json(by_alias=True, exclude_none=True).encode("utf-8") + b"\n"
                if len(raw) > 80 * 1024:
                    await incoming.send(ConnectionError("request_too_large", "La solicitud MCP supera el límite permitido."))
                    return
                process.stdin.write(raw)
                await process.stdin.drain()

    tasks = [asyncio.create_task(read_output()), asyncio.create_task(write_input())]
    try:
        yield reader, writer
    finally:
        with anyio.CancelScope(shield=True):
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            await reader.aclose()
            await writer.aclose()
            process.stdin.close()
            try:
                await asyncio.wait_for(process.wait(), 2)
            except asyncio.TimeoutError:
                process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), 2)
                except asyncio.TimeoutError:
                    process.kill()
                    await process.wait()


@asynccontextmanager
async def session_for(connection, headers):
    if connection["kind"] == "docker_mcp":
        command, args = docker_command(connection["profile"])
        await asyncio.to_thread(docker_preflight, command, connection["profile"])
        # Only OS infrastructure, never provider credentials or arbitrary env.
        env = {key: os.environ[key] for key in ("SYSTEMROOT", "WINDIR", "USERPROFILE", "HOME", "LOCALAPPDATA", "APPDATA", "TEMP", "TMP", "PATH") if key in os.environ}
        async with bounded_stdio(command, args, env) as (read, write):
            async with ClientSession(read, write, read_timeout_seconds=timedelta(seconds=TIMEOUT)) as session:
                await session.initialize()
                yield session
    else:
        async with client_for(connection, headers=headers) as client:
            async with streamable_http_client(connection["url"], http_client=client) as (read, write, _):
                async with ClientSession(read, write, read_timeout_seconds=timedelta(seconds=TIMEOUT)) as session:
                    await session.initialize()
                    yield session


async def list_tools(session):
    tools, cursor = [], None
    for _ in range(8):
        result = await session.list_tools(cursor=cursor)
        tools.extend(result.tools)
        if len(tools) > MAX_TOOLS:
            raise ConnectionError("too_many_tools", "El servidor supera el límite de 128 herramientas.", 502)
        cursor = result.nextCursor
        if not cursor:
            return tools
    raise ConnectionError("too_many_pages", "El catálogo supera el límite de paginación.", 502)
