FROM apache/airflow:2.10.5-python3.12

USER root

RUN apt-get -y update && apt-get -y install git gcc g++

USER airflow  

ENV PYTHONPATH "${PYTHONPATH}:/opt/airflow"

ARG GIT_TOKEN

RUN git clone https://github.com/blue-core-lod/bluecore-workflows.git --depth 1 /opt/airflow/bluecore-workflows

RUN mv bluecore-workflows/README.md /opt/airflow/. && mv bluecore-workflows/uv.lock /opt/airflow/. && mv bluecore-workflows/pyproject.toml /opt/airflow/. && mv bluecore-workflows/config/webserver_config.py /opt/airflow/

RUN mv bluecore-workflows/ils_middleware /opt/airflow/ils_middleware && rm -rf bluecore-workflows

RUN uv build
RUN uv pip install dist/*.whl
