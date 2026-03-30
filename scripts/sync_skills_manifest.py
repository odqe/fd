import argparse
import pathlib
import sys

import yaml


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync xixu-me/skills entries in skvlt.yaml from a checked-out skills directory.")
    parser.add_argument("--manifest", required=True, type=pathlib.Path, help="Path to skvlt.yaml")
    parser.add_argument("--skills-root", required=True, type=pathlib.Path, help="Path to the upstream skills/ directory")
    parser.add_argument("--source-key", default="xixu-me/skills", help="Manifest source key to update")
    return parser.parse_args()


def collect_skill_slugs(skills_root: pathlib.Path) -> list[str]:
    if not skills_root.exists():
        raise FileNotFoundError(f"Skills root does not exist: {skills_root}")
    return sorted(entry.name for entry in skills_root.iterdir() if entry.is_dir())


def render_manifest(manifest_data: dict) -> str:
    lines = [
        "# Generated for project-scoped restoration with Skills Vault.",
        f'total_sources: {manifest_data["total_sources"]}',
        f'total_skills: {manifest_data["total_skills"]}',
        f'scope: "{manifest_data["scope"]}"',
        "",
        "sources:",
    ]

    for source_name, source_data in manifest_data["sources"].items():
        lines.append(f'  "{source_name}":')
        lines.append(f'    count: {source_data["count"]}')
        lines.append("    skills:")
        for skill in source_data["skills"]:
            lines.append(f'      - "{skill}"')
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    args = parse_args()
    manifest_data = yaml.safe_load(args.manifest.read_text(encoding="utf-8"))

    if not isinstance(manifest_data, dict) or "sources" not in manifest_data:
        raise ValueError("Manifest is missing a top-level 'sources' mapping")

    sources = manifest_data["sources"]
    if args.source_key not in sources:
        raise KeyError(f"Manifest source '{args.source_key}' is missing")

    skill_slugs = collect_skill_slugs(args.skills_root)
    sources[args.source_key]["count"] = len(skill_slugs)
    sources[args.source_key]["skills"] = skill_slugs

    manifest_data["total_sources"] = len(sources)
    manifest_data["total_skills"] = sum(int(source.get("count", 0)) for source in sources.values())

    args.manifest.write_text(render_manifest(manifest_data), encoding="utf-8")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001 - CLI should emit a readable error and non-zero exit.
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc
