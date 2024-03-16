# server.py

from flask import Flask, render_template
import flask
from flask_socketio import SocketIO, emit
from flask_socketio import send, join_room, leave_room
import cv2
import numpy as np
import zlib


compressor = zlib.compressobj(level=6, strategy=zlib.Z_DEFAULT_STRATEGY)
app = Flask(__name__)
socketio = SocketIO(app)
clients = {}
clients_room = {}
@socketio.on('connect')
def handle_connect():
    client_id = flask.request.sid
    clients[client_id] = None
    print(f'Client {client_id} connected')

@socketio.on('disconnect')
def handle_disconnect():
    client_id = flask.request.sid
    if client_id in clients:
        del clients[client_id]
    print(f'Client {client_id} disconnected')

@socketio.on('send_audio')
def handle_send_audio(frame_request):
    audio_frame = frame_request['audio']
    room_number = frame_request['room']
    client_id = flask.request.sid
    join_room(room_number)
    audio_frame = zlib.decompress(audio_frame)

    if audio_frame is not None:
        socketio.send({'video': None, 'audio': audio_frame}, room=room_number, skip_sid=client_id)

@socketio.on('send_frame')
def handle_send_frame(frame_request):
    video_frame = frame_request['video']
    room_number = frame_request['room']
    client_id = flask.request.sid
    video_frame = zlib.decompress(video_frame)

    # Join the client to the specified room
    join_room(room_number)

    # Emit this data to all clients in the same room except the sender
    if video_frame is not None:
        socketio.send({'video': video_frame, 'audio': None}, room=room_number, skip_sid=client_id)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=1234, debug=True, allow_unsafe_werkzeug=True)