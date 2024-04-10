import asyncio
from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack
from av import VideoFrame
from fractions import Fraction
import numpy as np
import time

class CameraVideoTrack(VideoStreamTrack):
    """
    A video stream track that captures video frames from a webcam.
    """
    def __init__(self):
        super().__init__()  # Initialize the base class

    async def recv(self):
        frame = VideoFrame.from_ndarray(generate_frame(), format="bgr24")
        frame.pts = time.time()
        frame.time_base = Fraction(1, 1000)
        return frame

def generate_frame():
    """
    Generate a dummy frame for demonstration purposes.
    Replace this with actual webcam frame capture code.
    """
    return np.zeros((480, 640, 3), dtype=np.uint8)

async def run():
    # Create peer connection
    pc = RTCPeerConnection()
    pc.addTrack(CameraVideoTrack())

    # Handle offer from console
    offer = input("Enter the offer SDP: ")
    if offer:
        await pc.setRemoteDescription(RTCSessionDescription(sdp=offer, type='offer'))

        # Create an answer
        answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)

        print("Answer SDP:")
        print(answer.sdp)

asyncio.run(run())
