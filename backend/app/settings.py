import os


def _url(name: str, default: str) -> str:
    return os.getenv(name, default).rstrip("/")


LBL_API_URL = _url("LBL_API_URL", "http://192.168.0.3:8001")
DOMAR_API_URL = _url("DOMAR_API_URL", "http://192.168.0.3:8002")
ST_API_URL = _url("ST_API_URL", "http://192.168.0.3:8004")
LBL_PUBLIC_URL = _url("LBL_PUBLIC_URL", "https://lbl.dsna.codes")
DOMAR_PUBLIC_URL = _url("DOMAR_PUBLIC_URL", "https://judgements.dsna.codes")
ST_PUBLIC_URL = _url("ST_PUBLIC_URL", "https://stjornartidindi.dsna.codes")
SEARCH_TIMEOUT_SECONDS = float(os.getenv("SEARCH_TIMEOUT_SECONDS", "60"))
USER_AGENT = os.getenv("USER_AGENT", "heimdallur/1.0")
