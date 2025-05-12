from abc import ABC, abstractmethod
from collections.abc import AsyncIterable, AsyncIterator, Awaitable, Callable, Sequence
from inspect import isawaitable
from typing import Self, TypeGuard

from google.protobuf.message import Message
from grpc.aio import (
    ClientCallDetails,
    ClientInterceptor,
    UnaryUnaryCall,
    UnaryUnaryClientInterceptor,
)

MessageOrStream = Message | AsyncIterator[Message]

Continuation = Callable[[MessageOrStream], Awaitable[MessageOrStream]]


class Context:
    pass


class AsyncMiddleware(ABC):
    @abstractmethod
    async def on_request(
        self,
        request: MessageOrStream,
        call_next: Continuation,
        context: Context,
    ) -> MessageOrStream:
        """
        Called for all incoming GRPC requests.
        """


class MiddlewareStack:
    _middleware: list[AsyncMiddleware]

    def __init__(self) -> None:
        self._middleware = []

    def use(self, middleware: AsyncMiddleware) -> Self:
        self._middleware.append(middleware)
        return self

    def client_interceptors(self) -> Sequence[ClientInterceptor]:
        return [
            MiddlewareStackUnaryUnaryClientInterceptor(self),
        ]


def _is_async_iterator(arg: object) -> TypeGuard[AsyncIterator]:
    return hasattr(arg, "__anext__")


def _is_async_iterable(arg: object) -> TypeGuard[AsyncIterable]:
    return hasattr(arg, "__aiter__")


def _is_awaitable(arg: object) -> TypeGuard[Awaitable]:
    return isawaitable(arg)


async def _handle_message_or_stream(arg: object) -> MessageOrStream:
    if _is_awaitable(arg):
        arg = await arg

    if _is_async_iterator(arg):
        return arg
    if _is_async_iterable(arg):
        return aiter(arg)
    if _is_awaitable(arg):
        return await arg
    return arg


class MiddlewareStackUnaryUnaryClientInterceptor(UnaryUnaryClientInterceptor):
    _stack: MiddlewareStack

    def __init__(self, stack: MiddlewareStack) -> None:
        super().__init__()
        self._stack = stack

    async def intercept_unary_unary[RequestT, ResponseT](
        self,
        continuation: Callable[[ClientCallDetails, RequestT], UnaryUnaryCall],
        client_call_details: ClientCallDetails,
        request: RequestT,
    ) -> UnaryUnaryCall | ResponseT:
        context = Context()
        middlewares = iter(self._stack._middleware)

        async def continue_middleware(r: MessageOrStream) -> MessageOrStream:
            try:
                next_middleware = next(middlewares)
            except StopIteration:
                # no further middleware, continue request as normal
                return await continuation(client_call_details, r)

            # forward request to next middleware in line
            return await next_middleware.on_request(r, continue_middleware, context)

        return await continue_middleware(await _handle_message_or_stream(request))
