# Modified by joelhoty in 2026 from jhj0517/Whisper-WebUI (Apache-2.0): Replaced pytubefix with yt-dlp for YouTube metadata and audio downloads.
# See README.md for the full list of changes.
import os
from typing import Tuple

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

# Optional Netscape-format cookies file. Only needed when YouTube refuses anonymous downloads.
COOKIES_FILE_ENV = "YOUTUBE_COOKIES_FILE"


def _ydl_options(**options):
    options = {"quiet": True, "no_warnings": True, "noprogress": True, "noplaylist": True, **options}
    cookies_file = os.environ.get(COOKIES_FILE_ENV)
    if cookies_file:
        options["cookiefile"] = cookies_file
    return options


def get_ytmetas(link):
    if not link or not link.strip():
        return None, None, ""
    try:
        with YoutubeDL(_ydl_options(skip_download=True)) as ydl:
            info = ydl.extract_info(link.strip(), download=False)
    except DownloadError as e:
        return None, None, f"Failed to load video info: {e}"
    return info.get("thumbnail"), info.get("title"), info.get("description")


def download_ytaudio(link, output_dir) -> Tuple[str, str]:
    """Download the audio of a YouTube video as WAV into output_dir. Returns (audio_path, title)."""
    options = _ydl_options(
        format="bestaudio/best",
        outtmpl=os.path.join(output_dir, "audio.%(ext)s"),
        # Re-encode so the input is always a valid audio file (#304).
        postprocessors=[{"key": "FFmpegExtractAudio", "preferredcodec": "wav"}],
    )
    with YoutubeDL(options) as ydl:
        info = ydl.extract_info(link.strip(), download=True)
    audio_path = info["requested_downloads"][0]["filepath"]
    return audio_path, info.get("title") or info["id"]
