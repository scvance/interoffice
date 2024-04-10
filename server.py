# server.py

from flask import Flask, jsonify, render_template
import flask
from flask_socketio import SocketIO, emit
from flask_socketio import send, join_room, leave_room
import zlib
import threading

dictionary_lock = threading.Lock()

compressor = zlib.compressobj(level=6, strategy=zlib.Z_DEFAULT_STRATEGY)
app = Flask(__name__)
socketio = SocketIO(app)

rooms = ["Evan's office", "Sam's office", "Meeting room", "Break room"]
clients_room = {}
clients_old_room = {}

# moves the client to a new room (if necessary)
def change_rooms(client_id, new_room):
    global clients_room
    global clients_old_room
    old_room = clients_old_room[client_id] if client_id in clients_old_room.keys() else None
    # print("clients_room: ", clients_room)
    # print("clients_old_room: ", clients_old_room)
    if new_room not in clients_room.keys():
        clients_room[new_room] = []
    if old_room is None:
        if new_room in clients_room.keys():
            clients_room[new_room].append(client_id)
        join_room(f'room-{new_room}')
        clients_old_room[client_id] = new_room
    elif client_id not in clients_room[new_room]:
        leave_room(f'room-{old_room}')
        dictionary_lock.acquire()
        clients_room[old_room].remove(client_id)
        clients_room[new_room].append(client_id)
        join_room(f'room-{new_room}')
        clients_old_room[client_id] = new_room
    num_clients = len(clients_room[new_room])
    client_index = clients_room[new_room].index(client_id)
    return num_clients, client_index


@socketio.on('connect')
def handle_connect():
    client_id = flask.request.sid
    # clients_room[client_id] = None
    print(f'Client {client_id} connected')

@socketio.on('disconnect')
def handle_disconnect():
    client_id = flask.request.sid
    for room in clients_room.keys():
        if client_id in clients_room[room]:
            clients_room[room].remove(client_id)
    clients_old_room.pop(client_id, None)
    # if client_id in clients_room:
    #     del clients_room[client_id]
    print(f'Client {client_id} disconnected')

@socketio.on('send_audio')
def handle_send_audio(frame_request):
    audio_frame = frame_request['audio']
    room_number = frame_request['room']
    client_id = flask.request.sid
    audio_frame = zlib.decompress(audio_frame)

    num_other_clients, client_index = change_rooms(client_id, room_number)

    if audio_frame is not None:
        socketio.send({'video': None, 'audio': audio_frame}, room=(f'room-{room_number}'), skip_sid=client_id)

@socketio.on('send_frame')
def handle_send_frame(frame_request):
    video_frame = frame_request['video']
    room_number = frame_request['room']
    client_id = flask.request.sid
    video_frame = zlib.decompress(video_frame)

    print(client_id)

    num_other_clients, client_index = change_rooms(client_id, room_number)

    # Emit this
    # data to all clients in the same room except the sender
    if video_frame is not None:
        socketio.send({'video': video_frame, 'audio': None, 'n_clients':num_other_clients, 'client_index':client_index}, room=(f'room-{room_number}'), skip_sid=client_id)

@app.route('/rooms')
def get_rooms():
    return jsonify(rooms)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=1234, debug=True, allow_unsafe_werkzeug=True, use_reloader=False)