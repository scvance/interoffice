# server.py

from flask import Flask, jsonify, render_template
import flask
from flask_socketio import SocketIO, emit
from flask_socketio import send, join_room, leave_room
import cv2
import numpy as np
import zlib


compressor = zlib.compressobj(level=6, strategy=zlib.Z_DEFAULT_STRATEGY)
app = Flask(__name__)
socketio = SocketIO(app)

rooms = ["Evan's office", "Sam's office", "Meeting room", "Break room"]
clients_room = {}

# moves the client to a new room (if necessary)
def change_rooms(client_id, new_room):
    old_room = clients_room[client_id]
    if old_room != new_room:
        if old_room != None:
            leave_room(f'room-{old_room}')
        clients_room[client_id] = new_room
        join_room(f'room-{new_room}')

@socketio.on('connect')
def handle_connect():
    client_id = flask.request.sid
    clients_room[client_id] = None
    print(f'Client {client_id} connected')

@socketio.on('disconnect')
def handle_disconnect():
    client_id = flask.request.sid
    if client_id in clients_room:
        del clients_room[client_id]
    print(f'Client {client_id} disconnected')

@socketio.on('send_audio')
def handle_send_audio(frame_request):
    audio_frame = frame_request['audio']
    room_number = frame_request['room']
    client_id = flask.request.sid
    audio_frame = zlib.decompress(audio_frame)

    change_rooms(client_id, room_number)

    if audio_frame is not None:
        socketio.send({'video': None, 'audio': audio_frame}, room=(f'room-{room_number}'), skip_sid=client_id)

@socketio.on('send_frame')
def handle_send_frame(frame_request):
    video_frame = frame_request['video']
    room_number = frame_request['room']
    client_id = flask.request.sid
    # video_frame = zlib.decompress(video_frame)



    change_rooms(client_id, room_number)

    # Emit this
    # data to all clients in the same room except the sender
    if video_frame is not None:
        socketio.send({'video': video_frame, 'audio': None}, room=(f'room-{room_number}'), skip_sid=client_id)

@app.route('/rooms')
def get_rooms():
    return jsonify(rooms)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=1234, debug=True, allow_unsafe_werkzeug=True)