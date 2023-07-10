import ctypes
import os
import subprocess
import sys
import shutil
import tempfile


CLONE_NEWPID: int = 0x20000000
ERROR_CODE: int = 1
LAST_INDEX: int = -1
TEMP_DIR: str = '/tmp'
ROOT_DIR: str = '/'
LIBC = ctypes.CDLL(None)


def copy_to_tmp_get_name(command: str) -> (str, str):
    tmp_dir = tempfile.mkdtemp(dir=TEMP_DIR)
    shutil.copy(command, tmp_dir)
    return "./" + command.split('/')[LAST_INDEX], tmp_dir


def isolate_child_fs(tmp_dir: str) -> None:
    os.chroot(tmp_dir)
    os.chdir(ROOT_DIR)


def create_pid_namespace() -> None:
    # ref. https://elixir.bootlin.com/linux/latest/source/include/uapi/linux/sched.h#L32
    # ref. https://man7.org/linux/man-pages/man7/pid_namespaces.7.html
    # The first process created after a call to unshare(2) using CLONE_NEWPID has the PID 1
    # See also ref. https://man7.org/linux/man-pages/man2/unshare.2.html and
    LIBC.unshare(CLONE_NEWPID)


def exec_command(command: str, args: list[str]):
    # This call does a lot of heavy lifting
    # Specifically, it calls the Popen() lib call which will call a fork() and exec() thus
    # executing the command (with it's args) in a new process space. Usual inheritance of
    # stdout, stderr and stdin from the parent process apply. Including sigmask etc.
    # the capture_output flag controls whether we pipe stdout and stderr back to parent
    return subprocess.run([command, *args], capture_output=True)


def get_stdio(subprocess_result) -> None:
    # Write the captured stdout and stderr to those of the parent
    # Note that this is different from actually redirecting the output of the child, we save
    # and explicitly write. If we had wanted to redirect, we'd get the stdout and stderr of
    # the child, use os.dup() in the parent to 'realtime' redirect, and restored the parents
    # original file handles for these streams after redirection is done.
    if subprocess_result.stdout:
        sys.stdout.write(subprocess_result.stdout.decode("utf-8"))
    if subprocess_result.stderr:
        sys.stderr.write(subprocess_result.stderr.decode("utf-8"))


def main():
    args: list[str] = sys.argv[4:]

    subprocess_result = None
    try:
        command, tmp_dir = copy_to_tmp_get_name(sys.argv[3])
        isolate_child_fs(tmp_dir)
        create_pid_namespace()
        subprocess_result = exec_command(command, args)
        get_stdio(subprocess_result)

    # Handle case where file ops in shutil fail
    except OSError as e:
        print(f"OS Error: {e}")
        sys.exit(ERROR_CODE)

    # Handle case where running the subprocess fails
    # Note that this exception is also available as
    except subprocess.CalledProcessError as e:
        print(f"Child process error: {e}")
        sys.exit(e.returncode)

    # Handle whatever else may occur
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(ERROR_CODE)

    finally:
        # Change root back and restore original working dir
        os.chroot('/')

        # Check if child was naughty. If it was, hang head in shame!
        # We have this as a separate thing, because the codecrafters test child returns an exit code
        # without actually failing or raising a CalledProcessError()
        if subprocess_result is not None and subprocess_result.returncode > 0:
            sys.exit(subprocess_result.returncode)
        sys.exit(0)


if __name__ == "__main__":
    main()
