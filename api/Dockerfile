FROM python:3.12-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates git

ADD https://astral.sh/uv/install.sh /uv-installer.sh

RUN sh /uv-installer.sh && rm /uv-installer.sh

ENV PATH="/root/.local/bin/:$PATH"

ARG GIT_TOKEN

RUN git clone --depth 1 https://${GIT_TOKEN}@github.com/blue-core-lod/bluecore_api.git

WORKDIR /bluecore_api

RUN uv build && uv pip install --system dist/*.whl

CMD ["uv", "run", "fastapi", "run", "src/bluecore/app/main.py", "--port", "8100", "--root-path", "/api"] 
