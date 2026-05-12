# Piano Transcription Lab MVP Technical Design

## 1. Goal

Build a local command-line prototype that converts a piano-focused MP3/WAV file into piano sheet music.

The first version does not need a frontend, user system, online deployment, or public API. The goal is to validate whether the transcription quality is good enough to continue.

Target output:

- `output.mid`: raw or cleaned MIDI.
- `output.musicxml`: editable score file.
- `output.pdf`: rendered piano score.
- Optional `output.png`: preview image.

## 2. MVP Scope

### In Scope

- Local repo and Python scripts.
- Input: one MP3/WAV file.
- Primary use case: solo piano or mostly clean piano recording.
- Optional source separation when the input is not pure piano.
- Audio-to-MIDI transcription.
- Basic MIDI cleanup.
- MusicXML export.
- PDF rendering through MuseScore CLI.
- Small test set for quality checks.

### Out of Scope

- Web UI.
- Batch processing.
- User accounts.
- Cloud storage.
- Online job queue.
- Perfect transcription for any mixed song.
- Automatic full-song piano arrangement from vocals, drums, bass, and harmony.
- Manual score editor.

## 3. Recommended Pipeline

```text
input.mp3 / input.wav
  -> normalize audio
  -> optional piano source separation
  -> audio-to-MIDI transcription
  -> MIDI cleanup
  -> score conversion
  -> MuseScore rendering
  -> output.mid / output.musicxml / output.pdf
```

### Step 1: Audio Normalize

Use `ffmpeg` to convert any input file to a stable WAV format.

Recommended output:

- WAV
- 44.1 kHz or 16 kHz, depending on transcription model requirements
- stereo preserved unless the model prefers mono
- normalized loudness

Example future command:

```bash
ffmpeg -y -i input.mp3 -ar 44100 -ac 2 work/input.wav
```

### Step 2: Optional Piano Source Separation

Use this only when the input is not clean piano.

Candidate tool:

- `demucs`

MVP behavior:

- Default mode: skip separation.
- `--separate` mode: run Demucs and use the piano stem if available.
- Always keep both versions so we can compare:
  - transcription from original audio
  - transcription from separated piano audio

Reason:

Source separation can help with mixed songs, but it can also introduce artifacts. It should be treated as an experiment, not as a guaranteed improvement.

### Step 3: Audio to MIDI

Primary model:

- `piano_transcription_inference`

Backup / comparison model:

- `basic-pitch`

MVP recommendation:

- Start with `piano_transcription_inference` because the product is piano-focused.
- Keep the code boundary clean so we can swap in `basic-pitch` later.
- Use `--model piano-transcription-inference` for the built-in adapter.
- Keep `--transcriber-command` as a fallback for ad-hoc model experiments.
- Save raw model output before cleanup.

Artifact:

```text
work/raw.mid
```

### Step 4: MIDI Cleanup

This is the most important MVP quality layer.

Use:

- `pretty_midi` or `miditoolkit` for low-level MIDI edits.
- `music21` for notation-aware processing and MusicXML export.

Initial cleanup rules:

| Rule | Purpose |
| --- | --- |
| Remove very short notes | Reduce ghost notes and noise |
| Merge repeated same-pitch notes close together | Reduce fragmented notes |
| Drop very low-velocity notes | Reduce uncertain model output |
| Quantize note starts and durations | Make the score readable |
| Limit minimum note value | Avoid unreadable 64th-note clutter |
| Optional pitch range filter | Remove impossible or noisy notes |

Recommended first thresholds:

- Minimum duration: `60-90 ms`
- Minimum velocity: start with `10-20`, tune per model
- Minimum note value: `1/16` for simple mode, `1/32` for detailed mode

Artifact:

```text
work/clean.mid
```

### Step 5: Score Conversion

Use `music21` to load the cleaned MIDI and export MusicXML.

MVP notation rules:

- Create one piano score.
- Use treble and bass staves.
- First version can split hands by pitch around middle C.
- Later version should split hands with a smarter algorithm using pitch, time overlap, and hand movement.
- Start with fixed or estimated tempo.
- Avoid over-optimizing key signature and time signature in the first version.

