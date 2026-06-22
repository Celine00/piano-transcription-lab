import subprocess

from piano_transcription_lab.render import render_pdf


class Config:
    musescore = "mscore"


def test_render_pdf_accepts_musescore_crash_after_valid_pdf_write(tmp_path):
    source = tmp_path / "score.musicxml"
    target = tmp_path / "score.pdf"
    source.write_text("<score-partwise />")

    def run(command, check):
        target.write_bytes(b"%PDF-1.4\ncontent")
        raise subprocess.CalledProcessError(returncode=-6, cmd=command)

    render_pdf(source, target, Config(), run_command=run)

    assert target.read_bytes().startswith(b"%PDF-")


def test_render_pdf_raises_when_musescore_fails_without_valid_pdf(tmp_path):
    source = tmp_path / "score.musicxml"
    target = tmp_path / "score.pdf"
    source.write_text("<score-partwise />")

    def run(command, check):
        target.write_text("not a pdf")
        raise subprocess.CalledProcessError(returncode=-6, cmd=command)

    try:
        render_pdf(source, target, Config(), run_command=run)
    except subprocess.CalledProcessError:
        pass
    else:
        raise AssertionError("Expected CalledProcessError")
