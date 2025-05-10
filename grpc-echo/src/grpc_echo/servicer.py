from collections.abc import Generator, Iterator

from grpc import Server, ServicerContext, StatusCode

from . import echo_pb2 as proto
from .echo_pb2_grpc import EchoServiceServicer, add_EchoServiceServicer_to_server


class EchoServicer(EchoServiceServicer):
    @classmethod
    def add_to_server(cls, server: Server):
        add_EchoServiceServicer_to_server(cls(), server)

    def echo(
        self,
        request: proto.EchoInput,
        context: ServicerContext,
    ) -> proto.EchoOutput:
        match request.WhichOneof("value"):
            case "input":
                return proto.EchoOutput(output=request.input)
            case "error":
                context.abort(
                    StatusCode(request.error.status_code),
                    request.error.details,
                )
            case _:
                context.abort(
                    StatusCode.INVALID_ARGUMENT,
                    "'input' or 'error' must be specified.",
                )

    def echo_chars(
        self,
        request: proto.EchoInput,
        context: ServicerContext,
    ) -> Generator[proto.EchoOutput]:
        response = self.echo(request, context)
        for c in response.output:
            yield proto.EchoOutput(output=c)

    def echo_concat(
        self,
        request_iterator: Iterator[proto.EchoInput],
        context: ServicerContext,
    ) -> proto.EchoOutput:
        output = ""
        for request in request_iterator:
            response = self.echo(request, context)
            output = output + response.output

        return proto.EchoOutput(output=output)

    def echo_stream(
        self,
        request_iterator: Iterator[proto.EchoInput],
        context: ServicerContext,
    ) -> Generator[proto.EchoOutput]:
        for request in request_iterator:
            yield self.echo(request, context)
