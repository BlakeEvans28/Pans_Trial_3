"""Build and optionally serve a pygbag web package for Pan's Trial."""

from __future__ import annotations

import argparse
import datetime as dt
import http.server
import importlib.util
import os
import shutil
import tarfile
import zipfile
from pathlib import Path


PROJECT_FILES = (
    "main.py",
    "deck_utils.py",
    "pan_theme.py",
)
PROJECT_DIRS = (
    "engine",
    "ui",
    "assets",
)
FRAMEBUFFER_WIDTH = 1200
FRAMEBUFFER_HEIGHT = 900
ZIP_NAME = "pans_trial_web.zip"
PYGAME_GUI_MINIMAL_DATA_FILES = (
    "data/__init__.py",
    "data/default_theme.json",
    "data/FiraCode-Regular.ttf",
    "data/NotoSans-Regular.ttf",
    "data/NotoSans-Bold.ttf",
    "data/NotoSans-Italic.ttf",
    "data/NotoSans-BoldItalic.ttf",
    "data/translations/__init__.py",
    "data/translations/pygame-gui.en.json",
)


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
        raise SystemExit(f"Required package '{package_name}' is not installed for this Python interpreter.")
    if spec.submodule_search_locations:
        return Path(next(iter(spec.submodule_search_locations))).resolve()
    if spec.origin is None:
        raise SystemExit(f"Unable to locate files for package '{package_name}'.")
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
        dst = pygame_gui_dst / relative_path
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

    i18n_root = resolve_package_root("i18n")
    copy_package_tree(i18n_root, staging_root / "i18n", "tests")


def stage_project(project_root: Path, staging_root: Path) -> None:
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

    copy_runtime_dependencies(staging_root)
    (staging_root / "BUILD_MODE.txt").write_text("web\n", encoding="utf-8")


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
    if favicon_src.exists():
        shutil.copy2(favicon_src, build_web_dir / "favicon.png")


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
    print("Audio note   : MP3 music is excluded from the web build.")
    print("Runtime note : Bundling pygame_gui + i18n into the archive for pygbag.")

    stage_project(project_root, staging_root)
    create_bundle_archives(staging_root, build_web_dir, staging_root.name)
    install_index_html(project_root, build_web_dir, staging_root.name)
    install_favicon(project_root, build_web_dir)
    create_zip(build_web_dir, output_zip)

    build_size_mb = output_zip.stat().st_size / 1024 / 1024
    print(f"Web zip      : {output_zip} ({build_size_mb:.1f} MB)")

    if not args.build_only:
        serve_build(build_web_dir, args.port)


if __name__ == "__main__":
    main()
