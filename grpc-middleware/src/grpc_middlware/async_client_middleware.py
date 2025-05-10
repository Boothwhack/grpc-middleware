from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Awaitable
from typing import Callable

from google.protobuf.message import Message

MessageOrStream = Message | AsyncIterator[Message]

Continuation = Callable[[MessageOrStream], Awaitable[MessageOrStream]]


class Context:
    pass


class AsyncClientMiddleware(ABC):
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
