#!/usr/bin/env python3
"""Batch image compressor CLI — like Squoosh.app but in batch mode."""

import os
import sys
from pathlib import Path

import click
from PIL import Image
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, MofNCompleteColumn
from rich.table import Table
from send2trash import send2trash

console = Console()

ELIGIBLE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff", ".tif", ".webp"}
SKIP_DIRS = {"node_modules", ".git", "__pycache__", "dist", "build"}
LARGE_FILE_THRESHOLD = 50 * 1024 * 1024  # 50 MB


def is_hidden(path: Path) -> bool:
    """Check if any component of the path starts with a dot."""
    return any(part.startswith(".") for part in path.parts)


def scan_files(directory: Path, recursive: bool) -> list[Path]:
    """Walk directory and collect eligible image files."""
    files = []
    if recursive:
        for path in directory.rglob("*"):
            if path.is_symlink():
                continue
            if any(skip in path.parts for skip in SKIP_DIRS):
                continue
            if is_hidden(path.relative_to(directory)):
                continue
            if path.is_file() and path.suffix.lower() in ELIGIBLE_EXTENSIONS:
                files.append(path)
    else:
        for path in directory.iterdir():
            if path.is_symlink():
                continue
            if is_hidden(path.relative_to(directory)):
                continue
            if path.is_file() and path.suffix.lower() in ELIGIBLE_EXTENSIONS:
                files.append(path)
    return sorted(files)


def resize_image(img: Image.Image, max_width: int | None, max_height: int | None) -> Image.Image:
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


def is_animated(img: Image.Image) -> bool:
    """Check if image has multiple frames (animated GIF)."""
    try:
        return getattr(img, "n_frames", 1) > 1
    except Exception:
        return False


def convert_static(input_path: Path, output_path: Path, quality: int,
                   max_width: int | None, max_height: int | None) -> None:
    """Convert a static image to WebP."""
    img = Image.open(input_path)
    img.load()

    if max_width or max_height:
        img = resize_image(img, max_width, max_height)

    has_alpha = img.mode in ("RGBA", "PA", "LA")

    if not has_alpha and img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    elif img.mode == "PA":
        img = img.convert("RGBA")
    elif img.mode == "LA":
        img = img.convert("RGBA")

    save_kwargs = {"format": "webp", "quality": quality}
    if has_alpha:
        save_kwargs["lossless"] = False

    img.save(output_path, **save_kwargs)


def convert_animated_gif(input_path: Path, output_path: Path, quality: int,
                         max_width: int | None, max_height: int | None) -> None:
    """Convert an animated GIF to animated WebP."""
    img = Image.open(input_path)
    frames = []
    durations = []

    try:
        while True:
            frame = img.copy()
            if max_width or max_height:
                frame = resize_image(frame, max_width, max_height)
            if frame.mode == "P":
                frame = frame.convert("RGBA")
            elif frame.mode not in ("RGBA", "RGB"):
                frame = frame.convert("RGBA")
            frames.append(frame)
            durations.append(img.info.get("duration", 100))
            img.seek(img.tell() + 1)
    except EOFError:
        pass

    if frames:
        frames[0].save(
            output_path,
            format="webp",
            save_all=True,
            append_images=frames[1:],
            duration=durations,
            loop=img.info.get("loop", 0),
            quality=quality,
        )


