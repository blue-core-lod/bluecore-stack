# Blue Core Terraform and Docker

## Configuration
The Keycloak Container requires a local `.env` with the following variables:

```bash
DATABASE_URL=postgresql+psycopg2://airflow:airflow@postgres/bluecore
KEYCLOAK_URL=http://keycloak:8080
KEYCLOAK_REALM=bluecore
KEYCLOAK_CLIENT_ID=bluecore_api
KEYCLOAK_CLIENT_SECRET=<from bluecore_api client in keycloak>
KEYCLOAK_ADMIN=admin
KEYCLOAK_ADMIN_PASSWORD=gracious-professed
KC_DB=postgres
KC_DB_URL_HOST=postgres
KC_DB_URL_PORT=5432
KC_DB_URL_DATABASE=keycloak
KC_DB_SCHEMA=public
KC_DB_USERNAME=airflow
KC_DB_PASSWORD=airflow
KC_PROXY_HEADERS=xforwarded
KC_PROXY=edge
KC_HTTP_ENABLED=true
KC_HTTP_RELATIVE_PATH=/keycloak/
KC_LOG_LEVEL=INFO
KC_HOSTNAME=https://dev.bcld.info/keycloak
```

## Setup Airflow (Blue Core Workflows)
### Blue Core Database Connection
Some DAGs require a `bluecore_db` Postgres Connection (In the UI from the **Admin -> Connection** menu) 
with the following variables:

- **Connection Id**: bluecore_db
- **Connection Type**: Postgres
- **Host**: postgres
- **Database**: bluecore
- **Login**: airflow
- **Password**: airflow

## Setup Keycloak
To use Keycloak in the API and Airflow, you will need to do the following steps:
1. Create a `bluecore` realm
2. Create a `bluecore_api` client in the `bluecore` realm
   - **Client id**: `bluecore_api`
   - Turn on **Client authentication**
3. Create `create` and `update` Realm roles
4. Create a user 
5. Add the `create` and `update` roles to the user

## Blue Core Technical Stack
```mermaid
graph LR;
    sinopia["Sinopia"] --> keycloak["Keycloak"]
    marva["Marva"] --> keycloak
    graph_explorer["Graph Explorer"] --> keycloak
    notebooks@{ shape: docs, label: "Jupyter Notebooks"} --> keycloak

    keycloak <--> api["Blue Core API"]
    keycloak <--> workflows["Blue Core Workflows (Airflow)"]
    api <--> db[("Blue Core Database")]
    api --> workflows
    workflows <--> db
    db <--> vector_db[("Triples Vector Datastore")]
    api <--> vector_db
    workflows <--> vector_db
    api <--> ai_agents@{ shape: procs, label: "LLM AI Agents"}
    ai_agents <--> workflows
    ai_agents <--> vector_db
```
## For Local Development
Dev Docker compose file needs to be specified when starting the container service.
```bash
docker compose -f compose-dev.yaml up
```
