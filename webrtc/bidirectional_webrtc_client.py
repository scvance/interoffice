from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack, AudioStreamTrack
import cv2
import asyncio
import os
import platform
import socketio
from aiortc.contrib.media import MediaPlayer, MediaRelay

ROOT = os.path.dirname(__file__)
pc = None
# eventually remove the pc and instead only use the set of pcs
pcs = set()
video_stream = None
SERVER_IP = 'localhost'
SOCKETIO_URL = f'ws://{SERVER_IP}:1234/'
sio = socketio.AsyncClient()
sid = None
relay = None
webcam = None

def create_local_tracks(play_from, decode):
    global relay, webcam

    if play_from:
        player = MediaPlayer(play_from, decode=decode)
        return player.audio, player.video
    else:
        options = {"framerate": "30", "video_size": "640x480"}
        if relay is None:
            if platform.system() == "Darwin":
                webcam = MediaPlayer(
                    "default:none", format="avfoundation", options=options
                )
            elif platform.system() == "Windows":
                webcam = MediaPlayer(
                    "video=Integrated Camera", format="dshow", options=options
                )
            else:
                webcam = MediaPlayer("/dev/video0", format="v4l2", options=options)
            relay = MediaRelay()
        return None, relay.subscribe(webcam.video)

async def offer(request):
    if (request["client"] == sid):
        return
    params = request
    offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])

    pc = RTCPeerConnection()
    pcs.add(pc)

    @pc.on("connectionstatechange")
    async def on_connectionstatechange():
        print("Connection state is %s" % pc.connectionState)
        if pc.connectionState == "failed":
            await pc.close()
            pcs.discard(pc)

    audio, video = create_local_tracks(
        None, decode=True
    )

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
                    await pc.close()
                    break
        elif track.kind == 'audio':
            audio_track = track
            audio_track.onended = lambda: audio_track.stop()

    if audio:
        audio_sender = pc.addTrack(audio)

    if video:
        video_sender = pc.addTrack(video)

    await pc.setRemoteDescription(offer)

    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)
    await sio.emit('answer', {'sdp': pc.localDescription.sdp, 'type': pc.localDescription.type})


async def negotiate():
    global sio, pc
    pc.addTransceiver('video', direction='sendrecv')
    pc.addTransceiver('audio', direction='sendrecv')

    offer = await pc.createOffer()
    await pc.setLocalDescription(offer)

    while pc.iceGatheringState != 'complete':
        await asyncio.sleep(0.1)

    offer = pc.localDescription
    await sio.emit('offer', {'sdp': offer.sdp, 'type': offer.type})
    answer = None
    # received is a future event that we will wait for (we want to wait for the answer event)
    received = asyncio.Future()
    async def answer_callback(response):
        nonlocal answer
        answer = response['sdp']
        print("called")
        received.set_result(answer)
    async def failure_callback(response):
        print("Failure")
        received.set_result('failure')
    # Set the callback for the answer event
    sio.on('answer', answer_callback)
    sio.on('failure', failure_callback)
    # Wait for the answer event to be received timeout after 5 seconds
    await asyncio.wait_for(received, timeout=5)
    if answer is not None:
        await pc.setRemoteDescription(RTCSessionDescription(sdp=answer, type='answer'))
    else:
        await pc.close()

async def start():
    global pc, video_stream, use_stun
    # config = {'sdpSemantics': 'unified-plan'}
    # use_stun = False
    # if use_stun:
    #     config['iceServers'] = [{'urls': ['stun:stun.l.google.com:19302']}]

    pc = RTCPeerConnection()

    @pc.on("connectionstatechange")
    async def on_connectionstatechange():
        print("Connection state is %s" % pc.connectionState)
        if pc.connectionState == "failed":
            await pc.close()
            pcs.discard(pc)
    audio, video = create_local_tracks(
        None, decode=True
    )


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
    if audio:
        audio_sender = pc.addTrack(audio)

    if video:
        video_sender = pc.addTrack(video)
    # pc.addTrack(VideoStreamTrack())
    # pc.addTrack(AudioStreamTrack())

    await negotiate()

async def stop():
    await pc.close()

async def on_shutdown(app):
    # close peer connections
    coros = [pc.close() for pc in pcs]
    await asyncio.gather(*coros)
    pcs.clear()

async def main():
    await sio.connect(SOCKETIO_URL)
    global sid
    sid = sio.sid
    await start()
    sio.on('offer', offer)
    await sio.wait()
    # # terminate after 20 seconds
    # await asyncio.sleep(20)
    # await stop()

if __name__ == '__main__':

    asyncio.run(main())
