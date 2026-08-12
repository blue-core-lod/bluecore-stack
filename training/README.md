# Blue Core Developer On-boarding

This repository contains some documentation and configuration to help you get started with the [Blue Core](https://bluecore.info/) stack. Blue Core aims to create a community-operated BIBFRAME datastore where ownership and creation of the metadata are shared among member institutions, eliminating the need for duplicative institutional copies, and bringing library linked open data to production at scale. The technical stack currently includes:

* BIBFRAME Editors: [Marva](https://github.com/blue-core-lod/marva_editor) and 
  [Sinopia](https://github.com/blue-core-lod/sinopia_editor) are included in the stack to demonstrate 
  how the core Blue Core service can serve as a storage system used by a larger ecosystem of BIBFRAME tools.
* API Service: A REST based API for creating, reading, updating and deleting BIBFRAME data. It also 
  includes an MCP API for generative AI agents. Built with [FastAPI](https://fastapi.tiangolo.com/)
* Identity Management: A [Keycloak](https://www.keycloak.org/) based system for managing human and automated 
  access to the API.
* Workflow System: An [Apache Airflow](https://airflow.apache.org/) system for managing the loading BIBFRAME 
  data into ILS systems and ingesting CBD files into Blue Core Postgres database.
* A developer account is available for use in the various services:
  - **user:** `developer`
  - **password:** `123456`
Below are some instructions for getting started experimenting with you own instance of these services.

## Local Setup
Steps for setting up the Blue Core stack to run locally on your machine are available in the Blue Core Stack
[README](https://github.com/blue-core-lod/bluecore-stack#-new-developer-quick-start).

You should also load Sinopia's [resource templates](https://github.com/blue-core-lod/bluecore-stack/blob/main/docs/local-development.md#-load-resource-templates)
and some [CBD files](https://github.com/blue-core-lod/bluecore-stack/blob/main/docs/local-development.md#-load-data).

## Install Training Dependencies with uv
1. If you haven't already, please install [uv](https://github.com/astral-sh/uv)
2. Run `uv sync` to install the dependencies in the `bluecore-stack/training` direcotry.

## Launch Jupyter Lab
From the `training` folder, launch [Jupyter Lab](https://jupyter.org/) with the following 
command:

`uv run jupyter lab`

**NOTE**: If using the included Jupyter notebooks, you'll need to have a local version of the Blue Core stack running at http://localhost.

## Editing in Sinopia
1. Log into Sinopia 
2. Search for an existing Work or Instance
3. When loading, select either a Blue Core `_Work` or `_Instance` template
4. Add a note in Sinopia
5. Save (and fix any errors) 
6. Directly open the resource with the URL to see the changes

## Editing in Marva
1. Open Marva
2. Copy a Instance URL into Load field
3. Edit the Loaded Instance or Work
4. POST to save the changes to the Blue Core 

## Using the Graph Toolbox
1. Click on Graph toolbox
2. Run a search
3. Load resources

## Using the MCP API with Claude Code
1. Open Claude Code in the `bluecore-stacks/training` directory
2. Give Claude a prompt to `Use the local Blue Core MCP server using blue_core_mcp.py`
3. Ask for Claude to generate a csv report listing BIBFRAME Works in Blue Core with titles and associated BIBFRAME Instances.
