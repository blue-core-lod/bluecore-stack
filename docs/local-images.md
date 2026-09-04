# Building Local Images

`./scripts/dev/run --local-images` runs the published-image stack but builds the services 
you name from the Dockerfiles in your local checkouts, for when the thing you are changing 
is the Dockerfile or the production build rather than app code.

```bash
# Build Sinopia from ../sinopia_editor/Dockerfile; everything else comes from GHCR
./scripts/dev/run --local-images --sinopia

# Same for the API, Marva (+ its middleware), or the Airflow workflows image
./scripts/dev/run --local-images --api
./scripts/dev/run --local-images --marva
./scripts/dev/run --local-images --airflow

# Combine flags, or pass none to build every one of them
./scripts/dev/run --local-images --marva --sinopia
./scripts/dev/run --local-images

# After a change: rebuild the image and recreate only those containers
./scripts/dev/run --local-images --sinopia --rebuild
./scripts/dev/run --local-images --sinopia --rebuild --no-cache
```

Builds are tagged `<name>:built-dev-image`. For everyday app work use 
`./scripts/dev/run --sinopia` instead — that mode bind-mounts your source for live reload 
and never touches the Dockerfile.