def format_size(size_bytes: int) -> str:
    """Format bytes to human-readable size."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"


@click.command()
@click.argument("directory", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option("--quality", "-q", default=80, type=click.IntRange(1, 100),
              help="WebP quality (1-100, default 80)")
@click.option("--max-width", type=int, default=None,
              help="Max width in pixels (downscale only)")
@click.option("--max-height", type=int, default=None,
              help="Max height in pixels (downscale only)")
@click.option("--dry-run", is_flag=True, default=False,
              help="List files that would be processed without converting")
@click.option("--recursive/--no-recursive", default=True,
              help="Recurse into subdirectories (default: true)")
@click.option("--skip-existing", is_flag=True, default=False,
              help="Skip files that already have a .webp counterpart")
@click.option("--verbose", "-v", is_flag=True, default=False,
              help="Show per-file breakdown in report")
@click.option("--recompress", is_flag=True, default=False,
              help="Recompress existing .webp files")
@click.option("--delete-originals", is_flag=True, default=False,
              help="Send original files to recycle bin after successful conversion")
def main(directory: Path, quality: int, max_width: int | None, max_height: int | None,
         dry_run: bool, recursive: bool, skip_existing: bool, verbose: bool,
         recompress: bool, delete_originals: bool) -> None:
    """Batch compress images to WebP format.

    DIRECTORY is the path to scan for images.
    """
    directory = directory.resolve()
    console.print(f"\n[bold blue]Scanning[/bold blue] {directory}...\n")

    # --- Scan Phase ---
    files = scan_files(directory, recursive)

    # Filter out .webp unless --recompress
    if not recompress:
        files = [f for f in files if f.suffix.lower() != ".webp"]

    if not files:
        console.print("[yellow]No eligible images found.[/yellow]")
        sys.exit(0)

    # Count by extension
    ext_counts: dict[str, int] = {}
    total_size = 0
    for f in files:
        ext = f.suffix.lower()
        ext_counts[ext] = ext_counts.get(ext, 0) + 1
        total_size += f.stat().st_size

    ext_summary = "  |  ".join(f"{ext.upper().lstrip('.')}: {count}" for ext, count in sorted(ext_counts.items()))
    console.print(f"Found [bold green]{len(files)}[/bold green] eligible images ({format_size(total_size)} total)")
    console.print(f"  {ext_summary}\n")

    if dry_run:
        console.print("[yellow]Dry run — no files will be converted.[/yellow]\n")
        for f in files:
            console.print(f"  {f.relative_to(directory)}")
        console.print()
        sys.exit(0)

    # --- Processing Phase ---
    opts_parts = [f"quality={quality}"]
    if max_width:
        opts_parts.append(f"max_width={max_width}")
    if max_height:
        opts_parts.append(f"max_height={max_height}")
    console.print(f"[bold blue]Processing[/bold blue] with {', '.join(opts_parts)}\n")

    processed = 0
    skipped = 0
    failed = 0
    original_total = 0
    compressed_total = 0
    per_file_results: list[tuple[str, int, int, str]] = []
    seen_outputs: set[Path] = set()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        console=console,
    ) as progress:
        task = progress.add_task("Compressing", total=len(files))

        for file_path in files:
            progress.update(task, description=f"[cyan]{file_path.name}[/cyan]")
            output_path = file_path.with_suffix(".webp")

            # Collision detection
            if output_path in seen_outputs:
                console.print(f"  [yellow]WARN[/yellow] Output collision: {output_path.relative_to(directory)} — skipping {file_path.name}")
                skipped += 1
                progress.advance(task)
                continue
            seen_outputs.add(output_path)

            # Skip existing
            if skip_existing and output_path.exists() and file_path.suffix.lower() != ".webp":
                skipped += 1
                progress.advance(task)
                continue

            # Large file warning
            file_size = file_path.stat().st_size
            if file_size > LARGE_FILE_THRESHOLD:
                console.print(f"  [yellow]WARN[/yellow] Large file ({format_size(file_size)}): {file_path.relative_to(directory)}")

            try:
                img = Image.open(file_path)

                if is_animated(img):
                    convert_animated_gif(file_path, output_path, quality, max_width, max_height)
                else:
                    img.close()
                    convert_static(file_path, output_path, quality, max_width, max_height)

                original_size = file_size
                compressed_size = output_path.stat().st_size
                original_total += original_size
                compressed_total += compressed_size
                processed += 1

                rel = str(file_path.relative_to(directory))
                per_file_results.append((rel, original_size, compressed_size, "OK"))

            except PermissionError:
                console.print(f"  [red]ERROR[/red] Permission denied: {file_path.relative_to(directory)}")
                failed += 1
                per_file_results.append((str(file_path.relative_to(directory)), 0, 0, "Permission denied"))
            except Exception as e:
                console.print(f"  [red]ERROR[/red] {file_path.relative_to(directory)}: {e}")
                failed += 1
                per_file_results.append((str(file_path.relative_to(directory)), 0, 0, str(e)))

            progress.advance(task)

    # --- Report Phase ---
    console.print("\n[bold green]Done![/bold green]\n")

    table = Table(title="Compression Report", show_header=False, padding=(0, 2))
    table.add_column("Label", style="bold")
    table.add_column("Value")

    table.add_row("Processed", str(processed))
    if skipped:
        table.add_row("Skipped", f"{skipped} (already exist / collision)")
    else:
        table.add_row("Skipped", "0")
    table.add_row("Failed", str(failed))
    table.add_row("", "")
    table.add_row("Original size", format_size(original_total))
    table.add_row("Compressed size", format_size(compressed_total))

    if original_total > 0:
        saved = original_total - compressed_total
        pct = (saved / original_total) * 100
        table.add_row("Saved", f"{format_size(saved)} ({pct:.1f}%)")
    else:
        table.add_row("Saved", "0 B (0%)")

    console.print(table)

    if verbose and per_file_results:
        console.print()
        detail = Table(title="Per-File Breakdown")
        detail.add_column("File", style="cyan", no_wrap=True)
        detail.add_column("Original", justify="right")
        detail.add_column("Compressed", justify="right")
        detail.add_column("Saved", justify="right")
        detail.add_column("Status")

        for name, orig, comp, status in per_file_results:
            if status == "OK" and orig > 0:
                saved = orig - comp
                pct = (saved / orig) * 100
                detail.add_row(name, format_size(orig), format_size(comp), f"{pct:.1f}%", "[green]OK[/green]")
            else:
                detail.add_row(name, "-", "-", "-", f"[red]{status}[/red]")

        console.print(detail)

    # --- Delete Originals Phase ---
    if delete_originals and processed > 0:
        successful_files = [
            Path(directory / name) for name, orig, comp, status in per_file_results if status == "OK"
        ]
        console.print()
        console.print(f"[bold yellow]WARNING:[/bold yellow] This will send [bold]{len(successful_files)}[/bold] original files to the recycle bin.")
        console.print("[yellow]This action can be undone by restoring files from your recycle bin.[/yellow]\n")

        if click.confirm("Proceed with deleting originals?", default=False):
            deleted = 0
            delete_failed = 0
            for file_path in successful_files:
                try:
                    send2trash(file_path)
                    deleted += 1
                except Exception as e:
                    console.print(f"  [red]ERROR[/red] Could not delete {file_path.relative_to(directory)}: {e}")
                    delete_failed += 1
            console.print(f"\n[bold green]Deleted:[/bold green] {deleted} files sent to recycle bin")
            if delete_failed:
                console.print(f"[bold red]Failed to delete:[/bold red] {delete_failed} files")
        else:
            console.print("[cyan]Skipped — no files were deleted.[/cyan]")

    console.print()


if __name__ == "__main__":
    main()
