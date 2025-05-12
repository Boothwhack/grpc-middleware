from collections.abc import AsyncIterator

from grpc import StatusCode
from grpc.aio import Server, ServicerContext

from . import echo_pb2 as proto
from .echo_pb2_grpc import EchoServiceServicer, add_EchoServiceServicer_to_server


class AsyncEchoServicer(EchoServiceServicer):
    @classmethod
    def add_to_server(cls, server: Server):
        add_EchoServiceServicer_to_server(cls(), server)

    async def echo(
        self,
        request: proto.EchoInput,
        context: ServicerContext,
    ) -> proto.EchoOutput:
        match request.WhichOneof("value"):
            case "input":
                return proto.EchoOutput(output=request.input)
            case "error":
                await context.abort(
                    StatusCode(request.error.status_code),
                    request.error.details,
                )
            case _:
                await context.abort(
                    StatusCode.INVALID_ARGUMENT,
                    "'input' or 'error' must be specified.",
                )

    async def echo_chars(
        self,
        request: proto.EchoInput,
        context: ServicerContext,
    ) -> AsyncIterator[proto.EchoOutput]:
        response = await self.echo(request, context)
        for c in response.output:
            yield proto.EchoOutput(output=c)

    async def echo_concat(
        self,
        request_iterator: AsyncIterator[proto.EchoInput],
        context: ServicerContext,
    ) -> proto.EchoOutput:
        output = ""
        async for request in request_iterator:
            response = await self.echo(request, context)
            output = output + response.output

        return proto.EchoOutput(output=output)

    async def echo_stream(
        self,
        request_iterator: AsyncIterator[proto.EchoInput],
        context: ServicerContext,
    ) -> AsyncIterator[proto.EchoOutput]:
        async for request in request_iterator:
            yield await self.echo(request, context)
