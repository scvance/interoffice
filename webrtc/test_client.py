import socketio
import threading
import requests
import json
import argparse
import asyncio
import logging
import time
from aiortc import RTCIceCandidate, RTCPeerConnection, RTCSessionDescription
from aiortc.contrib.signaling import BYE, add_signaling_arguments, create_signaling


SERVER_IP = 'localhost'  # get your server's IP and put it here
SOCKETIO_URL = f'ws://{SERVER_IP}:1234/'
HTTP_URL = f'http://{SERVER_IP}:1234'

sio = socketio.AsyncClient()

curr_room = 0
video_room = 0
audio_room = 0
display_room = 0
audio_lock = threading.Lock()
audio_room_lock = threading.Lock()
video_room_lock = threading.Lock()
curr_room_lock = threading.Lock()
display_room_lock = threading.Lock()
last_frame_lock = threading.Lock()
video_lock = threading.Lock()

pc = None
sender = None

@sio.event
async def connect():
    print('Connected to server')


@sio.event
async def disconnect():
    print('Disconnected from server')


@sio.event
async def message(connection_data):
    global pc
    global sender
    if connection_data['offer'] is not None and pc.signalingState != 'stable':
        print('Received offer')
        sender = False
        oferer_id = connection_data['offerer_id']
        pc = RTCPeerConnection()
        await pc.setRemoteDescription(RTCSessionDescription(sdp=connection_data['offer'], type='offer'))
        await pc.setLocalDescription(await pc.createAnswer())
        await run(offerer=False)
        await sio.emit('answer', {'answer': pc.localDescription.sdp, 'room_id': 0, 'receiver_id': oferer_id})
    elif connection_data['answer'] is not None and pc.signalingState == 'have-local-offer':
        sender = True
        print('Received answer')
        await pc.setRemoteDescription(RTCSessionDescription(sdp=connection_data['answer'], type='answer'))
    # elif connection_data['candidate'] is not None:
    #     print('Received candidate')
    #     pc.addIceCandidate(RTCIceCandidate(connection_data['candidate'], sdpMid=connection_data['sdpMid'], sdpMLineIndex=connection_data['sdpMLineIndex']))



def channel_log(channel, t, message):
    print("channel(%s) %s %s" % (channel.label, t, message))


def channel_send(channel, message):
    channel_log(channel, ">", message)
    channel.send(message)


async def consume_signaling(pc, signaling):
    while True:
        obj = await signaling.receive()

        if isinstance(obj, RTCSessionDescription):
            await pc.setRemoteDescription(obj)

            if obj.type == "offer":
                # send answer
                await pc.setLocalDescription(await pc.createAnswer())
                await signaling.send(pc.localDescription)
        elif isinstance(obj, RTCIceCandidate):
            await pc.addIceCandidate(obj)
        elif obj is BYE:
            print("Exiting")
            break


time_start = None


def current_stamp():
    global time_start

    if time_start is None:
        time_start = time.time()
        return 0
    else:
        return int((time.time() - time_start) * 1000000)


async def run_answer(pc, signaling):
    await signaling.connect()

    @pc.on("datachannel")
    def on_datachannel(channel):
        channel_log(channel, "-", "created by remote party")

        @channel.on("message")
        def on_message(message):
            channel_log(channel, "<", message)

            if isinstance(message, str) and message.startswith("ping"):
                # reply
                channel_send(channel, "pong" + message[4:])

    # await consume_signaling(pc, signaling)


async def run(offerer=True):
    global pc
    # await signaling.connect()
    print(sender)
    channel = pc.createDataChannel("chat")
    channel_log(channel, "-", "created by local party")

    async def send_pings():
        while True:
            channel_send(channel, "ping %d" % current_stamp())
            await asyncio.sleep(1)

    @channel.on("open")
    def on_open():
        asyncio.ensure_future(send_pings())

    @channel.on("message")
    def on_message(message):
        channel_log(channel, "<", message)

        if isinstance(message, str) and message.startswith("pong"):
            elapsed_ms = (current_stamp() - int(message[5:])) / 1000
            print(" RTT %.2f ms" % elapsed_ms)

    @pc.on("datachannel")
    def on_datachannel(channel):
        channel_log(channel, "-", "created by remote party")

        @channel.on("message")
        def on_message(message):
            channel_log(channel, "<", message)

            if isinstance(message, str) and message.startswith("ping"):
                # reply
                channel_send(channel, "pong" + message[4:])

    @pc.on("connectionstatechange")
    async def on_connectionstatechange():
        print("Connection state is %s" % pc.connectionState)
        if pc.connectionState == "failed":
            await pc.close()
            # pcs.discard(pc)

    # send offer
    #if pc.connectionState != 'connected' and pc.connectionState != "connecting":
    if offerer:
        await pc.setLocalDescription(await pc.createOffer())
            # await signaling.send(pc.localDescription)
        await sio.emit('offer', {'offer': pc.localDescription.sdp, 'room_id': 0})

    # await consume_signaling(pc, signaling)

async def main():
    global pc
    await sio.connect(SOCKETIO_URL)
    res = requests.get(f'{HTTP_URL}/rooms')
    rooms = json.loads(res.content)
    parser = argparse.ArgumentParser(description="Data channels ping/pong")
    add_signaling_arguments(parser)
    args = parser.parse_args()
    signaling = create_signaling(args)
    pc = RTCPeerConnection()
    # task = asyncio.create_task(run())
    # loop = asyncio.get_event_loop()
    # coro = await run()

    try:
        # loop.run_until_complete(coro)
        await run(offerer=True)
        await sio.wait()
    except KeyboardInterrupt:
        pass
    finally:
        await sio.disconnect()
        await pc.close()
        signaling.close()
        # loop.run_until_complete(await pc.close())
        # loop.run_until_complete(signaling.close())

if __name__ == "__main__":
    asyncio.run(main())
