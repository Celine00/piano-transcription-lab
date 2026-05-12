from pathlib import Path


def separate_audio(source: Path, work_dir: Path, config) -> Path:
    if not config.separate:
        return source
    raise NotImplementedError(
        "Demucs separation is intentionally optional in the MVP skeleton. "
        "Run without --separate first, then add a Demucs adapter after the base pipeline works."
    )

