import base64
import gzip
import io
from pathlib import Path
import sys
import unittest
import zipfile


TOOLS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS_DIR))

from extract_fm3_inputs import MovieFormatError, extract_controller_bytes


def compact_movie(inputs: bytes, commands: bytes | None = None) -> bytes:
    if commands is None:
        commands = bytes(len(inputs))
    records = b"".join(
        bytes((command, value))
        for command, value in zip(commands, inputs, strict=True)
    )
    checksum = base64.b64encode(bytes.fromhex("11" * 16)).decode("ascii")
    header = (
        "version 3\n"
        "emuVersion 22000\n"
        "binary 1\n"
        f"length {len(inputs)}\n"
        "palFlag 0\n"
        "NewPPU 0\n"
        "FDS 0\n"
        "microphone 0\n"
        "fourscore 0\n"
        "port0 1\n"
        "port1 0\n"
        "port2 0\n"
        "romFilename test.nes\n"
        f"romChecksum base64:{checksum}\n"
        "comment author Testeur\n"
    ).encode("ascii")
    return header + b"|" + records + b"FM3 EXTRA DATA"


class ExtractFm3InputsTests(unittest.TestCase):
    def test_extracts_nested_tasvideos_container(self) -> None:
        movie = compact_movie(bytes((0x00, 0x01, 0x80, 0x18)))
        archive_buffer = io.BytesIO()
        with zipfile.ZipFile(
            archive_buffer, "w", compression=zipfile.ZIP_DEFLATED
        ) as archive:
            archive.writestr("movie.fm3", movie)

        inputs, metadata = extract_controller_bytes(
            gzip.compress(archive_buffer.getvalue())
        )

        self.assertEqual(inputs, bytes((0x00, 0x01, 0x80, 0x18)))
        self.assertEqual(metadata["frames"], 4)
        self.assertEqual(metadata["active_frames"], 3)
        self.assertEqual(metadata["rom_prg_md5"], "11" * 16)
        self.assertEqual(metadata["authors"], ["Testeur"])
        self.assertEqual(
            metadata["wrappers"], ["gzip", "zip:movie.fm3"]
        )

    def test_rejects_system_commands(self) -> None:
        movie = compact_movie(bytes((0, 0)), commands=bytes((0, 2)))
        with self.assertRaisesRegex(MovieFormatError, "commands.*frame"):
            extract_controller_bytes(movie)

    def test_rejects_truncated_log(self) -> None:
        movie = compact_movie(bytes((1, 2, 3)))[:-18]
        with self.assertRaisesRegex(MovieFormatError, "shorter"):
            extract_controller_bytes(movie)

    def test_pipe_in_comment_does_not_start_input_log(self) -> None:
        movie = compact_movie(bytes((0x01, 0x80))).replace(
            b"comment author Testeur\n",
            b"comment note gauche|droite\ncomment author Testeur\n",
        )
        inputs, metadata = extract_controller_bytes(movie)
        self.assertEqual(inputs, bytes((0x01, 0x80)))
        self.assertEqual(metadata["source_region"], "ntsc")
        self.assertTrue(metadata["starts_from_power_on"])

    def test_rejects_embedded_savestate_start(self) -> None:
        movie = compact_movie(bytes((0,))).replace(
            b"binary 1\n",
            b"savestate 0x001122\nbinary 1\n",
        )
        with self.assertRaisesRegex(MovieFormatError, "savestate"):
            extract_controller_bytes(movie)

    def test_rejects_non_md5_rom_checksum(self) -> None:
        movie = compact_movie(bytes((0,))).replace(
            base64.b64encode(bytes.fromhex("11" * 16)),
            base64.b64encode(b"not-an-md5"),
        )
        with self.assertRaisesRegex(MovieFormatError, "16-byte MD5"):
            extract_controller_bytes(movie)


if __name__ == "__main__":
    unittest.main()
