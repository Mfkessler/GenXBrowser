# GenXBrowser Frontend

For the [user guide and local quickstart](../README.md), start at the repository root.

## Development

With the [backend](../backend/README.md#development-workflow) running locally on port 5000 and Node.js 20.19+ or 22.12+:

```bash
npm ci
GENX_DEV_BACKEND_URL=http://127.0.0.1:5000 npm run dev -- --host 127.0.0.1
```

Checks: `npm run build:check`, `npm run test:unit -- --run`.

## Deployment

The [Dockerfile](Dockerfile) builds the app and serves it with nginx. Run the backend as `backend:5000` on the same Docker network. The default serves the app at `/` and sends requests to `/api`. For subpaths, set `VITE_BASE_URL` to the app path with a trailing slash and `VITE_API_BASE_URL` to the API's prefix **without** `/api`; configure your reverse proxy to strip that prefix before forwarding to nginx.

To customize branding, mount the generated `genxbrowser_config.yaml` at `/usr/share/nginx/html/genxbrowser_config.yaml`. It is read at runtime.

### Optional legal pages

Default images ship without legal texts or links. Bind-mount a trusted, operator-maintained directory at `/usr/share/nginx/html/instance-legal` (read-only), containing `index.json` with `{"enabled":true}`, `imprint.html`, and `terms.html`. Keep the files outside source and build contexts. For subpath deployments, forward `instance-legal/` as static content and use relative links back to the app (e.g. `../catalog`).
