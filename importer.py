import audiosegment
import os
from openai import OpenAI
from pathlib import Path
from pydub import AudioSegment
import requests
import shutil
import sqlite3
import sys
import typer
from urllib.parse import urlparse, unquote

app = typer.Typer()

DEFAULT_DB_PATH = Path.home() / "Library/Group Containers/243LU875E5.groups.com.apple.podcasts/Documents/MTLibrary.sqlite"
AUDIO_FILE_PATH = Path.home() / "Library/Group Containers/243LU875E5.groups.com.apple.podcasts/Library/Cache/"
EPISODE_ASSET_FILE_PATH = Path.home() / "Library/Group Containers/243LU875E5.groups.com.apple.podcasts/Library/Cache/Assets/Artwork/"
ALT_SHOW_IMAGE_FILE_PATH = Path.home() / "Library/Group Containers/243LU875E5.groups.com.apple.podcasts/Library/Cache/IMImageStore-Default/"

def get_shows_with_downloads(cursor):
    query = """
    SELECT DISTINCT ZMTPODCAST.Z_PK, ZMTPODCAST.ZTITLE, ZMTPODCAST.ZUUID, ZMTPODCAST.ZARTWORKTEMPLATEURL
    FROM ZMTEPISODE, ZMTPODCAST
    WHERE ZMTEPISODE.ZPODCAST = ZMTPODCAST.Z_PK AND ZMTPODCAST.ZDOWNLOADEDEPISODESCOUNT>0
    AND ZASSETURL IS NOT NULL;
    """
    cursor.execute(query)
    return cursor.fetchall()

# ZASSETURL has a file:// URL to the episode file
def get_episodes_for_show(cursor, show_id):
    query = """
    SELECT ZUUID, ZCLEANEDTITLE, ZASSETURL, ZARTWORKTEMPLATEURL
    FROM ZMTEPISODE
    WHERE ZPODCAST = ? AND ZASSETURL IS NOT NULL;
    """
    cursor.execute(query, (show_id,))
    return cursor.fetchall()

def download_image(url, path):
    response = requests.get(url, stream=True)
    with open(path, 'wb') as out_file:
        for chunk in response.iter_content(chunk_size=1024):
            out_file.write(chunk)

def segment_on_voice(file_path: Path, target_duration=20*60*1000):  # 20 minutes in milliseconds
    audio = AudioSegment.from_mp3(file_path)
    seg = audiosegment.from_file(file_path).resample(sample_rate_Hz=32000, sample_width=2, channels=1)

    # Detect voice sections (returns a list of tuples with start and end times in milliseconds)
    voice_segments = seg.detect_voice()
    speaking_pairs = [voice_segments[i:i+2] for i in range(0, len(voice_segments), 2)]

    current_segment = AudioSegment.silent(duration=0)
    cursor = 0
    segments = []

    for pair in speaking_pairs:
        chunk = pair[0][1] + pair[1][1] if len(pair) == 2 else pair[0][1] # combine the AudioSegments in the pair

        # Check if adding speaking and silence from the pair would exceed the target duration
        if len(current_segment) + len(chunk) > target_duration:
            # Save the current segment
            segments.append(current_segment)
            current_segment = AudioSegment.silent(duration=0)

        # Add the section of the original audio that corresponds to the resampled chunk
        slice = audio[cursor:cursor+len(chunk)]
        current_segment = current_segment + slice
        cursor += len(chunk)

    # Add the last segment
    if len(current_segment) > 0:
        segments.append(current_segment)

    # Export segments
    for i, segment in enumerate(segments):
        segment.export(file_path.parent / f'{file_path.stem}_{i+1}.mp3', format="mp3")

@app.command()
def navigate_podcasts(db_path: str = typer.Argument(DEFAULT_DB_PATH, help="Path to the Apple Podcasts SQLite database")):
    if not Path(db_path).exists():
        typer.echo("Database not found at the specified location.")
        return

    uri = f"file:{db_path}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)  # uri=True allows the use of URI options like mode=ro
    cursor = connection.cursor()

    shows = get_shows_with_downloads(cursor)
    if not shows:
        typer.echo("No shows with downloaded episodes found.")
        return

    typer.echo("Select a podcast show:")
    for idx, (_, show, *__) in enumerate(shows, start=1):
        typer.echo(f"{idx:3}. {show}")

    show_choice = typer.prompt("Enter the number of the show", type=int)
    (
        show_pk,
        show_name,
        show_uuid,
        show_artwork_template_url,
    ) = shows[show_choice - 1]

    episodes = get_episodes_for_show(cursor, show_pk)
    if not episodes:
        typer.echo(f"No downloaded episodes found for {show_name}.")
        return

    connection.close()

    typer.echo(f"Select an episode from {show_name}:")
    for idx, (_, episode, *__) in enumerate(episodes, start=1):
        typer.echo(f"{idx:3}. {episode}")

    episode_choice = typer.prompt("Enter the number of the episode", type=int)
    (
        episode_pk,
        episode_name,
        episode_asset_url,
        episode_artwork_template_url,
    ) = episodes[episode_choice - 1]

    typer.echo(f'{show_name} / {episode_name}')

    show_dir = Path.cwd() / 'assets' / show_name
    episode_dir = show_dir / episode_name

    episode_dir.mkdir(parents=True, exist_ok=True)

    episode_path = Path(unquote(urlparse(episode_asset_url).path))
    episode_dst = episode_dir / f'{episode_name}{episode_path.suffix}'

    shutil.copy(episode_path, episode_dst)

    if show_artwork_template_url:
        show_artwork_url = show_artwork_template_url.format(w=600, h=600, f="png")
        download_image(show_artwork_url, show_dir / f'{show_name}.png')
    if episode_artwork_template_url:
        episode_artwork_url = episode_artwork_template_url.format(w=600, h=600, f="png")
        download_image(episode_artwork_url, episode_dir / f'{episode_name}.png')

    print('Segmenting audio...')
    segment_on_voice(episode_dst)

if __name__ == "__main__":
    app()
