"""ZeroMQ wrappers for signal dispatch and result consumption."""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

import zmq
import zmq.asyncio

from .models import ValidatedSignal

log = logging.getLogger(__name__)


class ZMQProducer:
    """PUSH socket — sends validated signals to trade engine."""

    def __init__(self, address: str) -> None:
        self.address = address
        self._ctx = zmq.asyncio.Context.instance()
        self._socket = self._ctx.socket(zmq.PUSH)
        self._socket.setsockopt(zmq.SNDHWM, 1000)
        self._socket.setsockopt(zmq.LINGER, 1000)
        self._socket.connect(address)
        self.connected = True
        log.info("ZMQ producer connected to %s", address)

    async def send(self, signal: ValidatedSignal) -> None:
        try:
            await self._socket.send_json(signal.model_dump())
        except zmq.ZMQError as e:
            self.connected = False
            log.error("ZMQ send error: %s", e)
            raise

    def close(self) -> None:
        self._socket.close()
        self.connected = False


class ZMQConsumer:
    """PULL socket — receives execution results from MT5 bridge."""

    def __init__(self, address: str) -> None:
        self.address = address
        self._ctx = zmq.asyncio.Context.instance()
        self._socket = self._ctx.socket(zmq.PULL)
        self._socket.setsockopt(zmq.RCVHWM, 1000)
        self._socket.setsockopt(zmq.LINGER, 1000)
        self._socket.bind(address)
        log.info("ZMQ result consumer bound to %s", address)

    async def receive(self) -> Optional[dict]:
        try:
            if await self._socket.poll(timeout=100):
                return await self._socket.recv_json()
            return None
        except zmq.ZMQError as e:
            log.error("ZMQ recv error: %s", e)
            return None

    def close(self) -> None:
        self._socket.close()


class ZMQStateSubscriber:
    """SUB socket — receives state updates from trade engine."""

    def __init__(self, address: str) -> None:
        self.address = address
        self._ctx = zmq.asyncio.Context.instance()
        self._socket = self._ctx.socket(zmq.SUB)
        self._socket.setsockopt(zmq.RCVHWM, 1000)
        self._socket.setsockopt(zmq.LINGER, 1000)
        self._socket.setsockopt_string(zmq.SUBSCRIBE, "")
        self._socket.connect(address)
        log.info("ZMQ state subscriber connected to %s", address)

    async def receive(self) -> Optional[dict]:
        try:
            if await self._socket.poll(timeout=100):
                return await self._socket.recv_json()
            return None
        except zmq.ZMQError as e:
            log.error("ZMQ state recv error: %s", e)
            return None

    def close(self) -> None:
        self._socket.close()
