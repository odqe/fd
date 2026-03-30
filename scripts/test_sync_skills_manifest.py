import pathlib
import subprocess
import sys
import tempfile
import textwrap

import yaml


ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "sync_skills_manifest.py"


def run_sync(manifest_path: pathlib.Path, skills_root: pathlib.Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--manifest",
            str(manifest_path),
            "--skills-root",
            str(skills_root),
        ],
        text=True,
        capture_output=True,
        check=False,
    )


def test_updates_only_target_source_and_sorts_skills() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = pathlib.Path(temp_dir)
        manifest_path = temp_path / "skvlt.yaml"
        skills_root = temp_path / "skills"

        manifest_path.write_text(
            textwrap.dedent(
                """
                total_sources: 3
                total_skills: 8
                scope: "project"

                sources:
                  "xixu-me/xdrop":
                    count: 1
                    skills:
                      - "xdrop"

                  "xixu-me/xget":
                    count: 1
                    skills:
                      - "xget"

                  "xixu-me/skills":
                    count: 2
                    skills:
                      - "old-one"
                      - "old-two"
                """
            ).lstrip(),
            encoding="utf-8",
        )

        (skills_root / "zeta").mkdir(parents=True)
        (skills_root / "alpha").mkdir(parents=True)
        (skills_root / "beta").mkdir(parents=True)
        (skills_root / "README.md").write_text("ignore me", encoding="utf-8")

        result = run_sync(manifest_path, skills_root)

        if result.returncode != 0:
            raise AssertionError(f"expected sync script to succeed, got {result.returncode}: {result.stderr}")

        data = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        skills_source = data["sources"]["xixu-me/skills"]
        assert skills_source["count"] == 3
        assert skills_source["skills"] == ["alpha", "beta", "zeta"]
        assert data["sources"]["xixu-me/xdrop"]["skills"] == ["xdrop"]
        assert data["total_sources"] == 3
        assert data["total_skills"] == 5


def test_preserves_skvlt_manifest_format() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = pathlib.Path(temp_dir)
        manifest_path = temp_path / "skvlt.yaml"
        skills_root = temp_path / "skills"

        manifest_path.write_text(
            textwrap.dedent(
                """
                # Generated for project-scoped restoration with Skills Vault.
                total_sources: 3
                total_skills: 8
                scope: "project"

                sources:
                  "xixu-me/xdrop":
                    count: 1
                    skills:
                      - "xdrop"

                  "xixu-me/xget":
                    count: 1
                    skills:
                      - "xget"

                  "xixu-me/skills":
                    count: 2
                    skills:
                      - "old-one"
                      - "old-two"
                """
            ).lstrip(),
            encoding="utf-8",
        )

        (skills_root / "alpha").mkdir(parents=True)
        result = run_sync(manifest_path, skills_root)
        if result.returncode != 0:
            raise AssertionError(f"expected sync script to succeed, got {result.returncode}: {result.stderr}")

        manifest_text = manifest_path.read_text(encoding="utf-8")
        if 'scope: "project"' not in manifest_text:
            raise AssertionError(f'expected quoted scope in manifest, got: {manifest_text!r}')
        if '  "xixu-me/skills":' not in manifest_text:
            raise AssertionError(f'expected quoted source key in manifest, got: {manifest_text!r}')
        if '      - "alpha"' not in manifest_text:
            raise AssertionError(f'expected quoted skill entries in manifest, got: {manifest_text!r}')


def test_fails_when_target_source_missing() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = pathlib.Path(temp_dir)
        manifest_path = temp_path / "skvlt.yaml"
        skills_root = temp_path / "skills"

        manifest_path.write_text(
            textwrap.dedent(
                """
                total_sources: 1
                total_skills: 1
                scope: "project"

                sources:
                  "xixu-me/xdrop":
                    count: 1
                    skills:
                      - "xdrop"
                """
            ).lstrip(),
            encoding="utf-8",
        )
        skills_root.mkdir()

        result = run_sync(manifest_path, skills_root)

        if result.returncode == 0:
            raise AssertionError("expected sync script to fail when xixu-me/skills source is missing")
        if "xixu-me/skills" not in result.stderr:
            raise AssertionError(f"expected error to mention missing source, got: {result.stderr!r}")


if __name__ == "__main__":
    test_updates_only_target_source_and_sorts_skills()
    test_preserves_skvlt_manifest_format()
    test_fails_when_target_source_missing()
    print("sync skills manifest tests passed")
