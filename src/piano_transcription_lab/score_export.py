from pathlib import Path
import shutil


def export_musicxml(source: Path, target: Path, config) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        from music21 import converter
    except ImportError as exc:
        raise RuntimeError("music21 is required to export MusicXML. Install the runtime extras.") from exc

    score = converter.parse(str(source))
    score.write("musicxml", fp=str(target))


def copy_midi_as_placeholder(source: Path, target: Path, config) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)

