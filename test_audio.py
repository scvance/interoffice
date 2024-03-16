import alsaaudio
import zlib
import numpy as np

CHUNK = 1024
FORMAT = alsaaudio.PCM_FORMAT_S16_LE
CHANNELS = 1
RATE = 8000

# Record audio
audio_in = alsaaudio.PCM(alsaaudio.PCM_CAPTURE, alsaaudio.PCM_NORMAL, channels=CHANNELS, rate=RATE, format=FORMAT, periodsize=CHUNK)
# audio_in.setchannels(CHANNELS)
# audio_in.setrate(RATE)
# audio_in.setformat(FORMAT)
# audio_in.setperiodsize(CHUNK)

audio_chunks = []
for i in range(0, int(RATE / CHUNK)):
    length, data = audio_in.read()
    audio_chunks.append(data)

audio_chunks = zlib.compress(np.array(audio_chunks).tobytes())
audio_chunks = zlib.decompress(audio_chunks)
audio_chunks = np.frombuffer(audio_chunks, dtype=np.int16)

# Play audio
audio_out = alsaaudio.PCM(alsaaudio.PCM_PLAYBACK, alsaaudio.PCM_NORMAL, channels=CHANNELS, rate=RATE, format=FORMAT, periodsize=CHUNK)
# audio_out.setchannels(CHANNELS)
# audio_out.setrate(RATE)
# audio_out.setformat(FORMAT)
# audio_out.setperiodsize(CHUNK)

for chunk in audio_chunks:
    audio_out.write(chunk)

print("Audio recorded and played")

