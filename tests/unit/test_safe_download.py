import asyncio
import ssl
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

import httpcore2
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from mealie_mcp_server.support.safe_download import (
    DownloadResponse,
    PinnedDownloadTransport,
    download_bounded,
    is_private_address,
)

PUBLIC = ["93.184.216.34"]


class FakeTransport:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []
        self.closed = 0

    @asynccontextmanager
    async def fetch(self, url, *, validated_addresses, deadline):
        self.calls.append((url, validated_addresses, deadline))
        status, headers, chunks = next(self.responses)

        async def body():
            for chunk in chunks:
                if isinstance(chunk, asyncio.Event):
                    await chunk.wait()
                else:
                    yield chunk

        stream = body()
        try:
            yield DownloadResponse(status, headers, stream)
        finally:
            await stream.aclose()
            self.closed += 1


async def resolve(host):
    return PUBLIC


@pytest.mark.parametrize(
    "address",
    [
        "10.1.1.1",
        "192.0.0.1",
        "192.0.2.1",
        "198.51.100.1",
        "203.0.113.1",
        "192.88.99.1",
        "192.168.0.1",
        "172.16.0.1",
        "169.254.1.1",
        "100.64.1.1",
        "127.0.0.1",
        "0.1.2.3",
        "224.0.0.1",
        "::1",
        "fd00::1",
        "fe80::1",
        "fec0::1",
        "::ffff:127.0.0.1",
        "::ffff:7f00:1",
        "64:ff9b:1::1",
        "100::1",
        "2001:db8::1",
        "ff02::1",
        "2002:7f00:1::1",
        "2001::1",
        "3fff::1",
        "",
        "files.test",
        "999.1.1.1",
    ],
)
def test_private_and_special_use_addresses_refused(address):
    assert is_private_address(address)


@pytest.mark.parametrize(
    "address", ["93.184.216.34", "192.0.1.1", "2606:2800:220:1::1", "2a00:1450:4001::1"]
)
def test_original_public_address_policy(address):
    assert not is_private_address(address)


@pytest.mark.parametrize("answers", [[], ["10.0.0.1"], ["93.184.216.34", "10.0.0.1"]])
async def test_empty_private_and_mixed_dns_answers_never_connect(answers):
    async def resolver(host):
        return answers

    transport = FakeTransport([])
    with pytest.raises(ValueError, match="resolved|private"):
        await download_bounded("https://files.test/x", 1024, resolve=resolver, transport=transport)
    assert transport.calls == []


@pytest.mark.parametrize(
    "url",
    [
        "not a url",
        "file:///etc/passwd",
        "https://user:secret@files.test/a",
        "https://:secret@files.test/a",
    ],
)
async def test_bad_url_rejected_before_resolution(url):
    async def resolver(host):
        pytest.fail("Should not resolve")

    with pytest.raises(ValueError, match="download_url"):
        await download_bounded(url, 1024, resolve=resolver, transport=FakeTransport([]))


async def test_each_redirect_resolves_and_pins_once_and_closes_previous_body():
    answers = iter([["2606:2800:220:1::1", "93.184.216.34"], ["93.184.216.35"]])
    hosts = []

    async def resolver(host):
        hosts.append(host)
        return next(answers)

    transport = FakeTransport([(302, {"location": "https://other.test/b"}, []), (200, {}, [b"hi"])])
    assert (
        await download_bounded("https://files.test/a", 10, resolve=resolver, transport=transport)
        == b"hi"
    )
    assert hosts == ["files.test", "other.test"]
    assert [item[1] for item in transport.calls] == [
        ("2606:2800:220:1::1", "93.184.216.34"),
        ("93.184.216.35",),
    ]
    assert transport.closed == 2
    assert transport.calls[0][2] == transport.calls[1][2]


async def test_three_redirect_limit_and_private_redirect_refusal():
    transport = FakeTransport([(302, {"location": "/loop"}, [])] * 4)
    with pytest.raises(ValueError, match="too many redirects"):
        await download_bounded("https://files.test/a", 10, resolve=resolve, transport=transport)
    assert len(transport.calls) == transport.closed == 4
    transport = FakeTransport([(302, {"location": "http://169.254.169.254/x"}, [])])
    with pytest.raises(ValueError, match="private"):
        await download_bounded("https://files.test/a", 10, resolve=resolve, transport=transport)
    assert len(transport.calls) == transport.closed == 1


@pytest.mark.parametrize(
    ("headers", "chunks"), [({"content-length": "11"}, [b"x"]), ({}, [b"12345", b"678901"])]
)
async def test_declared_and_streamed_size_limits_close_response(headers, chunks):
    transport = FakeTransport([(200, headers, chunks)])
    with pytest.raises(ValueError, match="exceeds"):
        await download_bounded("https://files.test/a", 10, resolve=resolve, transport=transport)
    assert transport.closed == 1


@pytest.mark.parametrize("phase", ["dns", "body"])
async def test_total_timeout_includes_dns_and_body(phase):
    async def resolver(host):
        if phase == "dns":
            await asyncio.Event().wait()
        return PUBLIC

    transport = FakeTransport([(200, {}, [b"a", asyncio.Event()])])
    with pytest.raises(ValueError, match="Download timed out"):
        await download_bounded(
            "https://files.test/a", 10, timeout_s=0.02, resolve=resolver, transport=transport
        )
    assert transport.closed == (0 if phase == "dns" else 1)


