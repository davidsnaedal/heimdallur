# Heimdallur

Cross-index **exact** person search over:
- [Lögbirtingablað](https://lbl.dsna.codes) (logbirting-search)
- [Dómar](https://judgements.dsna.codes) (domar-search)
- [Stjórnartíðindi](https://stjornartidindi.dsna.codes) (stjornartidindi-search)

Query must be a **full name** (given name + surname) or a **kennitala** (`DDMMYY-XXXX`). No keyword / partial-name search. Icelandic grammatical case forms of the same name are treated as the same phrase.

## Run

```bash
docker compose up --build
```

Then open (LAN binds — not `0.0.0.0`):
- Web UI: `http://192.168.0.3:5175`
- API health: `http://192.168.0.3:8003/api/health`

Public URL is **https://heimdallur.dsna.codes** via the **kvik** nginx + Authentik stack (`C:\Users\dave\Projects\kvik`).

To roll back to the stack *before* Stjórnartíðindi was wired in, check out tag `checkpoint/pre-stjornartidindi` on this repo and on kvik (same tag name).

The LBL (`logbirting-search`), Dómar (`domar-search`), and Stjórnartíðindi (`stjornartidindi-search`) stacks must already be running. Heimdallur joins their Docker networks and calls each backend `/api/exact`.

## Notes

- `VITE_API_BASE_URL` is empty so the browser calls `/api` on the same origin. kvik nginx routes `/api/` → backend and `/` → web.
- Compose publishes `192.168.0.3:5175` and `192.168.0.3:8003` only (host LAN). Do not bind `0.0.0.0` — kvik nginx is the sole public entry.

## Deploying behind kvik nginx + Authentik

Live config: `kvik/deploy/nginx/conf.d/heimdallur.conf`.

1. Recreate this stack so ports bind to the LAN IP: `docker compose up -d`
2. Reload kvik nginx after pulling `heimdallur.conf`: `docker exec kvik-nginx-1 nginx -s reload`
3. Create/update the Authentik proxy provider (or run `configure-authentik-heimdallur.py` inside the authentik container).
