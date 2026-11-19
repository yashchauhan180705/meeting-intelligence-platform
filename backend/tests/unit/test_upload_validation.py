"""Unit tests for upload validation — T022.

Tests MIME type allowlist, size limit, zero-length, and speaker count validation.
"""

from app.lib.upload_validation import (
    validate_file_extension,
    validate_file_size,
    validate_speaker_count,
)


class TestFileExtensionValidation:
    """Extension allowlist tests."""

    def test_wav_accepted(self):
        assert validate_file_extension("recording.wav") is None

    def test_mp3_accepted(self):
        assert validate_file_extension("song.mp3") is None

    def test_m4a_accepted(self):
        assert validate_file_extension("audio.m4a") is None

    def test_webm_accepted(self):
        assert validate_file_extension("recording.webm") is None

    def test_ogg_accepted(self):
        assert validate_file_extension("audio.ogg") is None

    def test_txt_rejected(self):
        err = validate_file_extension("notes.txt")
        assert err is not None
        assert err.code == "UNSUPPORTED_FORMAT"

    def test_exe_rejected(self):
        err = validate_file_extension("malware.exe")
        assert err is not None
        assert err.code == "UNSUPPORTED_FORMAT"

    def test_pdf_rejected(self):
        err = validate_file_extension("document.pdf")
        assert err is not None
        assert err.code == "UNSUPPORTED_FORMAT"

    def test_no_extension_rejected(self):
        err = validate_file_extension("noextension")
        assert err is not None
        assert err.code == "UNSUPPORTED_FORMAT"

    def test_empty_filename_rejected(self):
        err = validate_file_extension("")
        assert err is not None
        assert err.code == "UNSUPPORTED_FORMAT"

    def test_case_insensitive(self):
        assert validate_file_extension("recording.WAV") is None
        assert validate_file_extension("audio.Mp3") is None


class TestFileSizeValidation:
    """Size limit tests."""

    MAX = 26214400  # 25 MiB

    def test_valid_size(self):
        assert validate_file_size(1024, self.MAX) is None

    def test_at_limit(self):
        assert validate_file_size(self.MAX, self.MAX) is None

    def test_over_limit(self):
        err = validate_file_size(self.MAX + 1, self.MAX)
        assert err is not None
        assert err.code == "FILE_TOO_LARGE"

    def test_zero_length_rejected(self):
        err = validate_file_size(0, self.MAX)
        assert err is not None
        assert err.code == "EMPTY_FILE"

    def test_negative_size_rejected(self):
        err = validate_file_size(-1, self.MAX)
        assert err is not None
        assert err.code == "EMPTY_FILE"


class TestSpeakerCountValidation:
    """Speaker count hint tests."""

    def test_none_accepted(self):
        assert validate_speaker_count(None) is None

    def test_one_accepted(self):
        assert validate_speaker_count(1) is None

    def test_ten_accepted(self):
        assert validate_speaker_count(10) is None

    def test_five_accepted(self):
        assert validate_speaker_count(5) is None

    def test_zero_rejected(self):
        err = validate_speaker_count(0)
        assert err is not None
        assert err.code == "VALIDATION_ERROR"

    def test_eleven_rejected(self):
        err = validate_speaker_count(11)
        assert err is not None
        assert err.code == "VALIDATION_ERROR"

    def test_negative_rejected(self):
        err = validate_speaker_count(-1)
        assert err is not None
        assert err.code == "VALIDATION_ERROR"
