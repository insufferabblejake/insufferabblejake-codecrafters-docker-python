import ctypes
import os
import subprocess
import sys
import shutil
import tempfile


CLONE_NEWPID = 0x20000000


def main():
    libc = ctypes.CDLL(None)
    # print(f"Command line: {sys.argv}")
    command: str = sys.argv[3]
    args: list[str] = sys.argv[4:]
    # print(f"Command: {command} Args: {args}")

    tmp_dir = tempfile.mkdtemp(dir='/tmp')
    # old_cwd = os.getcwd()
    completed_process = None
    try:
        shutil.copy(command, tmp_dir)
        # the copied command name without path in the new place
        command = "./" + command.split('/')[-1]

        # Change root directory to the temporary directory
        # fs isolation
        os.chroot(tmp_dir)
        os.chdir('/')

        # process isolation
        # Creating a new PID namespace
        # ref. https://elixir.bootlin.com/linux/latest/source/include/uapi/linux/sched.h#L32
        # ref. https://man7.org/linux/man-pages/man7/pid_namespaces.7.html
        # The first created after a call to unshare(2) using CLONE_NEWPID has the PID 1
        # See also ref. https://man7.org/linux/man-pages/man2/unshare.2.html and
        libc.unshare(CLONE_NEWPID)

        # This call does a lot of heavy lifting
        # Specifically, it calls the Popen() lib call which will call a fork() and exec() thus
        # executing the command (with it's args) in a new process space. Usual inheritance of
        # stdout, stderr and stdin from the parent process apply. Including sigmask etc.
        # the capture_output flag controls whether we pipe stdout and stderr back to parent
        completed_process = subprocess.run([command, *args], capture_output=True)
        # print(f"Child stdout: {stdout_output}, child stderr: {stderr_output}")

        # Write the captured stdout and stderr to those of the parent
        # Note that this is different from actually redirecting the output of the child, we save
        # and explicitly write. If we had wanted to redirect, we'd get the stdout and stderr of
        # the child, use os.dup() in the parent to 'realtime' redirect, and restored the parents
        # original file handles for these streams after redirection is done.
        # stdio isolation
        if completed_process.stdout:
            sys.stdout.write(completed_process.stdout.decode("utf-8"))
        if completed_process.stderr:
            sys.stderr.write(completed_process.stderr.decode("utf-8"))

    finally:
        # Change root back and restore original working dir
        os.chroot('/')
        # os.chdir(old_cwd)

        # Remove the temporary directory and all its contents
        # This doesn't seem to work, as cc runs the tests in a docker, so not sure what's happening.
        # shutil.rmtree(tmp_dir)

        # Interesting that we can also do the following, instead of what is being done
        # later on in the code.
        # try:
        #     completed_process.check_returncode()
        # except subprocess.CalledProcessError as e:
        #     # print(f"Child error {e.returncode}")
        #     sys.exit(e.returncode)

        # Check if child was naughty. If it was, hang head in shame!
        if completed_process is not None and completed_process.returncode > 0:
            sys.exit(completed_process.returncode)
        sys.exit(0)


if __name__ == "__main__":
    main()
