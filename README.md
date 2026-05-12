# Piano Transcription Lab

Local CLI prototype for converting piano-focused audio into editable music files and rendered sheet music.

This repo is intentionally local-first. There is no frontend, hosted API, user system, or queue. The first goal is to validate whether the transcription quality is good enough to keep building.

## Current MVP

The implemented skeleton provides:

- A `piano-transcribe` CLI.
- A pipeline for `audio -> raw MIDI -> clean MIDI -> MusicXML -> PDF`.
- Optional use of an existing MIDI file to test the downstream score/export path.
- Tested MIDI cleanup primitives.
- Lazy integration points for external tools.

External runtime tools are still required for a real audio-to-score run:

- `ffmpeg` for audio normalization.
- An audio-to-MIDI backend, passed through `--transcriber-command`.
- `music21` for MusicXML export.
- MuseScore CLI for PDF rendering.

## Setup

```bash
python -m pip install -e ".[dev]"
```

For runtime score export:

```bash
python -m pip install -e ".[runtime]"
```

For the built-in piano transcription backend:

```bash
python -m pip install -e ".[piano,runtime]"
```

`piano-transcription-inference` also needs PyTorch and `ffmpeg`. Install PyTorch for your machine first if the package does not bring in a compatible version.

## Test

```bash
pytest -q
```

## Run With Existing MIDI

This validates the cleanup/export/rendering half of the pipeline.

```bash
piano-transcribe transcribe samples/input/song.mp3 \
  --existing-midi samples/expected/song.mid \
  --out output/song \
  --work-dir work/song
```

## Run With A Transcriber Command

Pass any audio-to-MIDI command that accepts an audio input path and a MIDI output path.

```bash
piano-transcribe transcribe samples/input/song.mp3 \
  --transcriber-command "your-transcriber --audio {audio} --midi {midi}" \
  --out output/song \
  --work-dir work/song
```

The placeholders are:

- `{audio}`: normalized WAV path.
- `{midi}`: raw MIDI output path.

## Run With Built-In Piano Backend

This uses `piano_transcription_inference` directly.

```bash
piano-transcribe transcribe samples/input/song.mp3 \
  --model piano-transcription-inference \
  --device cpu \
  --out output/song \
  --work-dir work/song
```

To use a local checkpoint:

```bash
piano-transcribe transcribe samples/input/song.mp3 \
  --model piano-transcription-inference \
  --checkpoint-path path/to/checkpoint.pth \
  --out output/song
```

The backend follows the package API:

```python
from piano_transcription_inference import PianoTranscription, sample_rate
```

The audio is loaded at the package `sample_rate`, then `PianoTranscription(...).transcribe(audio, midi_path)` writes the MIDI file.

## Output

For `--out output/song`, expected artifacts are:

```text
output/song.raw.mid
output/song.clean.mid
output/song.musicxml
output/song.pdf
```

When using `--existing-midi`, the pipeline skips raw audio transcription and starts from the provided MIDI.

## Docs

- [MVP technical design](doc/MVP_TECH_DESIGN.md)
- [Implementation plan](docs/superpowers/plans/2026-05-12-mvp-cli.md)
