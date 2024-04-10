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
socketio = SocketIO(app, async_mode='threading')

rooms = ["Evan's office", "Sam's office", "Meeting room", "Break room"]
clients_room = {}
clients_old_room = {}

# moves the client to a new room (if necessary)
def change_rooms(client_id, new_room):
    global clients_room
    global clients_old_room
    old_room = clients_old_room[client_id] if client_id in clients_old_room.keys() else None
    if new_room not in clients_room.keys():
        dictionary_lock.acquire()
        clients_room[new_room] = []
        dictionary_lock.release()
    if old_room is None:
        if new_room in clients_room.keys():
            dictionary_lock.acquire()
            clients_room[new_room].append(client_id)
            dictionary_lock.release()
        join_room(f'room-{new_room}')
        dictionary_lock.acquire()
        clients_old_room[client_id] = new_room
        dictionary_lock.release()
    elif client_id not in clients_room[new_room]:
        leave_room(f'room-{old_room}')
        dictionary_lock.acquire()
        clients_room[old_room].remove(client_id)
        clients_room[new_room].append(client_id)
        join_room(f'room-{new_room}')
        clients_old_room[client_id] = new_room
        dictionary_lock.release()
    dictionary_lock.acquire()
    num_clients = len(clients_room[new_room])
    client_index = clients_room[new_room].index(client_id)
    dictionary_lock.release()

    return num_clients, client_index


@socketio.on('connect')
def handle_connect():
    client_id = flask.request.sid
    print(f'Client {client_id} connected')

@socketio.on('disconnect')
def handle_disconnect():
    client_id = flask.request.sid
    print(f'Client {client_id} disconnected')

@socketio.on('offer')
def handle_rooms(request):
    client_id = flask.request.sid
    room_id = request['room_id']
    offer = request['offer']
    change_rooms(client_id, room_id)
    socketio.send({'offerer_id': client_id, 'offer': offer, 'answerer_id': None, 'answer': None}, room=room_id, skip_sid=client_id)

@socketio.on('answer')
def handle_answer(request):
    client_id = flask.request.sid
    answer = request['answer']
    receiver_id = request['receiver_id']
    room_id = request['room_id']
    print(receiver_id)
    socketio.send({'answerer_id': client_id, 'answer': answer, "oferer_id": None, "offer": None}, room=room_id, skip_sid=client_id)


@app.route('/rooms')
def get_rooms():
    return jsonify(rooms)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=1234, debug=True, allow_unsafe_werkzeug=True)