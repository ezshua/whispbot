"""Utility functions for Whispbot."""

import logging
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

FALLBACK_TEMP_DIR = Path("temp")


def get_system_temp_dir() -> Path | None:
    """Get system temporary directory path.

    Checks TEMP, TMP, and Unix /tmp in order.

    Returns:
        Optional[Path]: System temp directory or None
    """
    for var in ("TEMP", "TMP", "TMPDIR"):
        val = os.environ.get(var)
        if val:
            return Path(val) / "whispbot"
    if Path("/tmp").exists():
        return Path("/tmp") / "whispbot"
    return None


def ensure_temp_dir(path: Path) -> Path:
    """Ensure temp directory exists and is writable.

    Tries the given path first, then system TEMP/TMP, then FALLBACK_TEMP_DIR.

    Args:
        path: Desired temp directory path

    Returns:
        Path: Usable temp directory path
    """
    candidates = [path]

    sys_temp = get_system_temp_dir()
    if sys_temp:
        candidates.append(sys_temp)

    if FALLBACK_TEMP_DIR not in candidates:
        candidates.append(FALLBACK_TEMP_DIR)

    for candidate in candidates:
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            test_file = candidate / ".write_test"
            test_file.write_text("")
            test_file.unlink()
            return candidate
        except Exception as e:
            if candidate is candidates[-1]:
                logger.warning(
                    "Temp dir '%s' not usable (%s), falling back to '%s'", path, e, candidate
                )
            else:
                logger.debug("Temp dir '%s' not usable (%s)", candidate, e)

    return FALLBACK_TEMP_DIR


def cleanup_temp_dir(path: Path) -> None:
    """Remove all files and subdirectories from temp directory.

    Creates the directory if it does not exist.

    Args:
        path: Temp directory path to clean
    """
    if path.exists():
        for item in path.iterdir():
            try:
                if item.is_file():
                    item.unlink()
                elif item.is_dir():
                    shutil.rmtree(item)
            except Exception as e:
                logger.warning("Failed to clean %s: %s", item, e)
    else:
        path.mkdir(parents=True, exist_ok=True)


def convert_audio_to_wav(input_path: Path, output_path: Path) -> bool:
    """Convert audio file to WAV format using ffmpeg.

    Args:
        input_path: Path to input audio file
        output_path: Path to output WAV file

    Returns:
        bool: True if conversion succeeded, False otherwise
    """
    try:
        subprocess.run(
            [
                "ffmpeg",
                "-i",
                str(input_path),
                "-ac",
                "1",
                "-ar",
                "16000",
                "-y",
                str(output_path),
            ],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=300,
        )
        logger.info(f"Successfully converted {input_path} to {output_path}")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to convert {input_path}: {e.stderr}")
        return False
    except subprocess.TimeoutExpired:
        logger.error(f"ffmpeg timed out converting {input_path}")
        return False
    except FileNotFoundError:
        logger.error("ffmpeg not found. Please install ffmpeg.")
        return False


def extract_audio_from_video(video_path: Path, audio_path: Path) -> bool:
    """Extract audio from video file using ffmpeg.

    Args:
        video_path: Path to input video file
        audio_path: Path to output audio file

    Returns:
        bool: True if extraction succeeded, False otherwise
    """
    try:
        subprocess.run(
            [
                "ffmpeg",
                "-i",
                str(video_path),
                "-vn",
                "-ac",
                "1",
                "-ar",
                "16000",
                "-y",
                str(audio_path),
            ],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=300,
        )
        logger.info(f"Successfully extracted audio from {video_path} to {audio_path}")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to extract audio from {video_path}: {e.stderr}")
        return False
    except subprocess.TimeoutExpired:
        logger.error(f"ffmpeg timed out extracting audio from {video_path}")
        return False
    except FileNotFoundError:
        logger.error("ffmpeg not found. Please install ffmpeg.")
        return False


def temp_filename(user_id: int, ext: str) -> str:
    """Generate unique temporary filename.

    Format: {user_id}_DDMMYY_HHMMSS_msec.{ext}

    Args:
        user_id: Telegram user ID
        ext: File extension including dot (e.g. '.mp3')

    Returns:
        str: Generated filename
    """
    now = datetime.now()
    return f"{user_id}_{now:%d%m%y_%H%M%S}_{now.microsecond // 1000:03d}{ext}"


def get_file_extension(file_path: Path) -> str | None:
    """Get file extension from path.

    Args:
        file_path: Path to file

    Returns:
        Optional[str]: File extension in lowercase, or None if no extension
    """
    suffix = file_path.suffix.lower()
    return suffix if suffix else None
