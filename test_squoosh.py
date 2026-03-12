"""Tests for squoosh.py batch image compressor."""

import os
import shutil
from pathlib import Path

import pytest
from click.testing import CliRunner
from PIL import Image

from squoosh import (
    convert_animated_gif,
    convert_static,
    format_size,
    is_animated,
    is_hidden,
    main,
    resize_image,
    scan_files,
    upscale_image,
)


@pytest.fixture
def tmp_images(tmp_path):
    """Create a temporary directory with various test images."""
    # RGB JPEG
    Image.new("RGB", (200, 150), (255, 0, 0)).save(tmp_path / "photo.jpg")
    # RGBA PNG (with transparency)
    Image.new("RGBA", (100, 100), (0, 255, 0, 128)).save(tmp_path / "icon.png")
    # BMP
    Image.new("RGB", (80, 60), (0, 0, 255)).save(tmp_path / "legacy.bmp")
    # Animated GIF (3 frames) — use RGB and convert so frames are distinct
    gif_frames = []
    for color in [(255, 0, 0), (0, 255, 0), (0, 0, 255)]:
        f = Image.new("RGB", (50, 50), color)
        f = f.quantize(colors=256)
        gif_frames.append(f)
    gif_frames[0].save(
        tmp_path / "anim.gif",
        save_all=True,
        append_images=gif_frames[1:],
        duration=100,
        loop=0,
    )
    return tmp_path


@pytest.fixture
def runner():
    return CliRunner()


# ---------- is_hidden ----------

class TestIsHidden:
    def test_hidden_file(self):
        assert is_hidden(Path(".secret"))

    def test_hidden_nested(self):
        assert is_hidden(Path("foo/.hidden/bar.png"))

    def test_not_hidden(self):
        assert not is_hidden(Path("foo/bar/image.png"))

    def test_dotfile_extension_not_hidden(self):
        assert not is_hidden(Path("image.png"))


# ---------- scan_files ----------

class TestScanFiles:
    def test_finds_eligible_files(self, tmp_images):
        files = scan_files(tmp_images, recursive=True)
        names = {f.name for f in files}
        assert names == {"photo.jpg", "icon.png", "legacy.bmp", "anim.gif"}

    def test_skips_hidden_files(self, tmp_images):
        Image.new("RGB", (10, 10), (0, 0, 0)).save(tmp_images / ".hidden.png")
        files = scan_files(tmp_images, recursive=True)
        assert not any(f.name == ".hidden.png" for f in files)

    def test_skips_excluded_dirs(self, tmp_images):
        nm = tmp_images / "node_modules"
        nm.mkdir()
        Image.new("RGB", (10, 10), (0, 0, 0)).save(nm / "dep.png")
        files = scan_files(tmp_images, recursive=True)
        assert not any("node_modules" in str(f) for f in files)

    def test_non_recursive(self, tmp_images):
        sub = tmp_images / "sub"
        sub.mkdir()
        Image.new("RGB", (10, 10), (0, 0, 0)).save(sub / "nested.png")
        files = scan_files(tmp_images, recursive=False)
        assert not any(f.name == "nested.png" for f in files)

    def test_recursive(self, tmp_images):
        sub = tmp_images / "sub"
        sub.mkdir()
        Image.new("RGB", (10, 10), (0, 0, 0)).save(sub / "nested.png")
        files = scan_files(tmp_images, recursive=True)
        assert any(f.name == "nested.png" for f in files)

    def test_ignores_non_image_files(self, tmp_images):
        (tmp_images / "readme.txt").write_text("hello")
        (tmp_images / "style.css").write_text("body {}")
        files = scan_files(tmp_images, recursive=True)
        names = {f.name for f in files}
        assert "readme.txt" not in names
        assert "style.css" not in names

    def test_case_insensitive_extensions(self, tmp_images):
        Image.new("RGB", (10, 10), (0, 0, 0)).save(tmp_images / "upper.PNG")
        files = scan_files(tmp_images, recursive=True)
        assert any(f.name == "upper.PNG" for f in files)

    def test_returns_sorted(self, tmp_images):
        files = scan_files(tmp_images, recursive=True)
        assert files == sorted(files)


# ---------- resize_image ----------

