"""Endpoint validation and DNS-pinned, bounded HTTP transport."""
from __future__ import annotations

import asyncio
import ipaddress
import json
import re
import socket
from urllib.parse import parse_qsl, urlsplit

import httpx

MAX_RESPONSE = 2 * 1024 * 1024
MAX_REQUEST = 64 * 1024
TIMEOUT = 20


class ConnectionError(Exception):
    def __init__(self, code: str, message: str, status: int = 422):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status


def validate_url(url: str, allow_private: bool) -> str:
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError:
        raise ConnectionError("invalid_url", "La URL no es válida.") from None
    if (len(url) > 2048 or parts.scheme not in {"https", "http"} or not parts.hostname
            or parts.username is not None or parts.password is not None or parts.fragment
            or any(c in url for c in "\r\n\\")):
        raise ConnectionError("invalid_url", "Usa una URL HTTP válida sin credenciales ni fragmentos.")
    if any(re.search(r"key|token|secret|password|credential|signature|auth", key, re.I)
           for key, _ in parse_qsl(parts.query)):
        raise ConnectionError("url_credential", "Introduce las credenciales en el campo seguro.")
    if parts.scheme == "http" and not allow_private:
        raise ConnectionError("https_required", "Las conexiones remotas requieren HTTPS.")
    if port == 0:
        raise ConnectionError("invalid_url", "Puerto no válido.")
    # Literal addresses can be rejected without making a network request.
    try:
        address = ipaddress.ip_address(parts.hostname)
    except ValueError:
        pass
    else:
        check_address(address, allow_private, parts.scheme)
    return str(httpx.URL(url))


def check_address(address, allow_private: bool, scheme: str):
    if getattr(address, "ipv4_mapped", None):
        address = address.ipv4_mapped
    if (address.is_link_local or address.is_multicast or address.is_unspecified or address.is_reserved
            or str(address) in {"168.63.129.16", "100.100.100.200"}):
        raise ConnectionError("destination_denied", "Este destino de red no está permitido.")
    if not address.is_global and not (allow_private and (address.is_private or address.is_loopback)):
        raise ConnectionError("private_destination", "Autoriza explícitamente la red privada para usar este destino.")
    if scheme == "http" and address.is_global:
        raise ConnectionError("https_required", "Las conexiones públicas requieren HTTPS.")


async def resolve_target(url: str, allow_private: bool) -> str:
    parts = urlsplit(validate_url(url, allow_private))
    try:
        answers = await asyncio.wait_for(asyncio.get_running_loop().getaddrinfo(
            parts.hostname, parts.port or (443 if parts.scheme == "https" else 80),
            type=socket.SOCK_STREAM), timeout=5)
    except (OSError, asyncio.TimeoutError):
        raise ConnectionError("dns_failed", "No se pudo resolver el servidor.", 502) from None
    if not answers:
        raise ConnectionError("dns_failed", "El servidor no tiene una dirección disponible.", 502)
    for answer in answers:
        check_address(ipaddress.ip_address(answer[4][0]), allow_private, parts.scheme)
    return answers[0][4][0]


class BoundedStream(httpx.AsyncByteStream):
    def __init__(self, source):
        self.source = source

    async def __aiter__(self):
        size = 0
        async for chunk in self.source:
            size += len(chunk)
            if size > MAX_RESPONSE:
                raise ConnectionError("response_too_large", "La respuesta supera el límite de 2 MiB.", 502)
            yield chunk

    async def aclose(self):
        await self.source.aclose()


class PinnedTransport(httpx.AsyncBaseTransport):
    """Resolve, validate and connect to the exact selected address on each request.

    Original Host and TLS SNI are retained; DNS cannot change the peer between
    validation and connect. Redirects and inherited proxies are disabled.
    """
    def __init__(self, url: str, allow_private: bool):
        self.url, self.allow_private = url, allow_private
        self.transport = httpx.AsyncHTTPTransport(retries=0, trust_env=False)

    async def handle_async_request(self, request):
        original = urlsplit(self.url)
        actual = urlsplit(str(request.url))
        if (actual.scheme, actual.hostname, actual.port or (443 if actual.scheme == "https" else 80), actual.path or "/") != (
                original.scheme, original.hostname, original.port or (443 if original.scheme == "https" else 80), original.path or "/"):
            raise ConnectionError("endpoint_changed", "La solicitud no coincide con el destino configurado.")
        target = await resolve_target(self.url, self.allow_private)
        headers = request.headers.copy()
        headers["Host"] = original.netloc
        headers["Accept-Encoding"] = "identity"
        pinned = httpx.Request(request.method, request.url.copy_with(host=target),
                               headers=headers, stream=request.stream,
                               extensions={**request.extensions, "sni_hostname": original.hostname})
        response = await self.transport.handle_async_request(pinned)
        if 300 <= response.status_code < 400:
            await response.aclose()
            raise ConnectionError("redirect_denied", "El servidor intentó redirigir la solicitud.", 502)
        if response.headers.get("content-encoding", "identity") not in {"identity", ""}:
            await response.aclose()
            raise ConnectionError("encoding_denied", "El servidor debe enviar una respuesta sin compresión.", 502)
        response.stream = BoundedStream(response.stream)
        return response

    async def aclose(self):
        await self.transport.aclose()


def client_for(connection, headers=None, **_kwargs):
    return httpx.AsyncClient(transport=PinnedTransport(connection["url"], connection["allow_private"]),
                             headers=headers, timeout=httpx.Timeout(TIMEOUT),
                             follow_redirects=False, trust_env=False)


def bounded_json(value):
    try:
        encoded = json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (ValueError, TypeError, RecursionError):
        raise ConnectionError("invalid_json", "Introduce un objeto JSON válido.") from None
    if len(encoded) > MAX_REQUEST:
        raise ConnectionError("request_too_large", "La solicitud supera el límite de 64 KiB.")
    return encoded
