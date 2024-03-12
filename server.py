# server.py

from flask import Flask, render_template
import flask
from flask_socketio import SocketIO, emit
from flask_socketio import send, join_room, leave_room
import cv2
import numpy as np

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

@socketio.on('send_frame')
def handle_send_frame(frame_request):
    frame_data = frame_request['frame']
    room_number = frame_request['room']
    client_id = flask.request.sid

    # Join the client to the specified room
    join_room(room_number)

    # Emit this data to all clients in the same room except the sender
    if frame_data is not None:
        socketio.send({'frame_data': frame_data}, room=room_number, skip_sid=client_id)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=1234, debug=True, allow_unsafe_werkzeug=True)