class TestResizeImage:
    def test_downscale_width(self):
        img = Image.new("RGB", (400, 200))
        result = resize_image(img, max_width=200, max_height=None)
        assert result.size == (200, 100)

    def test_downscale_height(self):
        img = Image.new("RGB", (400, 200))
        result = resize_image(img, max_width=None, max_height=100)
        assert result.size == (200, 100)

    def test_no_upscale(self):
        img = Image.new("RGB", (100, 50))
        result = resize_image(img, max_width=200, max_height=200)
        assert result.size == (100, 50)

    def test_both_constraints(self):
        img = Image.new("RGB", (1000, 800))
        result = resize_image(img, max_width=500, max_height=300)
        w, h = result.size
        assert w <= 500
        assert h <= 300

    def test_no_constraints(self):
        img = Image.new("RGB", (300, 200))
        result = resize_image(img, max_width=None, max_height=None)
        assert result.size == (300, 200)

    def test_exact_match_no_resize(self):
        img = Image.new("RGB", (100, 100))
        result = resize_image(img, max_width=100, max_height=100)
        assert result.size == (100, 100)


# ---------- upscale_image ----------

class TestUpscaleImage:
    def test_scale_2x(self):
        img = Image.new("RGB", (100, 50))
        result = upscale_image(img, scale=2.0, target_width=None)
        assert result.size == (200, 100)

    def test_scale_4x(self):
        img = Image.new("RGB", (100, 50))
        result = upscale_image(img, scale=4.0, target_width=None)
        assert result.size == (400, 200)

    def test_target_width(self):
        img = Image.new("RGB", (100, 50))
        result = upscale_image(img, scale=None, target_width=300)
        assert result.size == (300, 150)

    def test_target_width_downscale(self):
        img = Image.new("RGB", (400, 200))
        result = upscale_image(img, scale=None, target_width=200)
        assert result.size == (200, 100)

    def test_no_args_returns_original(self):
        img = Image.new("RGB", (100, 50))
        result = upscale_image(img, scale=None, target_width=None)
        assert result.size == (100, 50)

    def test_bicubic_resample(self):
        img = Image.new("RGB", (100, 50))
        result = upscale_image(img, scale=2.0, target_width=None, resample=Image.BICUBIC)
        assert result.size == (200, 100)

    def test_bilinear_resample(self):
        img = Image.new("RGB", (100, 50))
        result = upscale_image(img, scale=2.0, target_width=None, resample=Image.BILINEAR)
        assert result.size == (200, 100)


# ---------- is_animated ----------

class TestIsAnimated:
    def test_static_image(self):
        img = Image.new("RGB", (10, 10))
        assert not is_animated(img)

    def test_animated_gif(self, tmp_images):
        img = Image.open(tmp_images / "anim.gif")
        assert is_animated(img)
        img.close()


# ---------- convert_static ----------

class TestConvertStatic:
    def test_jpg_to_webp(self, tmp_images):
        out = tmp_images / "photo.webp"
        convert_static(tmp_images / "photo.jpg", out, quality=80, max_width=None, max_height=None)
        assert out.exists()
        img = Image.open(out)
        assert img.format == "WEBP"
        img.close()

    def test_png_rgba_preserves_alpha(self, tmp_images):
        out = tmp_images / "icon.webp"
        convert_static(tmp_images / "icon.png", out, quality=80, max_width=None, max_height=None)
        img = Image.open(out)
        assert img.mode == "RGBA"
        img.close()

    def test_bmp_to_webp(self, tmp_images):
        out = tmp_images / "legacy.webp"
        convert_static(tmp_images / "legacy.bmp", out, quality=80, max_width=None, max_height=None)
        assert out.exists()

    def test_with_resize(self, tmp_images):
        out = tmp_images / "photo_resized.webp"
        convert_static(tmp_images / "photo.jpg", out, quality=80, max_width=100, max_height=None)
        img = Image.open(out)
        assert img.size[0] <= 100
        img.close()

    def test_palette_mode_converts(self, tmp_images):
        p_img = Image.new("P", (50, 50))
        p_path = tmp_images / "palette.png"
        p_img.save(p_path)
        out = tmp_images / "palette.webp"
        convert_static(p_path, out, quality=80, max_width=None, max_height=None)
        assert out.exists()

    def test_la_mode_converts(self, tmp_images):
        la_img = Image.new("LA", (50, 50))
        la_path = tmp_images / "la_image.png"
        la_img.save(la_path)
        out = tmp_images / "la_image.webp"
        convert_static(la_path, out, quality=80, max_width=None, max_height=None)
        img = Image.open(out)
        assert img.mode == "RGBA"
        img.close()