Artifact:

```text
output/output.musicxml
```

### Step 6: Render PDF

Use MuseScore CLI in headless mode.

Artifact:

```text
output/output.pdf
```

Example future command:

```bash
mscore -o output/output.pdf output/output.musicxml
```

The actual executable may be `mscore`, `musescore`, or the MuseScore app binary path depending on the machine.

## 4. Proposed Repo Structure

```text
piano-transcription-lab/
  doc/
    MVP_TECH_DESIGN.md
  samples/
    input/
    expected/
  src/
    piano_transcription_lab/
      __init__.py
      cli.py
      audio.py
      separation.py
      transcription.py
      midi_cleanup.py
      score_export.py
      render.py
  scripts/
    transcribe_one.sh
  work/
    .gitkeep
  output/
    .gitkeep
  pyproject.toml
  README.md
```

`work/` and `output/` should be ignored by git except for `.gitkeep`.

## 5. CLI Shape

First CLI command:

```bash
python -m piano_transcription_lab.cli transcribe samples/input/song.mp3
```

Useful options:

```bash
--separate              # run Demucs before transcription
--model piano           # piano_transcription_inference
--model basic-pitch     # comparison path
--min-note 1/16         # score simplification
--keep-work             # keep intermediate files
--out output/song       # output prefix
```

Expected result:

```text
output/song.raw.mid
output/song.clean.mid
output/song.musicxml
output/song.pdf
```

## 6. Main Technical Risks

| Risk | Impact | MVP Handling |
| --- | --- | --- |
| Mixed audio is not clean enough | MIDI becomes noisy | Start with cleaner piano samples; add optional Demucs |
| MIDI is technically correct but score is unreadable | PDF is not useful | Invest early in cleanup and quantization |
| Left/right hand split is poor | Piano score feels wrong | Use simple split first, then improve |
| Pedal and reverb create long overlapping notes | Score becomes cluttered | Shorten or simplify sustained notes |
| Tempo and beat detection are unstable | Rhythm notation looks strange | Allow fixed tempo override later |
| Model dependency is hard to install | Prototype slows down | Isolate model adapter behind one interface |

## 7. Validation Plan

Use a small fixed test set:

| Sample | Purpose |
| --- | --- |
| Simple clean piano melody | Check basic pitch and rhythm |
| Piano with chords | Check polyphonic transcription |
| Fast arpeggio | Check timing and note density |
| Pedal-heavy piano | Check sustain cleanup |
| Mostly piano but with light backing | Check optional separation |
| Non-piano mixed track | Confirm failure mode is understandable |

For each sample, record:

- Whether MIDI sounds close to the input.
- Whether PDF is readable.
- Whether left/right hand split is acceptable.
- Whether there are too many ghost notes.
- Whether a human could clean the result in less than 10 minutes.

MVP success threshold:

> For clean piano input, the generated PDF should be good enough as a first draft for human editing.

## 8. Implementation Phases

### Phase 1: Local Smoke Test

Build the smallest script:

```text
input audio -> raw MIDI -> MusicXML -> PDF
```

Do not optimize quality yet. Confirm that all tools can run locally.

### Phase 2: Cleanup Layer

Add MIDI cleanup:

- short note filtering
- velocity filtering
- quantization
- repeated note merge
- minimum note value option

Compare before/after MIDI and PDF.

### Phase 3: Optional Separation

Add `--separate`.

Compare:

- original audio transcription
- separated piano transcription

Keep this optional because it may hurt clean piano recordings.

### Phase 4: Better Piano Notation

Improve:

- hand splitting
- tempo handling
- key signature estimation
- time signature assumptions
- simplified mode vs detailed mode

## 9. First Build Recommendation

Start with this order:

1. Create Python project skeleton.
2. Install and test MuseScore CLI.
3. Install and test one transcription model.
4. Convert one clean piano MP3 to raw MIDI.
5. Export raw MIDI to MusicXML and PDF.
6. Add cleanup rules only after the first full pipeline works.

The first milestone should be a single command that produces a PDF from one local piano file, even if the score is rough.
