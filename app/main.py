import ctypes
import json
import io
import os
import subprocess
import sys
import shutil
import tarfile
import tempfile
from urllib import request
from dataclasses import dataclass


@dataclass
class Config:
    CLONE_NEWPID: int = 0x20000000
    ERROR_CODE: int = 1
    LAST_INDEX: int = -1
    TEMP_DIR: str = '/tmp'
    ROOT_DIR: str = '/'
    LIBC = ctypes.CDLL(None)
    REGISTRY_URL = "https://registry.hub.docker.com"
    AUTH_URL = "https://auth.docker.io/token?service=registry.docker.io&scope=repository"
    MANIFEST_ACCEPT_HEADER = "application/vnd.docker.distribution.manifest.v2+json"
    NO_ERROR = 0


config = Config()


def copy_command_to_workspace(command: str) -> (str, str):
    command_dir = tempfile.mkdtemp(dir=config.TEMP_DIR)
    # TODO seem to not need this for stage 6
    # shutil.copy(command, command_dir)
    # retval = "./" + command.split('/')[config.LAST_INDEX], command_dir
    return command, command_dir


def isolate_child_fs(workspace: str) -> None:
    os.chroot(workspace)
    os.chdir(config.ROOT_DIR)


def create_pid_namespace() -> None:
    # ref. https://elixir.bootlin.com/linux/latest/source/include/uapi/linux/sched.h#L32
    # ref. https://man7.org/linux/man-pages/man7/pid_namespaces.7.html
    # The first process created after a call to unshare(2) using CLONE_NEWPID has the PID 1
    # See also ref. https://man7.org/linux/man-pages/man2/unshare.2.html and
    config.LIBC.unshare(config.CLONE_NEWPID)


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


def get_auth_token(image: str) -> str:
    url = f"{config.AUTH_URL}:{image}:pull"
    response = request.urlopen(url)
    return json.loads(response.read())["token"]


def get_headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": config.MANIFEST_ACCEPT_HEADER,
    }


def fetch_manifest(token, image):
    r = request.Request(f"{config.REGISTRY_URL}/v2/{image}/manifests/latest",
                        headers=get_headers(token))
    response = request.urlopen(r)
    return json.loads(response.read())


def pull_layer(token: str, image: str, digest):
    r = request.Request(f"{config.REGISTRY_URL}/v2/{image}/blobs/{digest}",
                        headers=get_headers(token))
    response = request.urlopen(r)
    return response.read()


def download_image_layers(token: str, image: str, manifest, workspace: str) -> None:
    for layer in manifest["layers"]:
        layer_tar = pull_layer(token, image, layer["digest"])
        with tarfile.open(fileobj=io.BytesIO(layer_tar)) as tar:
            tar.extractall(workspace)


def main():
    command_args: list[str] = sys.argv[4:]
    image: str = "library/" + sys.argv[2]
    token: str = get_auth_token(image)
    manifest = fetch_manifest(token, image)

    subprocess_result = None
    try:
        command, workspace = copy_command_to_workspace(sys.argv[3])
        download_image_layers(token, image, manifest, workspace)
        isolate_child_fs(workspace)
        create_pid_namespace()
        subprocess_result = exec_command(command, command_args)
        get_stdio(subprocess_result)

    # Handle case where file ops in shutil fail
    except OSError as e:
        print(f"OS Error: {e}")
        sys.exit(config.ERROR_CODE)

    # Handle case where running the subprocess fails
    # Note that this exception is also available as
    except subprocess.CalledProcessError as e:
        print(f"Child process error: {e}")
        sys.exit(e.returncode)

    # Handle whatever else may occur
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(config.ERROR_CODE)

    finally:
        # Change root back and restore original working dir
        os.chroot(config.ROOT_DIR)

        # Check if child was naughty. If it was, hang head in shame!
        # We have this as a separate thing, because the code crafters test child returns an exit code
        # without actually failing or raising a CalledProcessError()
        if subprocess_result is not None and subprocess_result.returncode > 0:
            sys.exit(subprocess_result.returncode)
        sys.exit(config.NO_ERROR)


if __name__ == "__main__":
    main()
