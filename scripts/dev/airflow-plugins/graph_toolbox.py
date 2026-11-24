"""Local dev only: loads the Graph Toolbox plugin from your checkout (no pip install).
Also sets its version from pyproject.toml, which would otherwise show "0.0.0+unknown".
"""

import tomllib

import bluecore_graph_toolbox

try:
    with open("/bluecore_graph_toolbox/pyproject.toml", "rb") as pyproject:
        bluecore_graph_toolbox.__version__ = tomllib.load(pyproject)["project"]["version"]
except (OSError, KeyError, tomllib.TOMLDecodeError):
    pass  # keep the default version

from bluecore_graph_toolbox.plugin import GraphToolboxPlugin  # noqa: E402, F401
