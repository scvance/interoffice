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
    socketio.emit('offer', {'sdp': request['sdp'], 'type': 'offer'})


@socketio.on('answer')
def handle_answer(request):
    print("Received answer")
    socketio.emit('answer', {'sdp': request['sdp'], 'type': 'answer'})

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=1234, debug=True, allow_unsafe_werkzeug=True)