# ---------- convert_animated_gif ----------

class TestConvertAnimatedGif:
    def test_creates_animated_webp(self, tmp_images):
        out = tmp_images / "anim.webp"
        convert_animated_gif(tmp_images / "anim.gif", out, quality=80, max_width=None, max_height=None)
        assert out.exists()
        img = Image.open(out)
        assert img.n_frames == 3
        img.close()

    def test_animated_with_resize(self, tmp_images):
        out = tmp_images / "anim_small.webp"
        convert_animated_gif(tmp_images / "anim.gif", out, quality=80, max_width=25, max_height=None)
        img = Image.open(out)
        assert img.size[0] <= 25
        img.close()


# ---------- format_size ----------

class TestFormatSize:
    def test_bytes(self):
        assert format_size(500) == "500 B"

    def test_kilobytes(self):
        assert format_size(2048) == "2.0 KB"

    def test_megabytes(self):
        assert format_size(5 * 1024 * 1024) == "5.0 MB"

    def test_gigabytes(self):
        assert format_size(2 * 1024 * 1024 * 1024) == "2.0 GB"

    def test_zero(self):
        assert format_size(0) == "0 B"


# ---------- CLI integration ----------

class TestCLI:
    def test_basic_run(self, tmp_images, runner):
        result = runner.invoke(main, [str(tmp_images)])
        assert result.exit_code == 0
        assert "Done!" in result.output
        assert "Processed" in result.output

    def test_dry_run_no_files_created(self, tmp_images, runner):
        result = runner.invoke(main, [str(tmp_images), "--dry-run"])
        assert result.exit_code == 0
        assert "Dry run" in result.output
        assert not (tmp_images / "photo.webp").exists()

    def test_skip_existing(self, tmp_images, runner):
        # First run creates .webp files
        runner.invoke(main, [str(tmp_images)])
        # Second run with --skip-existing should skip all
        result = runner.invoke(main, [str(tmp_images), "--skip-existing"])
        assert result.exit_code == 0
        assert "Skipped" in result.output

    def test_custom_quality(self, tmp_images, runner):
        result = runner.invoke(main, [str(tmp_images), "--quality", "50"])
        assert result.exit_code == 0

    def test_verbose_output(self, tmp_images, runner):
        result = runner.invoke(main, [str(tmp_images), "--verbose"])
        assert result.exit_code == 0
        assert "Per-File Breakdown" in result.output

    def test_no_recursive(self, tmp_images, runner):
        sub = tmp_images / "sub"
        sub.mkdir()
        Image.new("RGB", (10, 10), (0, 0, 0)).save(sub / "nested.png")
        result = runner.invoke(main, [str(tmp_images), "--no-recursive"])
        assert result.exit_code == 0
        assert not (sub / "nested.webp").exists()

    def test_max_width_resize(self, tmp_images, runner):
        # Create a large image
        Image.new("RGB", (2000, 1000), (100, 100, 100)).save(tmp_images / "big.jpg")
        result = runner.invoke(main, [str(tmp_images), "--max-width", "500"])
        assert result.exit_code == 0
        img = Image.open(tmp_images / "big.webp")
        assert img.size[0] <= 500
        img.close()

    def test_invalid_directory(self, runner):
        result = runner.invoke(main, ["/nonexistent/path"])
        assert result.exit_code != 0

    def test_empty_directory(self, tmp_path, runner):
        result = runner.invoke(main, [str(tmp_path)])
        assert result.exit_code == 0
        assert "No eligible images found" in result.output

    def test_output_collision(self, tmp_images, runner):
        # Create hero.png and hero.jpg in same folder — both map to hero.webp
        Image.new("RGB", (10, 10), (0, 0, 0)).save(tmp_images / "hero.png")
        Image.new("RGB", (10, 10), (0, 0, 0)).save(tmp_images / "hero.jpg")
        result = runner.invoke(main, [str(tmp_images)])
        assert result.exit_code == 0
        assert "collision" in result.output.lower() or "Skipped" in result.output

    def test_webp_skipped_by_default(self, tmp_images, runner):
        Image.new("RGB", (10, 10), (0, 0, 0)).save(tmp_images / "existing.webp", format="webp")
        result = runner.invoke(main, [str(tmp_images)])
        assert result.exit_code == 0
        # The .webp file should not be listed as processed separately

    def test_recompress_flag(self, tmp_images, runner):
        webp_path = tmp_images / "recomp.webp"
        Image.new("RGB", (10, 10), (0, 0, 0)).save(webp_path, format="webp")
        result = runner.invoke(main, [str(tmp_images), "--recompress"])
        assert result.exit_code == 0

    def test_delete_originals_confirmed(self, tmp_images, runner, monkeypatch):
        # Patch send2trash to just delete the file (no real recycle bin in tests)
        import squoosh
        deleted_files = []
        monkeypatch.setattr(squoosh, "send2trash", lambda p: (deleted_files.append(p), p.unlink() if hasattr(p, 'unlink') else os.unlink(p)))
        result = runner.invoke(main, [str(tmp_images), "--delete-originals"], input="y\n")
        assert result.exit_code == 0
        assert "WARNING" in result.output
        assert "recycle bin" in result.output.lower()
        assert len(deleted_files) > 0
        # Originals should be gone, webp files should remain
        assert not (tmp_images / "photo.jpg").exists()
        assert (tmp_images / "photo.webp").exists()

    def test_delete_originals_declined(self, tmp_images, runner):
        result = runner.invoke(main, [str(tmp_images), "--delete-originals"], input="n\n")
        assert result.exit_code == 0
        assert "no files were deleted" in result.output.lower()
        # Originals should still exist
        assert (tmp_images / "photo.jpg").exists()

    def test_delete_originals_without_flag(self, tmp_images, runner):
        result = runner.invoke(main, [str(tmp_images)])
        assert result.exit_code == 0
        # Originals should still exist
        assert (tmp_images / "photo.jpg").exists()
        assert "WARNING" not in result.output

    def test_delete_originals_dry_run(self, tmp_images, runner):
        result = runner.invoke(main, [str(tmp_images), "--delete-originals", "--dry-run"])
        assert result.exit_code == 0
        # Dry run exits before processing, no deletion prompt
        assert (tmp_images / "photo.jpg").exists()

    def test_scale_2x(self, tmp_images, runner):
        Image.new("RGB", (100, 50), (0, 0, 0)).save(tmp_images / "small.jpg")
        result = runner.invoke(main, [str(tmp_images), "--scale", "2x"])
        assert result.exit_code == 0
        img = Image.open(tmp_images / "small.webp")
        assert img.size == (200, 100)
        img.close()

    def test_scale_4x(self, tmp_images, runner):
        Image.new("RGB", (50, 25), (0, 0, 0)).save(tmp_images / "tiny.jpg")
        result = runner.invoke(main, [str(tmp_images), "--scale", "4x"])
        assert result.exit_code == 0
        img = Image.open(tmp_images / "tiny.webp")
        assert img.size == (200, 100)
        img.close()

    def test_target_width(self, tmp_images, runner):
        Image.new("RGB", (100, 50), (0, 0, 0)).save(tmp_images / "tw.jpg")
        result = runner.invoke(main, [str(tmp_images), "--target-width", "400"])
        assert result.exit_code == 0
        img = Image.open(tmp_images / "tw.webp")
        assert img.size == (400, 200)
        img.close()

    def test_scale_and_max_width_conflict(self, tmp_images, runner):
        result = runner.invoke(main, [str(tmp_images), "--scale", "2x", "--max-width", "100"])
        assert result.exit_code != 0

    def test_scale_and_target_width_conflict(self, tmp_images, runner):
        result = runner.invoke(main, [str(tmp_images), "--scale", "2x", "--target-width", "100"])
        assert result.exit_code != 0

    def test_resample_bicubic(self, tmp_images, runner):
        result = runner.invoke(main, [str(tmp_images), "--resample", "bicubic"])
        assert result.exit_code == 0

    def test_scale_shows_in_opts(self, tmp_images, runner):
        result = runner.invoke(main, [str(tmp_images), "--scale", "2x"])
        assert "scale=2x" in result.output

    def test_resample_shows_in_opts(self, tmp_images, runner):
        result = runner.invoke(main, [str(tmp_images), "--resample", "bicubic"])
        assert "resample=bicubic" in result.output
