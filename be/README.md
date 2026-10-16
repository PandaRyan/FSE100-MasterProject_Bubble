# Backend

## Run locally

From this directory, sync the dependencies and start the development server:

```sh
uv sync
uv run uvicorn main:app --reload
```

The API is available at <http://127.0.0.1:8000>. Interactive API
documentation is at <http://127.0.0.1:8000/docs>.

## Endpoints

- `GET /` returns a welcome message.
- `GET /health` returns the service health status.
