# Blue Core Terraform and Docker

## Configuration
The Keycloak Container requires a local `.env` with the following variables:

```bash
###########################--------------------------------
## Airflow Configuration ##
###########################
DATABASE_URL=postgresql+psycopg2://airflow:airflow@postgres/bluecore

######################-------------------------------------
## Keycloak Clients ##
######################
# Client 1: bluecore_api
API_KEYCLOAK_CLIENT_ID=bluecore_api
API_KEYCLOAK_CLIENT_SECRET=K0b2aBJlqDFcTiozMTP5XM6vf2G9E18W

# Client 2: airflow_client
AIRFLOW_KEYCLOAK_REALM=bluecore
AIRFLOW_KEYCLOAK_CLIENT_ID=bluecore_workflows
AIRFLOW_KEYCLOAK_CLIENT_SECRET=KIu8gWa8rtjlT0Zl7zkNzsObFZGJ2IsJ
KEYCLOAK_INTERNAL_URL=http://keycloak:8080/keycloak/
KEYCLOAK_EXTERNAL_URL=http://localhost/keycloak/

############################-------------------------------
## Keycloak Configuration ##
############################
# Bluecore realm and keycloak path
KEYCLOAK_REALM=bluecore

# Master realm Admin credentials
KEYCLOAK_ADMIN=admin
KEYCLOAK_ADMIN_PASSWORD=gracious-professed

# Keycloak database connection
KC_DB=postgres
KC_DB_URL_HOST=postgres
KC_DB_URL_PORT=5432
KC_DB_URL_DATABASE=keycloak
KC_DB_SCHEMA=public
KC_DB_USERNAME=airflow
KC_DB_PASSWORD=airflow

# Keycloak health check enabled
KC_HEALTH_ENABLED=true 

# Keycloak HTTP and proxy access settings
KEYCLOAK_URL=http://keycloak:8080/keycloak/
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
4. Create a user in the new `bluecore` realm
5. Add the `create` and `update` roles to the user

###  💾 Exporting Keycloak realm config
To export any changes of the bluecore realm config, you can use the following commands
depending on the environment you are working in:

```bash
   # 🚧 Development
   ./scripts/export-keycloak-realm.sh
````

```bash
   # 🚀 Production
   ./scripts/export-keycloak-realm.sh --env=production
```

This will export the realm config to the `keycloak-export` directory.


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
