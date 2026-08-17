from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from typing import Any
from urllib.parse import urlparse

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from app.exact import parse_person_query
from app.settings import (
    DOMAR_API_URL,
    DOMAR_PUBLIC_URL,
    LBL_API_URL,
    LBL_PUBLIC_URL,
    SEARCH_TIMEOUT_SECONDS,
    USER_AGENT,
)

app = FastAPI(title="Heimdallur")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _client() -> httpx.Client:
    return httpx.Client(
        headers={"User-Agent": USER_AGENT},
        timeout=SEARCH_TIMEOUT_SECONDS,
        follow_redirects=True,
    )


def _upstream_error_detail(resp: httpx.Response) -> str:
    try:
        data = resp.json()
        detail = data.get("detail")
        if isinstance(detail, str) and detail.strip():
            return detail
    except Exception:
        pass
    return f"Upstream HTTP {resp.status_code}"


def _fetch_exact(base: str, q: str, limit: int) -> dict[str, Any]:
    url = f"{base}/api/exact"
    try:
        with _client() as client:
            resp = client.get(url, params={"q": q, "limit": limit})
    except httpx.HTTPError as e:
        raise RuntimeError(f"unreachable ({e})") from e
    if resp.status_code == 400:
        raise ValueError(_upstream_error_detail(resp))
    if resp.status_code >= 400:
        raise RuntimeError(_upstream_error_detail(resp))
    data = resp.json()
    if not isinstance(data, dict):
        raise RuntimeError("unexpected response")
    return data


