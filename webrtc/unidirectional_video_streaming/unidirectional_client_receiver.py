import asyncio
from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack, AudioStreamTrack
import cv2
import socketio

pc = None
video_stream = None
SERVER_IP = 'localhost'
SOCKETIO_URL = f'ws://{SERVER_IP}:1234/'
sio = socketio.AsyncClient()
async def negotiate():
    global sio
    pc.addTransceiver('video', direction='recvonly')
    pc.addTransceiver('audio', direction='recvonly')

    offer = await pc.createOffer()
    await pc.setLocalDescription(offer)

    while pc.iceGatheringState != 'complete':
        await asyncio.sleep(0.1)

    offer = pc.localDescription
    await sio.emit('offer', {'sdp': offer.sdp, 'type': offer.type})
    answer = None
    async def answer_callback(response):
        nonlocal answer
        answer = response['sdp']
        # this disconnect breaks the sio wait loop
        await sio.disconnect()
    sio.on('answer', answer_callback)
    await sio.wait()
    # reconnect to the sio (not strictly necessary for _current_ functionality)
    await sio.connect(SOCKETIO_URL)
    await pc.setRemoteDescription(RTCSessionDescription(sdp=answer, type='answer'))

async def start():
    global pc, video_stream, use_stun
    # config = {'sdpSemantics': 'unified-plan'}
    # use_stun = False
    # if use_stun:
    #     config['iceServers'] = [{'urls': ['stun:stun.l.google.com:19302']}]

    pc = RTCPeerConnection()

    @pc.on('track')
    async def on_track(track):
        global video_stream
        if track.kind == 'video':
            while True:
                frame = await track.recv()
                frame_rgb = frame.to_ndarray(format='rgb24')
                frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
                cv2.imshow('Received Video', frame_bgr)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
        elif track.kind == 'audio':
            audio_track = track
            audio_track.onended = lambda: audio_track.stop()

    pc.addTrack(VideoStreamTrack())
    # pc.addTrack(AudioStreamTrack())

    await negotiate()

async def stop():
    await pc.close()

async def main():
    await sio.connect(SOCKETIO_URL)
    await start()
    # terminate after 20 seconds
    await asyncio.sleep(20)
    await stop()

if __name__ == '__main__':

    asyncio.run(main())
