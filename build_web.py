"""Build and optionally serve a pygbag web package for Pan's Trial."""

from __future__ import annotations

import argparse
import datetime as dt
import http.server
import io
import importlib.util
import math
import os
import random
import shutil
import tarfile
import urllib.request
import wave
import zipfile
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    Image = None


PROJECT_FILES = (
    "main.py",
    "deck_utils.py",
    "pan_theme.py",
)
PROJECT_DIRS = (
    "engine",
    "multiplayer",
    "ui",
)
FRAMEBUFFER_WIDTH = 1200
FRAMEBUFFER_HEIGHT = 900
ZIP_NAME = "pans_trial_web.zip"
DEPENDENCY_INSTALL_HINT = "Install web build dependencies with: python -m pip install -r requirements-web.txt"
WEB_AUDIO_FILES = (
    "Pan_Intro_Updated.mp3",
    "Pan_Intro.mp3",
    "PanPhase1_Updated.mp3",
    "PanPhase1.mp3",
)
WEB_CLASH_FILENAME = "clash.wav"
WEB_ASSET_FILES = (
    "appeasing_pan.png",
    "Ballista.png",
    "banner.png",
    "labrynth.png",
    "MedievalSharp.ttf",
    "p1.png",
    "p2.png",
    "PanTitle.png",
    "Pan_Background.png",
    "Pan_Icon.png",
    "player_portrait_micah.png",
    "stone.png",
    "Stone_Wall.jpg",
    "tarot_ballista.png",
    "tarot_trap.png",
    "tarot_wall.png",
    "tarot_weapons.png",
    "Trap.png",
    "traversing.png",
    "victory.png",
    *tuple(f"cards/Weapon{value:02}.png" for value in range(1, 13)),
)
WEB_JPEG_ASSET_FILES = {
    "PanTitle.png",
    "Pan_Background.png",
    "tarot_ballista.png",
    "tarot_trap.png",
    "tarot_wall.png",
    "tarot_weapons.png",
}
WEB_IMAGE_LONGEST_EDGE_CAPS = {
    "appeasing_pan.png": 1024,
    "Ballista.png": 512,
    "banner.png": 768,
    "labrynth.png": 900,
    "p1.png": 640,
    "p2.png": 640,
    "Pan_Icon.png": 1024,
    "player_portrait_micah.png": 256,
    "stone.png": 1024,
    "Stone_Wall.jpg": 512,
    "tarot_ballista.png": 768,
    "tarot_trap.png": 768,
    "tarot_wall.png": 768,
    "tarot_weapons.png": 768,
    "Trap.png": 512,
    "traversing.png": 1024,
    "victory.png": 768,
    **{f"cards/Weapon{value:02}.png": 384 for value in range(1, 13)},
}
PYGAME_GUI_MINIMAL_DATA_FILES = (
    "data/__init__.py",
    "data/default_theme.json",
    "data/FiraCode-Bold.ttf",
    "data/FiraCode-Regular.ttf",
    "data/FiraMono-BoldItalic.ttf",
    "data/FiraMono-RegularItalic.ttf",
    "data/NotoSansJP-Bold.otf",
    "data/NotoSansJP-Regular.otf",
    "data/NotoSansSC-Bold.otf",
    "data/NotoSansSC-Regular.otf",
    "data/NotoSans-Regular.ttf",
    "data/NotoSans-Bold.ttf",
    "data/NotoSans-Italic.ttf",
    "data/NotoSans-BoldItalic.ttf",
    "data/translations/__init__.py",
    "data/translations/pygame-gui.en.json",
)
FAVICON_MAX_SIZE = 128
PYGBAG_CDN_CACHE_DIRNAME = ".pygbag_cdn_cache"
PYGBAG_LOCAL_CDN_FILES = {
    "cdn/cp312/pygame_ce-2.5.7-cp312-cp312-wasm32_bi_emscripten.whl": (
        "https://pygame-web.github.io/cdn/cp312/"
        "pygame_ce-2.5.7-cp312-cp312-wasm32_bi_emscripten.whl"
    ),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the Pan's Trial web version with pygbag.")
    parser.add_argument("--port", type=int, default=8000, help="Port to use when serving the build.")
    parser.add_argument(
        "--build-only",
        action="store_true",
        help="Build the web package without starting a local HTTP server.",
    )
    return parser.parse_args()


def resolve_package_root(package_name: str) -> Path:
    spec = importlib.util.find_spec(package_name)
    if spec is None:
        raise SystemExit(
            f"Required package '{package_name}' is not installed for this Python interpreter.\n"
            f"{DEPENDENCY_INSTALL_HINT}"
        )
    if spec.submodule_search_locations:
        return Path(next(iter(spec.submodule_search_locations))).resolve()
    if spec.origin is None:
        raise SystemExit(f"Unable to locate files for package '{package_name}'.\n{DEPENDENCY_INSTALL_HINT}")
    return Path(spec.origin).resolve().parent


def copy_package_tree(
    source_root: Path,
    destination_root: Path,
    *extra_ignored_names: str,
) -> None:
    shutil.copytree(
        source_root,
        destination_root,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo", *extra_ignored_names),
    )


def copy_runtime_dependencies(staging_root: Path) -> None:
    pygame_gui_root = resolve_package_root("pygame_gui")
    pygame_gui_dst = staging_root / "pygame_gui"
    copy_package_tree(pygame_gui_root, pygame_gui_dst, "data", "__pyinstaller")
    for relative_path in PYGAME_GUI_MINIMAL_DATA_FILES:
        src = pygame_gui_root / relative_path
        if not src.exists():
            continue
        dst = pygame_gui_dst / relative_path
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

    i18n_root = resolve_package_root("i18n")
    copy_package_tree(i18n_root, staging_root / "i18n", "tests")


def _get_resample_filter():
    if Image is None:
        return None
    if hasattr(Image, "Resampling"):
        return Image.Resampling.LANCZOS
    return Image.LANCZOS


def get_web_output_relative_path(relative_path: str) -> str:
    if relative_path in WEB_JPEG_ASSET_FILES:
        return str(Path(relative_path).with_suffix(".jpg")).replace("\\", "/")
    return relative_path


def copy_web_asset(source_root: Path, destination_root: Path, relative_path: str) -> tuple[int, int]:
    source_path = source_root / relative_path
    if not source_path.exists():
        raise SystemExit(f"Required web asset is missing: {source_path}")

    destination_relative_path = get_web_output_relative_path(relative_path)
    destination_path = destination_root / destination_relative_path
    destination_path.parent.mkdir(parents=True, exist_ok=True)

    original_size = source_path.stat().st_size
    suffix = source_path.suffix.lower()
    if Image is None or suffix not in {".png", ".jpg", ".jpeg"}:
        shutil.copy2(source_path, destination_path)
        return original_size, destination_path.stat().st_size

    resample_filter = _get_resample_filter()
    with Image.open(source_path) as image:
        max_edge = WEB_IMAGE_LONGEST_EDGE_CAPS.get(relative_path)
        if max_edge is not None and max(image.size) > max_edge:
            scale = max_edge / max(image.size)
            resized_size = (
                max(1, int(round(image.width * scale))),
                max(1, int(round(image.height * scale))),
            )
            image = image.resize(resized_size, resample_filter)

        if destination_path.suffix.lower() == ".png":
            image.save(destination_path, format="PNG", optimize=True, compress_level=9)
        else:
            image = image.convert("RGB")
            image.save(destination_path, format="JPEG", optimize=True, progressive=True, quality=90)

    return original_size, destination_path.stat().st_size


def copy_web_assets(project_root: Path, staging_root: Path) -> tuple[int, int]:
    source_root = project_root / "assets"
    destination_root = staging_root / "assets"
    original_total = 0
    staged_total = 0

    for relative_path in WEB_ASSET_FILES:
        original_size, staged_size = copy_web_asset(source_root, destination_root, relative_path)
        original_total += original_size
        staged_total += staged_size

    return original_total, staged_total


def _generate_clash_samples(sample_rate: int = 44100) -> list[int]:
    """Return the generated clash sound as signed 16-bit PCM samples."""
    rng = random.Random(27)
    total = int(sample_rate * 0.45)
    samples: list[int] = []
    for i in range(total):
        t = i / sample_rate
        envelope = math.exp(-t * 7.5)
        ring = (
            math.sin(2 * math.pi * 1450 * t)
            + 0.55 * math.sin(2 * math.pi * 2320 * t)
            + 0.35 * math.sin(2 * math.pi * 3170 * t)
        )
        hit_noise = rng.uniform(-1.0, 1.0) * math.exp(-t * 22)
        sample = int(max(-32767, min(32767, (0.25 * ring + 0.75 * hit_noise) * envelope * 0.7 * 32767)))
        samples.append(sample)
    return samples


def _build_clash_wav_bytes() -> bytes:
    """Generate the browser clash effect as a small WAV file."""
    with io.BytesIO() as buffer:
        with wave.open(buffer, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(44100)
            pcm = bytearray()
            for sample in _generate_clash_samples():
                pcm.extend(int(sample).to_bytes(2, byteorder="little", signed=True))
            wav_file.writeframes(bytes(pcm))
        return buffer.getvalue()


def install_browser_audio(project_root: Path, build_web_dir: Path) -> int:
    """Copy browser-played audio beside the web bundle for direct HTML5 playback."""
    source_root = project_root / "audio"
    destination_root = build_web_dir / "audio"
    destination_root.mkdir(parents=True, exist_ok=True)

    total_bytes = 0
    for filename in WEB_AUDIO_FILES:
        source_path = source_root / filename
        if not source_path.exists():
            raise SystemExit(f"Required browser audio file is missing: {source_path}")
        destination_path = destination_root / filename
        shutil.copy2(source_path, destination_path)
        total_bytes += destination_path.stat().st_size

    clash_path = destination_root / WEB_CLASH_FILENAME
    clash_path.write_bytes(_build_clash_wav_bytes())
    total_bytes += clash_path.stat().st_size
    return total_bytes


def stage_project(project_root: Path, staging_root: Path) -> tuple[int, int]:
    if staging_root.exists():
        shutil.rmtree(staging_root)
    staging_root.mkdir(parents=True)

    for filename in PROJECT_FILES:
        shutil.copy2(project_root / filename, staging_root / filename)

    for directory in PROJECT_DIRS:
        shutil.copytree(
            project_root / directory,
            staging_root / directory,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
        )

    original_asset_bytes, staged_asset_bytes = copy_web_assets(project_root, staging_root)
    copy_runtime_dependencies(staging_root)
    (staging_root / "BUILD_MODE.txt").write_text("web\n", encoding="utf-8")
    return original_asset_bytes, staged_asset_bytes


def iter_staging_files(staging_root: Path):
    build_root = staging_root / "build"
    for file_path in sorted(staging_root.rglob("*")):
        if not file_path.is_file():
            continue
        if build_root in file_path.parents:
            continue
        yield file_path


def create_bundle_archives(staging_root: Path, build_web_dir: Path, bundle_name: str) -> None:
    build_web_dir.mkdir(parents=True, exist_ok=True)
    apk_path = build_web_dir / f"{bundle_name}.apk"
    tar_path = build_web_dir / f"{bundle_name}.tar.gz"

    if apk_path.exists():
        apk_path.unlink()
    if tar_path.exists():
        tar_path.unlink()

    with zipfile.ZipFile(apk_path, "w", compression=zipfile.ZIP_DEFLATED) as apk_archive:
        for file_path in iter_staging_files(staging_root):
            arcname = (Path("assets") / file_path.relative_to(staging_root)).as_posix()
            apk_archive.write(file_path, arcname=arcname)

    with tarfile.open(tar_path, "w:gz") as tar_archive:
        for file_path in iter_staging_files(staging_root):
            arcname = (Path("assets") / file_path.relative_to(staging_root)).as_posix()
            tar_archive.add(file_path, arcname=arcname, recursive=False)


def _download_cached_file(url: str, cache_path: Path) -> Path:
    """Cache remote pygbag runtime files so local web testing works without pygbag's dev server."""
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    if cache_path.exists():
        return cache_path

    try:
        with urllib.request.urlopen(url) as response, cache_path.open("wb") as destination:
            shutil.copyfileobj(response, destination)
    except Exception as exc:
        raise SystemExit(f"Failed to download required pygbag runtime file: {url}\n{exc}") from exc

    return cache_path


def install_local_pygbag_cdn(project_root: Path, build_web_dir: Path) -> int:
    """Mirror the minimal localhost /cdn files pygbag expects during local development."""
    cache_root = project_root / "WEB_BUILD" / PYGBAG_CDN_CACHE_DIRNAME
    total_bytes = 0

    for relative_path, url in PYGBAG_LOCAL_CDN_FILES.items():
        cached_file = _download_cached_file(url, cache_root / relative_path)
        destination_path = build_web_dir / relative_path
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(cached_file, destination_path)
        total_bytes += destination_path.stat().st_size

    return total_bytes


def install_index_html(project_root: Path, build_web_dir: Path, bundle_name: str) -> None:
    template_path = project_root / "WEB_BUILD" / "index_template.html"
    html = template_path.read_text(encoding="utf-8")
    replacements = {
        "__BUNDLE__": bundle_name,
        "__TITLE__": "Pan's Trial",
        "__WIDTH__": str(FRAMEBUFFER_WIDTH),
        "__HEIGHT__": str(FRAMEBUFFER_HEIGHT),
        "__ASPECT__": f"{FRAMEBUFFER_WIDTH / FRAMEBUFFER_HEIGHT:.12g}",
        "__BUILD_VERSION__": dt.datetime.now().strftime("%Y%m%d%H%M"),
    }
    for old, new in replacements.items():
        html = html.replace(old, new)
    (build_web_dir / "index.html").write_text(html, encoding="utf-8")


def install_favicon(project_root: Path, build_web_dir: Path) -> None:
    favicon_src = project_root / "assets" / "Pan_Icon.png"
    favicon_dst = build_web_dir / "favicon.png"
    if not favicon_src.exists():
        return
    if Image is None:
        shutil.copy2(favicon_src, favicon_dst)
        return

    resample_filter = _get_resample_filter()
    with Image.open(favicon_src) as image:
        image.thumbnail((FAVICON_MAX_SIZE, FAVICON_MAX_SIZE), resample_filter)
        image.save(favicon_dst, format="PNG", optimize=True, compress_level=9)


def create_zip(build_web_dir: Path, output_zip: Path) -> None:
    output_zip.parent.mkdir(parents=True, exist_ok=True)
    if output_zip.exists():
        output_zip.unlink()

    with zipfile.ZipFile(output_zip, "w", compression=zipfile.ZIP_STORED) as archive:
        for file_path in sorted(build_web_dir.rglob("*")):
            if file_path.is_file():
                archive.write(file_path, arcname=file_path.relative_to(build_web_dir))


def serve_build(build_web_dir: Path, port: int) -> None:
    print(f"Serving on http://localhost:{port}")
    print("Press Ctrl+C to stop.")
    os.chdir(build_web_dir)
    server = http.server.HTTPServer(("", port), http.server.SimpleHTTPRequestHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")


def main() -> None:
    args = parse_args()

    project_root = Path(__file__).resolve().parent
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    staging_root = project_root / "build" / f"pans_trial_web_{stamp}"
    build_web_dir = staging_root / "build" / "web"
    output_zip = project_root / "WEB_BUILD" / ZIP_NAME

    print("=" * 52)
    print("Building Pan's Trial for the web")
    print("=" * 52)
    print(f"Project root : {project_root}")
    print(f"Staging root : {staging_root}")
    print("Audio note   : Serving browser audio beside the bundle for HTML5 playback.")
    print("Runtime note : Bundling pygame_gui + i18n into the archive for pygbag.")
    if Image is None:
        print("Asset note   : Pillow not found, so web art will be copied without image optimization.")
        print(f"              {DEPENDENCY_INSTALL_HINT}")

    original_asset_bytes, staged_asset_bytes = stage_project(project_root, staging_root)
    create_bundle_archives(staging_root, build_web_dir, staging_root.name)
    install_index_html(project_root, build_web_dir, staging_root.name)
    install_favicon(project_root, build_web_dir)
    browser_audio_bytes = install_browser_audio(project_root, build_web_dir)
    local_cdn_bytes = install_local_pygbag_cdn(project_root, build_web_dir)
    create_zip(build_web_dir, output_zip)

    original_asset_mb = original_asset_bytes / 1024 / 1024
    staged_asset_mb = staged_asset_bytes / 1024 / 1024
    saved_asset_mb = original_asset_mb - staged_asset_mb
    build_size_mb = output_zip.stat().st_size / 1024 / 1024
    print(f"Web assets   : {staged_asset_mb:.1f} MB (saved {saved_asset_mb:.1f} MB from {original_asset_mb:.1f} MB)")
    print(f"Browser audio: {browser_audio_bytes / 1024 / 1024:.1f} MB")
    print(f"Local CDN    : {local_cdn_bytes / 1024 / 1024:.1f} MB (for localhost pygbag dependency loading)")
    print(f"Web zip      : {output_zip} ({build_size_mb:.1f} MB)")

    if not args.build_only:
        serve_build(build_web_dir, args.port)


if __name__ == "__main__":
    main()
