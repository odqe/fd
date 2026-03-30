import os
import pathlib
import subprocess
import sys
import tempfile
import textwrap


ROOT = pathlib.Path(__file__).resolve().parents[1]
RETRY_SCRIPT = ROOT / "scripts" / "retry-command.sh"


def to_wsl_path(path: pathlib.Path) -> str:
    drive = path.drive.rstrip(":").lower()
    tail = path.as_posix().split(":", 1)[1]
    return f"/mnt/{drive}{tail}"


def bash_command(script_path: pathlib.Path, *args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)

    if os.name == "nt":
        env_args = []
        if env:
            env_args = ["env", *[f"{key}={value}" for key, value in env.items()]]
        cmd = ["wsl.exe", *env_args, "bash", to_wsl_path(script_path), *args]
    else:
        cmd = ["bash", str(script_path), *args]
    return subprocess.run(cmd, text=True, capture_output=True, env=merged_env, check=False)


def write_script(path: pathlib.Path, content: str) -> None:
    path.write_text(textwrap.dedent(content).lstrip(), encoding="utf-8", newline="\n")


def assert_equal(actual, expected, message: str) -> None:
    if actual != expected:
        raise AssertionError(f"{message}: expected {expected!r}, got {actual!r}")


def shell_path(path: pathlib.Path) -> str:
    return to_wsl_path(path) if os.name == "nt" else str(path)


def main() -> int:
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = pathlib.Path(temp_dir)
        counter_file = temp_path / "counter.txt"
        counter_path = shell_path(counter_file)

        retry_then_succeed = temp_path / "retry-then-succeed.sh"
        write_script(
            retry_then_succeed,
            f"""
            #!/usr/bin/env bash
            count=0
            if [ -f "{counter_path}" ]; then
              count=$(cat "{counter_path}")
            fi
            count=$((count + 1))
            echo "$count" > "{counter_path}"
            if [ "$count" -eq 1 ]; then
              echo "Rate limit exceeded (retry in 1s, remaining: 0/180, reset in 1s)" >&2
              exit 1
            fi
            echo "installed"
            """,
        )
        result = bash_command(
            RETRY_SCRIPT,
            "bash",
            shell_path(retry_then_succeed),
            env={"RETRY_ATTEMPTS": "3", "RETRY_SKIP_SLEEP": "1"},
        )
        assert_equal(result.returncode, 0, "retryable failure should eventually succeed")
        assert_equal(counter_file.read_text(encoding="utf-8").strip(), "2", "retryable failure should run twice")
        if "Retrying command in 2s (attempt 1/3)" not in result.stdout:
            raise AssertionError(f"expected retry log in stdout, got: {result.stdout!r}")

        counter_file.write_text("", encoding="utf-8")
        non_retryable = temp_path / "non-retryable.sh"
        write_script(
            non_retryable,
            """
            #!/usr/bin/env bash
            echo "permission denied" >&2
            exit 7
            """,
        )
        result = bash_command(
            RETRY_SCRIPT,
            "bash",
            shell_path(non_retryable),
            env={"RETRY_ATTEMPTS": "3", "RETRY_SKIP_SLEEP": "1"},
        )
        assert_equal(result.returncode, 7, "non-retryable failure should keep original exit code")
        if "Retrying command" in result.stdout:
            raise AssertionError(f"unexpected retry log for non-retryable failure: {result.stdout!r}")

        no_hint_retry = temp_path / "no-hint-retry.sh"
        no_hint_counter = temp_path / "no-hint-counter.txt"
        no_hint_counter_path = shell_path(no_hint_counter)
        write_script(
            no_hint_retry,
            f"""
            #!/usr/bin/env bash
            count=0
            if [ -f "{no_hint_counter_path}" ]; then
              count=$(cat "{no_hint_counter_path}")
            fi
            count=$((count + 1))
            echo "$count" > "{no_hint_counter_path}"
            if [ "$count" -eq 1 ]; then
              echo "Rate limit exceeded" >&2
              exit 1
            fi
            echo "ok"
            """,
        )
        result = bash_command(
            RETRY_SCRIPT,
            "bash",
            shell_path(no_hint_retry),
            env={"RETRY_ATTEMPTS": "3", "RETRY_SKIP_SLEEP": "1"},
        )
        assert_equal(result.returncode, 0, "retry without delay hint should still succeed")
        if "Retrying command in 3s (attempt 1/3)" not in result.stdout:
            raise AssertionError(f"expected fallback retry delay in stdout, got: {result.stdout!r}")

        http_retry = temp_path / "http-retry.sh"
        http_counter = temp_path / "http-counter.txt"
        http_counter_path = shell_path(http_counter)
        write_script(
            http_retry,
            f"""
            #!/usr/bin/env bash
            count=0
            if [ -f "{http_counter_path}" ]; then
              count=$(cat "{http_counter_path}")
            fi
            count=$((count + 1))
            echo "$count" > "{http_counter_path}"
            if [ "$count" -eq 1 ]; then
              echo "Unexpected HTTP response: 502" >&2
              exit 1
            fi
            echo "downloaded"
            """,
        )
        result = bash_command(
            RETRY_SCRIPT,
            "bash",
            shell_path(http_retry),
            env={"RETRY_ATTEMPTS": "3", "RETRY_SKIP_SLEEP": "1"},
        )
        assert_equal(result.returncode, 0, "HTTP 502 responses should be retried")
        assert_equal(http_counter.read_text(encoding="utf-8").strip(), "2", "HTTP 502 retry should rerun the command")

        server_error_retry = temp_path / "server-error-retry.sh"
        server_error_counter = temp_path / "server-error-counter.txt"
        server_error_counter_path = shell_path(server_error_counter)
        write_script(
            server_error_retry,
            f"""
            #!/usr/bin/env bash
            count=0
            if [ -f "{server_error_counter_path}" ]; then
              count=$(cat "{server_error_counter_path}")
            fi
            count=$((count + 1))
            echo "$count" > "{server_error_counter_path}"
            if [ "$count" -eq 1 ]; then
              echo '{{"code":"[Request ID: 7b686a65fe23a6aa] Server Error"}}' >&2
              exit 1
            fi
            echo "installed"
            """,
        )
        result = bash_command(
            RETRY_SCRIPT,
            "bash",
            shell_path(server_error_retry),
            env={"RETRY_ATTEMPTS": "3", "RETRY_SKIP_SLEEP": "1"},
        )
        assert_equal(result.returncode, 0, "generic server errors should be retried")
        assert_equal(
            server_error_counter.read_text(encoding="utf-8").strip(),
            "2",
            "generic server errors should rerun the command",
        )

    print("retry-command tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
