import subprocess
import sys


def main():
    # print(f"Command line: {sys.argv}")
    command: str = sys.argv[3]
    args: list[str] = sys.argv[4:]
    # print(f"Command: {command} Args: {args}")

    completed_process = subprocess.run([command, *args], capture_output=True)
    # print(f"Child stdout: {stdout_output}, child stderr: {stderr_output}")

    # Redirect the captured stdout and stderr to those of the parent
    sys.stdout.write(completed_process.stdout.decode("utf-8"))
    sys.stderr.write(completed_process.stderr.decode("utf-8"))


if __name__ == "__main__":
    main()
