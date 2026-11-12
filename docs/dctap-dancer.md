# 💃 DCTap Dancer
[DCTap Dancer](https://github.com/blue-core-lod/dctap-dancer) (a Bluecore fork
of [lcnetdev/dctap-dancer](https://github.com/lcnetdev/dctap-dancer)) is the
profile/template editor for Marva. Metadata staff edit Marva profiles and
starting points as DCTAP workspaces, and Marva loads them live.

| What | Where |
|---|---|
| Editor | `http://localhost/marva/dancer/` |
| Workspace list (read by Marva) | `http://localhost/marva/dancer/api/serve/workspaces` |
| Profiles / starting points for a workspace | `/marva/dancer/api/serve/<workspace id or name>/profile`, `.../starting-points` |
| Image | `ghcr.io/blue-core-lod/dctap-dancer` (override with `DCTAP_DANCER_IMAGE`) |
| Data | SQLite files in `./dctap-dancer-data/` on the host (`DCTAP_DANCER_DATA_DIR`), mounted at `/app/data` |

## 🔗 How Marva uses it
On load, Marva (`src/stores/profile.js`, via `src/bluecore/dancer.js`) picks
its profiles in this order:

1. The workspace chosen in Marva's **DCTap** menu (saved in the browser's
   `localStorage` as `marva-dancerWorkspace`), if it still exists.
2. The workspace named **`Blue Core`** (`dancerDefaultWorkspace` in
   `src/bluecore/environment.js`). Marva remembers it as the selection.
3. LC's profiles on GitHub (`profiles` / `starting` in
   `src/bluecore/environment.js`), when the dancer is unreachable or has no
   `Blue Core` workspace.

So editing `Blue Core` changes Marva's templates for everyone who hasn't
picked another workspace. To try changes safely, duplicate `Blue Core` in
the dancer, edit the copy, and select it from Marva's DCTap menu.

## 🌱 Seeded workspace
On first start the dancer creates `Blue Core` from LC's marva-prod profiles
and starting points, before it starts serving requests. It never seeds again
while a workspace with that name exists, so edits survive restarts and image
upgrades. To reseed, delete (or rename) `Blue Core` in the editor and restart
the container. If you change the seed name, change Marva's
`dancerDefaultWorkspace` to match.

| Variable (`.env`) | Default |
|---|---|
| `DCTAP_DANCER_SEED_WORKSPACE` | `Blue Core` |
| `DCTAP_DANCER_SEED_PROFILES` | LC `marva-prod/marva-profiles.json` (GitHub raw URL) |
| `DCTAP_DANCER_SEED_STARTING_POINTS` | LC `marva-prod/marva-starting.json` (GitHub raw URL) |

Quote names with spaces in `.env` (`DCTAP_DANCER_SEED_WORKSPACE="Blue Core"`).
The sources may be URLs or file paths inside the container. Set
`DCTAP_DANCER_SEED_WORKSPACE=` (empty) to turn seeding off.

## 💾 Where profiles persist
Marva stores no profiles; it fetches them from the dancer on every load. The
dancer keeps each workspace as a SQLite file in a **host directory** that is
bind-mounted into the container (not a named Docker volume):

| File | Contents |
|---|---|
| `_master.db` | Workspace list (names and IDs) |
| `<workspace-id>.db` | One workspace's shapes and rows (e.g. `Blue Core`) |

Each edit rewrites its workspace file immediately. Because the files live on
the host, they survive container rebuilds, `docker compose down -v`, and
volume prunes. Deleting the directory, or moving to a new server without it,
loses them; on the next start the dancer reseeds `Blue Core` from LC's
profiles, **silently discarding Blue Core's edits**.

Every environment (local, staging, production) defaults to
`./dctap-dancer-data/` in the `bluecore-stack` checkout, like `uploads/`. Its
contents are git-ignored, and `scripts/prod/run` never cleans the checkout.

To keep the data elsewhere (for example, off the checkout so a re-clone can't
lose it), set `DCTAP_DANCER_DATA_DIR` in `.env`, e.g.
`DCTAP_DANCER_DATA_DIR=/srv/bluecore/dctap-dancer-data`. Either way, include
the directory in the server's backups.

Back up by copying the directory (stop the container first for a clean copy),
or use the dancer's **Download** button for a single workspace `.db`.

## 🔐 Authentication
The editor and its API require a Keycloak login (`bluecore` realm, public
client `bluecore_api` with PKCE). If you are already signed in to Marva or
Sinopia, the login is silent. The `/api/serve/` routes and `/api/health` stay
public so Marva can read profiles without a token.

The dancer reads `KEYCLOAK_EXTERNAL_URL`, `KEYCLOAK_INTERNAL_URL` and
`KEYCLOAK_REALM` from `.env`. Token issuers must match `KEYCLOAK_EXTERNAL_URL`
(that is, `KC_HOSTNAME`).

## 🛠️ Local development

`scripts/dev/run --marva` (or a full run) runs the dancer from your checkout
at `LOCAL_DCTAP_DANCER_DIR` (default `../dctap-dancer`, on `bluecore-dev-mvp`)
with hot reload:

| Part | Watcher | When you edit |
|---|---|---|
| Frontend (`frontend/src/`) | Vite dev server | Changes show in the browser right away, no reload |
| Backend (`backend/src/`) | `tsx watch` | The API restarts in a couple of seconds |

nginx (`nginx/local-dev.conf`) sends `/marva/dancer/api/` to the backend and
everything else under `/marva/dancer/` to Vite. Both log to
`docker compose logs -f dctap-dancer`, tagged `[api]` and `[ui]`.

After changing dependencies (`package.json`), restart the container so it
reinstalls them. Image mode (`scripts/dev/run --image`) runs the published GHCR
image instead, with no hot reload.

## 🚀 Releases
Publishing the image is manual only; merges to the fork never publish. The
fork's `.github/workflows/bluecore-publish.yml` builds it with
`VITE_BASE_PATH=/marva/dancer/` when you either run the workflow from the
Actions tab on `bluecore-dev-mvp` (pushes `:latest`) or publish a GitHub Release
targeting `bluecore-dev-mvp` (pushes `:latest` and `:<tag>`). See the fork's
`BLUECORE.md`. Pin a release with
`DCTAP_DANCER_IMAGE=ghcr.io/blue-core-lod/dctap-dancer:<tag>`.
