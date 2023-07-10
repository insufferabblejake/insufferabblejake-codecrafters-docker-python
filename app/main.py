import subprocess
import sys


def main():
    # print(f"Command line: {sys.argv}")
    command: str = sys.argv[3]
    args: list[str] = sys.argv[4:]
    # print(f"Command: {command} Args: {args}")

    # This call does a lot of heavy lifting
    # Specifically, it calls the Popen() lib call which will call a fork() and exec() thus
    # executing the command (with it's args) in a new process space. Usual inheritance of
    # stdout, stderr and stdin from the parent process apply. Including sigmask etc.
    # the capture_output flag controls whether we pipe stdout and stderr back to parent
    # so we can save it/process it later.
    completed_process = subprocess.run([command, *args], capture_output=True)
    # print(f"Child stdout: {stdout_output}, child stderr: {stderr_output}")

    # Write the captured stdout and stderr to those of the parent
    # Note that this is different from actually redirecting the output of the child, we save
    # and explicitly write. If we had wanted to redirect, we'd get the stdout and stderr of
    # the child, use os.dup() in the parent to 'realtime' redirect, and restored the parents
    # original file handles for these streams after redirection is done.
    sys.stdout.write(completed_process.stdout.decode("utf-8"))
    sys.stderr.write(completed_process.stderr.decode("utf-8"))


if __name__ == "__main__":
    main()
