import os
import sys
from openai import OpenAI

# maximum file size is 26214400 bytes (2024-08-03)

if len(sys.argv) < 2:
    print('Please provide a file to transcribe')
    sys.exit(1)
file_name = sys.argv[1]

if not os.getenv('OPENAI_API_KEY'):
    print('Please provide an API key')
    sys.exit(1)

client = OpenAI()
file_name_base = os.path.splitext(file_name)[0]

audio_file = open(file_name, 'rb')
transcription = client.audio.transcriptions.create(
    model='whisper-1',
    file = audio_file,
    language='ru',
)
with open(f'{file_name_base}.txt', 'w') as f:
    f.write(transcription.text)
