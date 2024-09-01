from pathlib import Path
import os
import sys
from openai import OpenAI

# maximum file size is 26214400 bytes (2024-08-03)

if len(sys.argv) < 2:
    print('Please provide a file to transcribe')
    sys.exit(1)
file_path = Path(sys.argv[1])

if not os.getenv('OPENAI_API_KEY'):
    print('Please provide an API key')
    sys.exit(1)

client = OpenAI()

audio_file = open(file_path, 'rb')
transcription = client.audio.transcriptions.create(
    model='whisper-1',
    file = audio_file,
    language='ru',
)
with open(file_path.parent / f'{file_path.stem}.txt', 'w') as f:
    f.write(transcription.text)
