from aiortc.contrib.media import MediaStreamTrack
import asyncio
import cv2
import numpy as np


class VideoStreamTrack(MediaStreamTrack):
    kind = "video"

    def __init__(self):
        super().__init__()
        self._queue = asyncio.Queue()

    async def recv(self):
        frame_bytes = await self._queue.get()
        frame = cv2.imdecode(np.frombuffer(frame_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
        return frame

    async def on_frame(self, frame_bytes):
        await self._queue.put(frame_bytes)


class AudioStreamTrack(MediaStreamTrack):
    kind = "audio"

    def __init__(self):
        super().__init__()
        self._queue = asyncio.Queue()

    async def recv(self):
        audio_frame = await self._queue.get()
        return audio_frame

    async def on_frame(self, audio_frame):
        await self._queue.put(audio_frame)