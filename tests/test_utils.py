"""Tests for utility functions."""

import os
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.utils import (
    FALLBACK_TEMP_DIR,
    cleanup_temp_dir,
    convert_audio_to_wav,
    ensure_temp_dir,
    extract_audio_from_video,
    get_file_extension,
    get_system_temp_dir,
    temp_filename,
)


class TestGetSystemTempDir:
    """Tests for get_system_temp_dir."""

    def test_uses_temp_env_var(self):
        with patch.dict(os.environ, {"TEMP": r"C:\Temp"}, clear=True):
            result = get_system_temp_dir()
        assert result == Path(r"C:\Temp") / "whispbot"

    def test_uses_tmp_when_temp_not_set(self):
        with patch.dict(os.environ, {"TMP": r"/var/tmp"}, clear=True):
            result = get_system_temp_dir()
        assert result == Path("/var/tmp") / "whispbot"

    def test_uses_tmpdir_when_others_not_set(self):
        with patch.dict(os.environ, {"TMPDIR": "/custom/tmp"}, clear=True):
            result = get_system_temp_dir()
        assert result == Path("/custom/tmp") / "whispbot"

    def test_uses_unix_tmp_when_no_env_vars(self):
        with patch.dict(os.environ, {}, clear=True):
            with patch("pathlib.Path.exists", return_value=True):
                result = get_system_temp_dir()
        assert result == Path("/tmp") / "whispbot"

    def test_returns_none_when_no_temp_available(self):
        with patch.dict(os.environ, {}, clear=True):
            with patch("pathlib.Path.exists", return_value=False):
                result = get_system_temp_dir()
        assert result is None


class TestEnsureTempDir:
    """Tests for ensure_temp_dir."""

    @patch("src.utils.get_system_temp_dir", return_value=None)
    @patch("pathlib.Path.mkdir")
    @patch("pathlib.Path.write_text")
    @patch("pathlib.Path.unlink")
    def test_returns_given_path_when_writable(
        self, mock_unlink, mock_write, mock_mkdir, mock_get_sys_temp
    ):
        path = Path("/tmp/whispbot")
        result = ensure_temp_dir(path)
        assert result == path
        mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)

    @patch("src.utils.get_system_temp_dir", return_value=None)
    @patch("pathlib.Path.mkdir", side_effect=[PermissionError, None])
    @patch("pathlib.Path.write_text")
    @patch("pathlib.Path.unlink")
    def test_falls_back_when_configured_dir_fails(
        self, mock_unlink, mock_write, mock_mkdir, mock_get_sys_temp
    ):
        path = Path("/tmp/whispbot")
        result = ensure_temp_dir(path)
        assert result == FALLBACK_TEMP_DIR

    @patch("src.utils.get_system_temp_dir", return_value=Path("/sys/tmp/whispbot"))
    @patch("pathlib.Path.mkdir", side_effect=[PermissionError, None, None])
    @patch("pathlib.Path.write_text")
    @patch("pathlib.Path.unlink")
    def test_uses_system_temp_as_intermediate_fallback(
        self, mock_unlink, mock_write, mock_mkdir, mock_get_sys_temp
    ):
        path = Path("/tmp/whispbot")
        result = ensure_temp_dir(path)
        assert result == Path("/sys/tmp/whispbot")


class TestCleanupTempDir:
    """Tests for cleanup_temp_dir."""

    def test_removes_files(self):
        mock_file = MagicMock(spec=Path)
        mock_file.is_file.return_value = True
        mock_file.is_dir.return_value = False

        mock_path = MagicMock(spec=Path)
        mock_path.exists.return_value = True
        mock_path.iterdir.return_value = [mock_file]

        cleanup_temp_dir(mock_path)
        mock_file.unlink.assert_called_once_with()

    def test_removes_subdirectories(self):
        mock_dir = MagicMock(spec=Path)
        mock_dir.is_file.return_value = False
        mock_dir.is_dir.return_value = True

        mock_path = MagicMock(spec=Path)
        mock_path.exists.return_value = True
        mock_path.iterdir.return_value = [mock_dir]

        with patch("shutil.rmtree") as mock_rmtree:
            cleanup_temp_dir(mock_path)
        mock_rmtree.assert_called_once_with(mock_dir)

    def test_creates_dir_if_not_exists(self):
        mock_path = MagicMock(spec=Path)
        mock_path.exists.return_value = False

        cleanup_temp_dir(mock_path)
        mock_path.mkdir.assert_called_once_with(parents=True, exist_ok=True)


class TestConvertAudioToWav:
    """Tests for convert_audio_to_wav."""

    @patch("subprocess.run")
    def test_success(self, mock_run):
        result = convert_audio_to_wav(Path("in.mp3"), Path("out.wav"))
        assert result is True
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert "ffmpeg" in args
        assert "-ac" in args
        assert "1" in args

    @patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "ffmpeg", stderr="error"))
    def test_ffmpeg_error_returns_false(self, mock_run):
        result = convert_audio_to_wav(Path("in.mp3"), Path("out.wav"))
        assert result is False

    @patch("subprocess.run", side_effect=FileNotFoundError)
    def test_ffmpeg_not_found_returns_false(self, mock_run):
        result = convert_audio_to_wav(Path("in.mp3"), Path("out.wav"))
        assert result is False

    @patch("subprocess.run", side_effect=subprocess.TimeoutExpired("ffmpeg", 300))
    def test_timeout_returns_false(self, mock_run):
        result = convert_audio_to_wav(Path("in.mp3"), Path("out.wav"))
        assert result is False


class TestExtractAudioFromVideo:
    """Tests for extract_audio_from_video."""

    @patch("subprocess.run")
    def test_success(self, mock_run):
        result = extract_audio_from_video(Path("in.mp4"), Path("out.wav"))
        assert result is True
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert "ffmpeg" in args
        assert "-vn" in args

    @patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "ffmpeg", stderr="error"))
    def test_ffmpeg_error_returns_false(self, mock_run):
        result = extract_audio_from_video(Path("in.mp4"), Path("out.wav"))
        assert result is False

    @patch("subprocess.run", side_effect=FileNotFoundError)
    def test_ffmpeg_not_found_returns_false(self, mock_run):
        result = extract_audio_from_video(Path("in.mp4"), Path("out.wav"))
        assert result is False

    @patch("subprocess.run", side_effect=subprocess.TimeoutExpired("ffmpeg", 300))
    def test_timeout_returns_false(self, mock_run):
        result = extract_audio_from_video(Path("in.mp4"), Path("out.wav"))
        assert result is False


class TestTempFilename:
    """Tests for temp_filename."""

    def test_format(self):
        result = temp_filename(12345, ".mp3")
        assert result.startswith("12345_")
        assert result.endswith(".mp3")
        parts = result.split("_")
        assert len(parts) == 4  # user_id_DDMMYY_HHMMSS_mmm.ext


class TestGetFileExtension:
    """Tests for get_file_extension."""

    def test_returns_extension(self):
        assert get_file_extension(Path("test.mp3")) == ".mp3"

    def test_returns_lowercase(self):
        assert get_file_extension(Path("test.MP3")) == ".mp3"

    def test_returns_none_when_no_extension(self):
        assert get_file_extension(Path("file")) is None

    def test_returns_none_for_dotfile(self):
        assert get_file_extension(Path(".gitignore")) is None
