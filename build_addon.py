from __future__ import annotations

import argparse
import shutil
import zipfile
from pathlib import Path


EXCLUDED_DIRS = {"__pycache__", ".git", "build"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".db", ".sqlite", ".sqlite3", ".log", ".tmp"}


def read_manifest(project_dir: Path) -> dict[str, str]:
	values = {}
	for line in (project_dir / "manifest.ini.tpl").read_text(encoding="utf-8").splitlines():
		line = line.strip()
		if not line or line.startswith("#") or "=" not in line:
			continue
		key, value = line.split("=", 1)
		values[key.strip()] = value.strip()
	return values


def build(project_dir: Path, output_dir: Path) -> Path:
	manifest = read_manifest(project_dir)
	addon_name = manifest["name"]
	version = manifest["version"]
	build_root = output_dir / "staging"
	package_path = output_dir / f"{addon_name}-{version}.nvda-addon"
	if build_root.exists():
		shutil.rmtree(build_root)
	output_dir.mkdir(parents=True, exist_ok=True)
	shutil.copytree(
		project_dir / "addon",
		build_root,
		ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo", "*.db", "*.sqlite", "*.sqlite3", "*.log", "*.tmp"),
	)
	shutil.copy2(project_dir / "manifest.ini.tpl", build_root / "manifest.ini")
	if package_path.exists():
		package_path.unlink()
	with zipfile.ZipFile(package_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
		for path in build_root.rglob("*"):
			if path.is_file() and _should_include(path, build_root):
				archive.write(path, path.relative_to(build_root).as_posix())
	shutil.rmtree(build_root)
	return package_path


def _should_include(path: Path, root: Path) -> bool:
	relative = path.relative_to(root)
	if any(part in EXCLUDED_DIRS for part in relative.parts):
		return False
	if path.suffix.lower() in EXCLUDED_SUFFIXES:
		return False
	return True


def main() -> None:
	parser = argparse.ArgumentParser(description="Construir paquete .nvda-addon simple.")
	parser.add_argument("--project-dir", default=".")
	parser.add_argument("--output-dir", default="build")
	args = parser.parse_args()
	package_path = build(Path(args.project_dir).resolve(), Path(args.output_dir).resolve())
	print(package_path)


if __name__ == "__main__":
	main()
