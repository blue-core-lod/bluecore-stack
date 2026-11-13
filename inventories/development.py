import os
import sys
import paramiko

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from duo import auth_gss_then_duo

paramiko.Transport.auth_gssapi_with_mic = auth_gss_then_duo

bluecore_dev = [
    (
        "bluecore-dev.stanford.edu",
        {
            "ssh_paramiko_connect_kwargs": {
                "gss_auth": True,
                "gss_deleg_creds": True,
            },
            "ssh_look_for_keys": False,
            "ssh_allow_agent": False,
        },
    )
]
