# Single-user notebook image spawned by DockerSpawner for each JupyterHub
# user. Bakes in the same deps and notebooks documented in training/README.md
# so a Hub-hosted notebook matches the local `uv run jupyter lab` workflow.
#
# Build context is the repo root (see the `jupyterhub` service's `build:` in
# compose-base.yaml) so this can COPY from training/ alongside jupyterhub/.
FROM quay.io/jupyter/scipy-notebook:2025-08-11

USER root
COPY jupyterhub/singleuser/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt && \
    rm /tmp/requirements.txt

USER ${NB_UID}

# Seeds the per-user named volume mounted at this path on first spawn (Docker
# copies image content into an empty named volume the first time it's used).
COPY --chown=${NB_UID}:${NB_GID} training/notebooks/ /home/jovyan/work/notebooks/
COPY --chown=${NB_UID}:${NB_GID} training/blue_core_mcp.py /home/jovyan/work/