def _lbl_hits(payload: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for h in payload.get("hits") or []:
        year = h.get("year")
        out.append(
            {
                "source": "lbl",
                "source_label": "Lögbirtingablað",
                "id": str(h.get("errand_id")),
                "title": h.get("filename") or "LBL advert",
                "subtitle": h.get("issue_path") or "",
                "date": year,
                "year": year,
                "preview": h.get("preview") or "",
                "source_url": h.get("source_url"),
                "open_url": h.get("source_url"),
                "preview_kind": "lbl",
                "meta": {
                    "errand_type": h.get("errand_type"),
                    "errand_category": h.get("errand_category"),
                    "errand_action": h.get("errand_action"),
                    "filename": h.get("filename"),
                    "issue_path": h.get("issue_path"),
                },
            }
        )
    return out


def _domar_hits(payload: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for h in payload.get("hits") or []:
        vid = h.get("id")
        date = h.get("verdict_date")
        year = h.get("year") or ((date or "")[:4] or None)
        open_url = h.get("source_url") or (
            f"{DOMAR_PUBLIC_URL}/" if not vid else f"{DOMAR_PUBLIC_URL}/?id={vid}"
        )
        out.append(
            {
                "source": "domar",
                "source_label": "Dómar",
                "id": str(vid),
                "title": h.get("case_number") or str(vid),
                "subtitle": " · ".join(
                    p for p in (h.get("court"), h.get("title")) if p
                ),
                "date": date,
                "year": year,
                "preview": h.get("preview") or h.get("presentings") or "",
                "source_url": h.get("source_url"),
                "open_url": h.get("source_url") or open_url,
                "preview_kind": "domar",
                "meta": {
                    "court": h.get("court"),
                    "case_number": h.get("case_number"),
                    "title": h.get("title"),
                    "keywords": h.get("keywords") or [],
                    "has_pdf": bool(h.get("has_pdf")),
                    "verdict_date": date,
                },
            }
        )
    return out


def _sort_key(hit: dict[str, Any]) -> tuple:
    date = (hit.get("date") or hit.get("year") or "")[:10]
    return (date == "", date, hit.get("source") or "", hit.get("id") or "")


@app.get("/api/health")
def health() -> dict[str, Any]:
    indexes: dict[str, Any] = {}
    for name, base in (("lbl", LBL_API_URL), ("domar", DOMAR_API_URL)):
        try:
            with httpx.Client(timeout=5.0, headers={"User-Agent": USER_AGENT}) as client:
                resp = client.get(f"{base}/api/health")
            if resp.is_success:
                indexes[name] = resp.json()
            else:
                indexes[name] = {"status": "error", "http": resp.status_code}
        except httpx.HTTPError as e:
            indexes[name] = {"status": "unreachable", "error": str(e)}
    ok = all(
        isinstance(v, dict) and v.get("status") == "ok" for v in indexes.values()
    )
    return {"status": "ok" if ok else "degraded", "indexes": indexes}


@app.get("/api/search")
def search_api(q: str, limit: int = 200) -> dict[str, Any]:
    parsed = parse_person_query(q)
    if parsed.error:
        raise HTTPException(status_code=400, detail=parsed.error)

    limit = max(1, min(int(limit or 200), 500))
    warnings: list[str] = []
    lbl_payload: dict[str, Any] | None = None
    domar_payload: dict[str, Any] | None = None

    def _lbl() -> dict[str, Any]:
        return _fetch_exact(LBL_API_URL, parsed.raw, limit)

    def _domar() -> dict[str, Any]:
        return _fetch_exact(DOMAR_API_URL, parsed.raw, limit)

    with ThreadPoolExecutor(max_workers=2) as pool:
        fut_lbl = pool.submit(_lbl)
        fut_domar = pool.submit(_domar)
        try:
            lbl_payload = fut_lbl.result()
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        except RuntimeError as e:
            warnings.append(f"Lögbirtingablað: {e}")
        try:
            domar_payload = fut_domar.result()
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        except RuntimeError as e:
            warnings.append(f"Dómar: {e}")

    hits = []
    if lbl_payload:
        hits.extend(_lbl_hits(lbl_payload))
    if domar_payload:
        hits.extend(_domar_hits(domar_payload))
    hits.sort(key=_sort_key, reverse=True)

    by_source = {
        "lbl": 0 if not lbl_payload else int(lbl_payload.get("total") or 0),
        "domar": 0 if not domar_payload else int(domar_payload.get("total") or 0),
    }
    by_year: dict[str, int] = {}
    for h in hits:
        year = h.get("year")
        if year:
            by_year[str(year)] = by_year.get(str(year), 0) + 1

    bits = [
        f'{by_source["lbl"]} Lögbirtingablað',
        f'{by_source["domar"]} dómur/dómar',
    ]
    summary = f'Exact matches for “{parsed.raw}”: {len(hits)} ({", ".join(bits)}).'
    if parsed.kennitala:
        summary += f" Kennitala {parsed.kennitala}."
    if parsed.name:
        summary += " Full name is matched as a contiguous phrase (Icelandic case forms included)."

    return {
        "query": parsed.raw,
        "mode": parsed.mode,
        "kennitala": parsed.kennitala,
        "name": parsed.name,
        "total": len(hits),
        "by_source": by_source,
        "by_year": dict(sorted(by_year.items(), reverse=True)),
        "by_type": (lbl_payload or {}).get("by_type") or {},
        "by_court": (domar_payload or {}).get("by_court") or {},
        "hits": hits,
        "warnings": warnings,
        "summary": summary,
        "indexes": {
            "lbl": LBL_PUBLIC_URL,
            "domar": DOMAR_PUBLIC_URL,
        },
    }


def _assert_lbl_pdf_url(url: str) -> str:
    raw = (url or "").strip()
    if not raw:
        raise HTTPException(status_code=400, detail="Missing url")
    parsed = urlparse(raw)
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(status_code=400, detail="Invalid url scheme")
    host = (parsed.hostname or "").lower()
    if host != "files.logbirtingablad.is":
        raise HTTPException(status_code=400, detail="PDF host not allowed")
    if not (parsed.path or "").lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Not a PDF url")
    return raw


@app.get("/api/preview")
def preview_api(
    source: str = Query(..., description="lbl or domar"),
    url: str = Query("", description="LBL PDF URL"),
    id: str = Query("", description="island.is verdict id"),
):
    src = (source or "").strip().lower()
    if src == "lbl":
        pdf_url = _assert_lbl_pdf_url(url)
        upstream_url = f"{LBL_API_URL}/api/preview"
        params = {"url": pdf_url}
        filename = (urlparse(pdf_url).path.rsplit("/", 1)[-1] or "document.pdf")
    elif src == "domar":
        verdict_id = (id or "").strip()
        if not verdict_id or "/" in verdict_id or ".." in verdict_id:
            raise HTTPException(status_code=400, detail="Invalid id")
        upstream_url = f"{DOMAR_API_URL}/api/preview"
        params = {"id": verdict_id}
        filename = f"{verdict_id}.pdf"
    else:
        raise HTTPException(status_code=400, detail="source must be lbl or domar")

    try:
        client = httpx.Client(
            headers={"User-Agent": USER_AGENT},
            timeout=60.0,
            follow_redirects=True,
        )
        upstream = client.send(
            client.build_request("GET", upstream_url, params=params),
            stream=True,
        )
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Upstream fetch failed: {e}") from e

    if upstream.status_code >= 400:
        upstream.close()
        client.close()
        raise HTTPException(status_code=502, detail=f"Upstream HTTP {upstream.status_code}")

    content_type = upstream.headers.get("content-type") or "application/pdf"

    def iter_bytes():
        try:
            for chunk in upstream.iter_bytes():
                yield chunk
        finally:
            upstream.close()
            client.close()

    return StreamingResponse(
        iter_bytes(),
        media_type=content_type,
        headers={
            "Content-Disposition": f'inline; filename="{filename}"',
            "Cache-Control": "public, max-age=3600",
        },
    )


def main() -> None:
    import uvicorn

    uvicorn.run(
        "app.api:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
