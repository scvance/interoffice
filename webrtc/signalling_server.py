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
connected_clients = []

@socketio.on('connect')
def handle_connect():
    client_id = flask.request.sid
    connected_clients.append(client_id)
    print(f'Client {client_id} connected')

@socketio.on('disconnect')
def handle_disconnect():
    client_id = flask.request.sid
    connected_clients.remove(client_id)
    print(f'Client {client_id} disconnected')

@socketio.on('offer')
def handle_rooms(request):
    client_id = flask.request.sid
    # if nobody else is connected im gonna send a failure so that client is not just waiting for an answer that will never come
    # even worse, since there is a timeout for it to wait for an answer, if offer comes during the timeout it may confuse
    # everything
    # Also it might be no big deal to just emit the offer. idk.
    if len(connected_clients) < 2:
        socketio.emit('failure', {'type': 'failure'})
    else:
        socketio.emit('offer', {'sdp': request['sdp'], 'type': 'offer', 'client': client_id})


@socketio.on('answer')
def handle_answer(request):
    client_id = flask.request.sid
    print("Received answer")
    socketio.emit('answer', {'sdp': request['sdp'], 'type': 'answer', 'client': client_id})

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=1234, debug=True, allow_unsafe_werkzeug=True)