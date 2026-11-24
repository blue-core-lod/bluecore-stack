"""LOCAL DEV ONLY: register the Graph Toolbox plugin from your local checkout.

compose-local-dev.yaml mounts this file into Airflow's plugins folder and puts
the graph-toolbox source (LOCAL_GRAPH_TOOLBOX_DIR, default the nginx/toolbox
submodule) on PYTHONPATH. Airflow imports every module in the plugins folder
and registers the AirflowPlugin subclasses it finds, so no pip install is
needed and whatever branch the checkout is on is what runs.

Without a pip install there is no package metadata, so the Toolbox would report
version "0.0.0+unknown". Its modules read ``__version__`` from the package at
import time, so set it from the checkout's pyproject.toml (mounted read-only)
before the plugin is imported.
"""

import tomllib

import bluecore_graph_toolbox

try:
    with open("/bluecore_graph_toolbox/pyproject.toml", "rb") as pyproject:
        bluecore_graph_toolbox.__version__ = tomllib.load(pyproject)["project"]["version"]
except (OSError, KeyError, tomllib.TOMLDecodeError):
    pass  # keep the package's own fallback

from bluecore_graph_toolbox.plugin import GraphToolboxPlugin  # noqa: E402, F401
