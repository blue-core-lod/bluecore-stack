# JupyterHub image for the Blue Core Stack.
# Adds the packages needed to spawn per-user containers (DockerSpawner),
# authenticate against Keycloak (oauthenticator), and store Hub state in
# the shared Postgres instance instead of the default sqlite file.
FROM quay.io/jupyterhub/jupyterhub:5.2

RUN pip install --no-cache-dir \
    dockerspawner==13.* \
    oauthenticator==17.* \
    psycopg2-binary==2.9.*

COPY jupyterhub_config.py /srv/jupyterhub/jupyterhub_config.py

WORKDIR /srv/jupyterhub
