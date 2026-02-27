# Batch Image Compressor CLI — Project Spec

## Overview

A Python CLI tool that works like Squoosh.app but in batch mode. It scans a project folder recursively for raster images, compresses them to WebP format (including animated GIF → animated WebP), and saves the output alongside the original file with the same name but `.webp` extension.

---

## Tech Stack

- **Python 3.10+**
- **Pillow (PIL)** — core image processing
- **Click** — CLI argument parsing
- **Rich** — terminal progress bars and formatted output
- **pathlib** — filesystem traversal

Install: `pip install Pillow click rich`

---

## CLI Interface

```bash
# Basic usage — compress all images in folder to WebP at quality 80
python squoosh.py /path/to/project

# Custom quality (1-100, default 80)
python squoosh.py /path/to/project --quality 80

# Optional max resize (maintains aspect ratio)
python squoosh.py /path/to/project --max-width 1920 --max-height 1080

# Dry run — list files that would be processed without converting
python squoosh.py /path/to/project --dry-run

# Recursive (default: true), disable with flag
python squoosh.py /path/to/project --no-recursive

# Skip files that already have a .webp counterpart
python squoosh.py /path/to/project --skip-existing
```

---

## Eligible File Types

### Include (raster images only):
- `.png`
- `.jpg` / `.jpeg`
- `.gif` (including animated)
- `.bmp`
- `.tiff` / `.tif`
- `.webp` (recompress if quality differs — optional)

### Exclude:
- `.svg`
- `.eps`
- `.ai`
- `.pdf`
- Any file that fails to open as a raster image via Pillow

---

## Core Logic

### 1. Scan Phase
- Walk the target directory (recursively by default)
- Collect all files matching eligible extensions (case-insensitive)
- Skip hidden files/folders (prefixed with `.`)
- Skip `node_modules`, `.git`, `__pycache__`, `dist`, `build` folders
- Report total files found and estimated size

### 2. Processing Phase
For each eligible file:

```
original:  /project/assets/hero-banner.png
output:    /project/assets/hero-banner.webp
```

#### Static Images (PNG, JPG, BMP, TIFF):
1. Open with `Pillow`
2. If `--max-width` or `--max-height` is set, resize using `Image.LANCZOS` while maintaining aspect ratio (only downscale, never upscale)
3. Convert to RGB if necessary (handle RGBA → keep alpha for WebP)
4. Save as `.webp` with specified quality
5. For PNG/images with transparency: use `lossless=False` with alpha preserved

#### Animated GIFs:
1. Open with Pillow, detect `n_frames > 1`
2. Extract all frames and durations
3. If resize flags are set, resize each frame
4. Save as animated `.webp` using `save_all=True`, passing `append_images`, `duration`, `loop`
5. Preserve loop count from original GIF

### 3. Report Phase
After processing, print a summary table:
- Files processed / skipped / failed
- Total original size vs total compressed size
- Compression ratio (% saved)
- Per-file breakdown (optional with `--verbose`)

---

## File Structure

```
batch-squoosh/
├── squoosh.py          # Main CLI entry point + all logic (single file for simplicity)
├── requirements.txt    # Pillow, click, rich
└── README.md           # Usage instructions
```

Keep it as a **single file** (`squoosh.py`) for portability. No need for a package structure.

---

## Key Implementation Details

### Animated GIF → Animated WebP

```python
def convert_animated_gif(input_path, output_path, quality, max_width, max_height):
    img = Image.open(input_path)
    frames = []
    durations = []
    
    try:
        while True:
            frame = img.copy()
            if max_width or max_height:
                frame = resize_image(frame, max_width, max_height)
            # Convert palette mode to RGBA for WebP compatibility
            if frame.mode == 'P':
                frame = frame.convert('RGBA')
            frames.append(frame)
            durations.append(img.info.get('duration', 100))
            img.seek(img.tell() + 1)
    except EOFError:
        pass
    
    if frames:
        frames[0].save(
            output_path,
            format='webp',
            save_all=True,
            append_images=frames[1:],
            duration=durations,
            loop=img.info.get('loop', 0),
            quality=quality
        )
```

### Resize Logic

```python
def resize_image(img, max_width=None, max_height=None):
    """Downscale only, maintain aspect ratio."""
    w, h = img.size
    ratio = 1.0
    
    if max_width and w > max_width:
        ratio = min(ratio, max_width / w)
    if max_height and h > max_height:
        ratio = min(ratio, max_height / h)
    
    if ratio < 1.0:
        new_size = (int(w * ratio), int(h * ratio))
        return img.resize(new_size, Image.LANCZOS)
    return img
```

### Transparency Handling

- PNG with alpha → WebP with alpha (no conversion to RGB)
- JPEG (no alpha) → WebP RGB
- GIF with transparency → WebP RGBA
- Use `img.mode` to detect: if `RGBA` or `PA`, preserve alpha channel

---

## Edge Cases to Handle

1. **File permissions**: Skip and warn if file can't be read/written
2. **Corrupted images**: Wrap in try/except, log error, continue batch
3. **Duplicate output**: If `hero.png` and `hero.jpg` both exist in same folder, both would write `hero.webp` — detect this collision and warn/skip the second one
4. **Very large files**: No special handling needed, Pillow streams. But warn if a single file is > 50MB
5. **Already WebP**: Skip by default, or recompress with `--recompress` flag
6. **Symlinks**: Don't follow symlinks by default

---

## Example Output

```
🔍 Scanning /home/user/project...

Found 47 eligible images (12.4 MB total)
  PNG: 23  |  JPG: 18  |  GIF: 4  |  BMP: 2

⚙️  Processing with quality=80, max_width=1920

 [████████████████████████████████] 47/47 — 100%

✅ Done!

┌──────────────────────────────────────┐
│          Compression Report          │
├──────────────────────────────────────┤
│ Processed:    45                     │
│ Skipped:       2 (already exist)     │
│ Failed:        0                     │
│                                      │
│ Original size:   12.4 MB             │
│ Compressed size:  3.8 MB             │
│ Saved:            8.6 MB (69.4%)     │
└──────────────────────────────────────┘
```

---

## Optional Future Enhancements (not in v1)

- [ ] AVIF output format support
- [ ] Config file (`.squooshrc`) for per-project defaults
- [ ] Watch mode — auto-compress new images added to folder
- [ ] Web UI with Flask/Streamlit
- [ ] Parallel processing with `concurrent.futures` for large batches
- [ ] `--output-dir` flag to save WebP files to a separate folder
- [ ] `--delete-originals` flag (dangerous, requires confirmation)
- [ ] EXIF data preservation/stripping options
