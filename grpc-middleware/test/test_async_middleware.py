from collections.abc import Sequence
from concurrent import futures
from contextlib import asynccontextmanager

import grpc
import grpc.aio
import pytest
from grpc.aio import ClientInterceptor, ServerInterceptor
from grpc_echo import AsyncEchoServicer, EchoServiceStub, proto

from grpc_middleware import (
    AsyncMiddleware,
    Context,
    Continuation,
    MessageOrStream,
    MiddlewareStack,
)


@asynccontextmanager
async def async_echo_service(
    client_interceptors: Sequence[ClientInterceptor] = [],
    server_interceptors: Sequence[ServerInterceptor] = [],
):
    address = "unix:echo_service.sock"

    # configure grpc server
    credentials = grpc.local_server_credentials(grpc.LocalConnectionType.UDS)
    server = grpc.aio.server(
        futures.ThreadPoolExecutor(),
        interceptors=server_interceptors,
    )
    AsyncEchoServicer.add_to_server(server)
    server.add_secure_port(address, credentials)

    # launch server in background
    await server.start()

    # setup client channel and stub
    credentials = grpc.local_channel_credentials(grpc.LocalConnectionType.UDS)
    channel = grpc.aio.secure_channel(
        address,
        credentials,
        interceptors=client_interceptors,
    )
    stub = EchoServiceStub(channel)

    # yield stub to caller
    yield stub

    # no need to wait for running rpc's
    await server.stop(grace=None)


@pytest.mark.asyncio
async def test_async_middleware():
    class BasicMiddleware(AsyncMiddleware):
        async def on_request(
            self,
            request: MessageOrStream,
            call_next: Continuation,
            context: Context,
        ) -> MessageOrStream:
            assert isinstance(request, proto.EchoInput)

            return await call_next(proto.EchoInput(input=request.input + " And more!"))

    app = MiddlewareStack().use(BasicMiddleware())

    async with async_echo_service(
        client_interceptors=app.client_interceptors(),
    ) as service:
        request = proto.EchoInput(input="Hello, World!")
        response: proto.EchoOutput = await service.echo(request)
        assert response.output == "Hello, World! And more!"
