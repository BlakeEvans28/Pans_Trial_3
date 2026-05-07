# Web Build and Deployment

This page covers how Pan's Trial is packaged for browser play and how to host the generated build.

## Prerequisites

- Python `3.12`
- The packages listed in `requirements-web.txt`
- The project root as the current working directory

## Build the Web Version

```powershell
py -3.12 -m venv .venv-web
.\.venv-web\Scripts\python.exe -m pip install --upgrade pip
.\.venv-web\Scripts\python.exe -m pip install -r requirements-web.txt
.\.venv-web\Scripts\python.exe build_web.py --build-only
```

## What the Build Produces

The build process stages the project, bundles browser dependencies, and writes:

- `WEB_BUILD/site` - deployable browser site
- `WEB_BUILD/pans_trial_web.zip` - local deployment zip
- `build/pans_trial_web_<timestamp>/build/web` - timestamped staging output

`build_web.py` also refreshes the deploy site and can include the PHP room relay when requested.

## Serve the Browser Build Locally

For the closest local test to a hosted experience, use the room server:

```powershell
.\.venv-web\Scripts\python.exe room_server.py --host 127.0.0.1 --port 8000
```

Open:

```text
http://127.0.0.1:8000
```

If you only need a static local browser check, `build_web.py` can build and serve in one step:

```powershell
.\.venv-web\Scripts\python.exe build_web.py --port 8000
```

## One-URL Hosted Deployment

For a hosted setup where the same origin serves both the web game and multiplayer rooms:

```powershell
.\.venv-web\Scripts\python.exe build_web.py --build-only
.\.venv-web\Scripts\python.exe room_server.py --host 0.0.0.0
```

Helpful repo files:

- `render.yaml`
- `Procfile`
- `room_server.py`

The room server also exposes:

```text
/health
```

## Shared Hosting With PHP

If your host cannot run the Python room server but can run PHP:

```powershell
.\.venv-web\Scripts\python.exe build_web.py --build-only --php-room-server
```

Then upload the contents of `WEB_BUILD/site` to the host.

This mode points multiplayer traffic at `room_server.php` and includes a writable room-data folder for the relay. It is useful for lightweight hosting, but the Python room server is still the stronger backend option.

## HTTPS Notes

If the page is served over HTTPS, the room API should also be HTTPS. Browsers often block secure pages from calling plain HTTP endpoints.

To run the Python room server with TLS:

```powershell
.\.venv-web\Scripts\python.exe room_server.py --certfile path\to\cert.pem --keyfile path\to\key.pem
```

## Useful Room-Server Options

- `--host`: bind address
- `--port`: port number
- `--web-root`: static site folder to serve
- `--max-rooms`: room cap
- `--room-timeout-seconds`: inactive room cleanup threshold

Environment variable equivalents exist for room limits and timeout tuning.

## Common Deployment Pattern

1. Build the browser package.
2. Verify the site locally.
3. Host `WEB_BUILD/site` behind the Python room server when possible.
4. Fall back to the PHP relay only when long-lived Python hosting is not available.
5. Rebuild and redeploy after gameplay, UI, or asset changes.
