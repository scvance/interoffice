import sounddevice as sd
import numpy as np

CHUNK = 4096
FORMAT = 'int16'  # Sounddevice uses string format for specifying data types
CHANNELS = 1
RATE = 8000

# Record audio
print("Recording audio...")
audio_data = sd.rec(int(RATE * 10), samplerate=RATE, channels=CHANNELS, dtype=FORMAT)
sd.wait()  # Wait until recording is finished
print("Audio recorded")

audio_data = audio_data.tobytes()
audio_data = np.frombuffer(audio_data, dtype=np.int16)

# Play the recorded audio
print("Playing audio...")
sd.play(audio_data, samplerate=RATE)
sd.wait()  # Wait until playback is finished
print("Audio playback finished")
