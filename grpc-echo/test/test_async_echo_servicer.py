from collections.abc import AsyncIterator
from concurrent import futures
from contextlib import asynccontextmanager
from secrets import token_hex

import grpc
import grpc.aio
import pytest

from grpc_echo import AsyncEchoServicer, EchoServiceStub, proto


@asynccontextmanager
async def async_echo_service():
    address = "unix:echo_service.sock"

    # configure grpc server
    credentials = grpc.local_server_credentials(grpc.LocalConnectionType.UDS)
    server = grpc.aio.server(futures.ThreadPoolExecutor())
    AsyncEchoServicer.add_to_server(server)
    server.add_secure_port(address, credentials)

    # launch server in background
    await server.start()

    # setup client channel and stub
    credentials = grpc.local_channel_credentials(grpc.LocalConnectionType.UDS)
    channel = grpc.aio.secure_channel(address, credentials)
    stub = EchoServiceStub(channel)

    # yield stub to caller
    yield stub

    # no need to wait for running rpc's
    await server.stop(grace=None)


@pytest.mark.asyncio
async def test_echo_unary_unary_input():
    """Service should respons with input string as output."""
    async with async_echo_service() as service:
        text = token_hex(16)

        response: proto.EchoOutput = await service.echo(proto.EchoInput(input=text))
        assert response.output == text


@pytest.mark.asyncio
async def test_echo_unary_stream_input():
    """
    Service should split input string into characters and respond with a message
    for each.
    """
    async with async_echo_service() as service:
        text = token_hex(16)
        characters = list(text)

        request = proto.EchoInput(input=text)
        response_iterator: AsyncIterator[proto.EchoOutput] = service.echo_chars(request)
        output = [response.output async for response in response_iterator]

        assert output == characters


@pytest.mark.asyncio
async def test_echo_stream_unary_input():
    """Service should respond by concatenating every input string."""
    async with async_echo_service() as service:
        texts = [token_hex(4) for _ in range(4)]
        concatenated = "".join(texts)

        async def input_producer():
            for t in texts:
                yield proto.EchoInput(input=t)

        response: proto.EchoOutput = await service.echo_concat(input_producer())

        assert response.output == concatenated


@pytest.mark.asyncio
async def test_echo_stream_stream_input():
    """
    Service should respond with every input string as seperate output messages.
    """
    async with async_echo_service() as service:
        texts = [token_hex(4) for _ in range(4)]

        async def input_producer():
            for t in texts:
                yield proto.EchoInput(input=t)

        response_iterator: AsyncIterator[proto.EchoOutput] = service.echo_stream(
            input_producer(),
        )
        outputs = [response.output async for response in response_iterator]

        assert outputs == texts
