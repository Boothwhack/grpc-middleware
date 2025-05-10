from collections.abc import Iterator
from concurrent import futures
from contextlib import contextmanager
from secrets import token_hex

import grpc

from grpc_echo import EchoServicer, EchoServiceStub, proto


@contextmanager
def echo_service():
    address = "unix:echo_service.sock"

    # configure grpc server
    credentials = grpc.local_server_credentials(grpc.LocalConnectionType.UDS)
    server = grpc.server(futures.ThreadPoolExecutor())
    EchoServicer.add_to_server(server)
    server.add_secure_port(address, credentials)

    # launch server in background
    server.start()

    # setup client channel and stub
    credentials = grpc.local_channel_credentials(grpc.LocalConnectionType.UDS)
    channel = grpc.secure_channel(address, credentials)
    stub = EchoServiceStub(channel)

    # yield stub to caller
    yield stub

    # no need to wait for running rpc's
    server.stop(grace=None)


def test_echo_unary_unary_input():
    """Service should respons with input string as output."""
    with echo_service() as service:
        text = token_hex(16)

        response: proto.EchoOutput = service.echo(proto.EchoInput(input=text))
        assert response.output == text


def test_echo_unary_stream_input():
    """
    Service should split input string into characters and respond with a message
    for each.
    """
    with echo_service() as service:
        text = token_hex(16)
        characters = list(text)

        request = proto.EchoInput(input=text)
        response_iterator: Iterator[proto.EchoOutput] = service.echo_chars(request)
        output = [response.output for response in response_iterator]

        assert output == characters


def test_echo_stream_unary_input():
    """Service should respond by concatenating every input string."""
    with echo_service() as service:
        texts = [token_hex(4) for _ in range(4)]
        concatenated = "".join(texts)

        response: proto.EchoOutput = service.echo_concat(
            proto.EchoInput(input=t) for t in texts
        )

        assert response.output == concatenated


def test_echo_stream_stream_input():
    """
    Service should respond with every input string as seperate output messages.
    """
    with echo_service() as service:
        texts = [token_hex(4) for _ in range(4)]

        requests = (proto.EchoInput(input=t) for t in texts)
        response_iterator: Iterator[proto.EchoOutput] = service.echo_stream(requests)
        outputs = [response.output for response in response_iterator]

        assert outputs == texts