async def test_real_socket_uses_pinned_address_and_preserves_host_and_fallback():
    hosts = []

    async def serve(reader, writer):
        try:
            headers = await reader.readuntil(b"\r\n\r\n")
            hosts.append(headers)
            writer.write(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\nhi")
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()

    server = await asyncio.start_server(serve, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    try:
        transport = PinnedDownloadTransport(private_checker=lambda address: False)
        async with transport.fetch(
            f"http://pinned.invalid:{port}/x",
            validated_addresses=("::1", "127.0.0.1"),
            deadline=asyncio.get_running_loop().time() + 2,
        ) as response:
            assert response.status == 200
            assert b"".join([chunk async for chunk in response.body]) == b"hi"
        assert f"Host: pinned.invalid:{port}".lower().encode() in hosts[0].lower()
    finally:
        server.close()
        await server.wait_closed()


async def test_default_peer_guard_refuses_before_sending_http_bytes():
    received = []
    done = asyncio.Event()

    async def serve(reader, writer):
        try:
            received.append(await reader.read(1024))
        finally:
            writer.close()
            await writer.wait_closed()
            done.set()

    server = await asyncio.start_server(serve, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    try:
        with pytest.raises(ValueError, match="connected to a private"):
            async with PinnedDownloadTransport().fetch(
                f"http://pinned.invalid:{port}/",
                validated_addresses=("127.0.0.1",),
                deadline=asyncio.get_running_loop().time() + 2,
            ):
                pytest.fail("Must reject the peer before HTTP")
        await asyncio.wait_for(done.wait(), 2)
        assert received == [b""]
    finally:
        server.close()
        await server.wait_closed()


async def test_real_tls_keeps_original_sni_host_verifies_certificate_and_ignores_proxy(
    tmp_path, monkeypatch
):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "pinned.invalid")])
    now = datetime.now(UTC)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=1))
        .add_extension(
            x509.SubjectAlternativeName([x509.DNSName("pinned.invalid")]), critical=False
        )
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )
    cert_path, key_path = tmp_path / "cert.pem", tmp_path / "key.pem"
    cert_path.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    server_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    server_context.load_cert_chain(cert_path, key_path)
    sni, requests = [], []
    server_context.set_servername_callback(
        lambda ssl_socket, hostname, context: sni.append(hostname)
    )

    async def serve(reader, writer):
        try:
            requests.append(await reader.readuntil(b"\r\n\r\n"))
            writer.write(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\nhi")
            await writer.drain()
        except asyncio.IncompleteReadError, ConnectionError:
            pass
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except ConnectionError:
                pass

    server = await asyncio.start_server(serve, "127.0.0.1", 0, ssl=server_context)
    port = server.sockets[0].getsockname()[1]
    client_context = ssl.create_default_context(cafile=str(cert_path))
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:1")
    monkeypatch.setenv("ALL_PROXY", "http://127.0.0.1:1")
    url = f"https://pinned.invalid:{port}/x"
    try:
        transport = PinnedDownloadTransport(
            private_checker=lambda address: False, ssl_context=client_context
        )
        async with transport.fetch(
            url, validated_addresses=("127.0.0.1",), deadline=asyncio.get_running_loop().time() + 3
        ) as response:
            assert b"".join([chunk async for chunk in response.body]) == b"hi"
        assert sni == ["pinned.invalid"]
        assert f"Host: pinned.invalid:{port}".lower().encode() in requests[0].lower()
        assert b"authorization:" not in requests[0].lower()
        with pytest.raises(httpcore2.ConnectError):
            async with PinnedDownloadTransport(private_checker=lambda address: False).fetch(
                url,
                validated_addresses=("127.0.0.1",),
                deadline=asyncio.get_running_loop().time() + 3,
            ):
                pytest.fail("Untrusted certificate must be refused")
    finally:
        server.close()
        await server.wait_closed()


@pytest.mark.parametrize(
    ("status", "headers", "message"), [(302, {}, "without a Location"), (404, {}, "HTTP 404")]
)
async def test_failure_response_is_closed(status, headers, message):
    transport = FakeTransport([(status, headers, [])])
    with pytest.raises(ValueError, match=message):
        await download_bounded("https://files.test/x", 10, resolve=resolve, transport=transport)
    assert transport.closed == 1


async def test_cancellation_closes_response_without_changing_it_to_timeout():
    entered = asyncio.Event()

    @asynccontextmanager
    async def fetch(url, *, validated_addresses, deadline):
        async def body():
            entered.set()
            await asyncio.Event().wait()
            yield b""

        try:
            yield DownloadResponse(200, {}, body())
        finally:
            closed.append(True)

    closed = []
    transport = FakeTransport([])
    transport.fetch = fetch
    task = asyncio.create_task(
        download_bounded("https://files.test/a", 10, resolve=resolve, transport=transport)
    )
    await asyncio.wait_for(entered.wait(), 2)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert closed == [True]


async def test_real_transport_refuses_unsupported_status():
    async def serve(reader, writer):
        try:
            await reader.readuntil(b"\r\n\r\n")
            writer.write(b"HTTP/1.1 700 Weird\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()

    server = await asyncio.start_server(serve, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    try:
        transport = PinnedDownloadTransport(private_checker=lambda address: False)
        with pytest.raises(ValueError, match="unsupported HTTP status 700"):
            async with transport.fetch(
                f"http://pinned.invalid:{port}/",
                validated_addresses=("127.0.0.1",),
                deadline=asyncio.get_running_loop().time() + 2,
            ):
                pytest.fail("Must refuse unsupported status")
    finally:
        server.close()
        await server.wait_closed()
