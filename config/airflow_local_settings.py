"""Airflow local settings for the Blue Core stack.

Airflow's metadata database is reached through PgBouncer running in
transaction pooling mode, so consecutive transactions from one Airflow
connection can be served by different PostgreSQL backend connections.

The psycopg 3 driver (``postgresql+psycopg://``) automatically turns a query
into a server-side prepared statement after it has run ``prepare_threshold``
times (5 by default). Prepared statements live on a single backend
connection, so when PgBouncer hands the next transaction to another backend
the statement is missing and queries fail with errors such as
``prepared statement "_pg3_0" does not exist``.

Setting ``prepare_threshold`` to ``None`` turns off server-side prepared
statements. Airflow picks this up through
``AIRFLOW__DATABASE__SQL_ALCHEMY_CONNECT_ARGS=airflow_local_settings.connect_args``
in ``compose-base.yaml``.
"""

connect_args = {"prepare_threshold": None}
