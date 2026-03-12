# Squoosher

Batch image compressor CLI — like Squoosh.app but in batch mode. Converts raster images to WebP format.

## Tech Stack

- Python 3.10+, single-file CLI (`squoosh.py`)
- **Pillow** — image processing
- **Click** — CLI argument parsing
- **Rich** — terminal output (progress bars, tables)
- **pytest** — testing (with `click.testing.CliRunner`)

## Project Structure

```
squoosh.py          # All logic: scan, convert, CLI entry point
test_squoosh.py     # 45 tests (unit + CLI integration)
pyproject.toml      # Package config, entry point: squoosher = squoosh:main
requirements.txt    # Pillow, click, rich
batch-squoosh-spec.md  # Original spec document
```

## Key Commands

```bash
# Run tests
python -m pytest test_squoosh.py -v

# Run the tool
python squoosh.py /path/to/images

# Install (editable)
pip install -e .
```

## Architecture

Single-file design for portability. Key functions:
- `scan_files()` — walks directory, filters by extension, skips hidden/excluded dirs
- `resize_image()` — downscale only, maintains aspect ratio (LANCZOS)
- `convert_static()` — static image → WebP (handles RGBA, PA, LA modes)
- `convert_animated_gif()` — animated GIF → animated WebP (frame-by-frame)
- `main()` — Click CLI entry point with scan → process → report phases

## Conventions

- Keep everything in `squoosh.py` (single file)
- Tests use `tmp_path` / `tmp_images` fixtures with in-memory PIL images
- CLI tests use `click.testing.CliRunner`
- Eligible extensions: .png, .jpg, .jpeg, .gif, .bmp, .tiff, .tif, .webp
- Skipped dirs: node_modules, .git, __pycache__, dist, build
