import io
from pyinfra.operations import files, server

STACK_DIR = "/home/bluecore/bluecore-stack"
REPO_URL = "https://github.com/blue-core-lod/bluecore-stack"
SCRIPT_PATH = "/tmp/bluecore-deploy.sh"

deploy_script = f"""#!/bin/bash
set -e
if [ -d {STACK_DIR}/.git ]; then
    git -C {STACK_DIR} pull
else
    git clone {REPO_URL} {STACK_DIR}
fi
cd {STACK_DIR}
docker compose down
docker compose up -d
"""

files.put(
    name="Upload deploy script",
    src=io.StringIO(deploy_script),
    dest=SCRIPT_PATH,
    mode="755",
)

server.shell(
    name="Run deploy as bluecore",
    commands=[f"ksu bluecore -e /bin/bash {SCRIPT_PATH}"],
)
