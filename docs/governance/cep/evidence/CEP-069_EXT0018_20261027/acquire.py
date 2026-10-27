"""Preserve direct official-endpoint acquisition results; never substitute rates."""

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

OUT = Path(__file__).resolve().parent
TARGETS = [
    ("Iranian National Tax Administration", "https://intamedia.ir/"),
    ("Iranian National Tax Administration", "https://www.intamedia.ir/"),
    ("Iranian National Tax Administration", "https://tax.gov.ir/"),
    ("Social Security Organization", "https://tamin.ir/"),
    ("Social Security Organization", "https://news.tamin.ir/news/item/197893"),
    ("Ministry of Cooperatives Labour and Social Welfare", "https://mcls.gov.ir/"),
    ("Ministry of Cooperatives Labour and Social Welfare", "https://rkj.mcls.gov.ir/"),
    ("Parliament Research Center", "https://rc.majlis.ir/"),
    ("National laws and regulations portal", "https://qavanin.ir/"),
    ("Official Gazette", "https://rrk.ir/"),
    ("Government laws and regulations information portal", "https://dotic.ir/"),
]


def fetch(target):
    issuer, url = target
    row = {
        "issuing_body_candidate": issuer,
        "requested_url": url,
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "statutory_authority_verified": False,
        "values_extracted": False,
        "effective_from": None,
        "effective_to": None,
        "applicability": "Endpoint discovery only; not an authenticated statutory document.",
    }
    try:
        request = Request(
            url, headers={"User-Agent": "Mozilla/5.0 BONIRA-evidence-intake"}
        )
        with urlopen(request, timeout=12) as response:
            data = response.read(4_000_001)
            row.update(
                status=response.status,
                final_url=response.url,
                content_type=response.headers.get("Content-Type"),
                bytes=len(data),
            )
            if len(data) > 4_000_000:
                row["result"] = "RESPONSE_OVER_DISCOVERY_LIMIT"
                return row
            filename = (
                "endpoint_" + hashlib.sha256(url.encode()).hexdigest()[:12] + ".bin"
            )
            (OUT / filename).write_bytes(data)
            row.update(
                artifact=filename,
                sha256=hashlib.sha256(data).hexdigest(),
                result="RETRIEVED_ENDPOINT_REQUIRES_CONTENT_QUALIFICATION",
            )
    except HTTPError as error:
        row.update(result="HTTP_ERROR", status=error.code)
    except (URLError, TimeoutError, OSError) as error:
        # Exception classes only: proxy/network diagnostics can contain credentials.
        row.update(result="TRANSPORT_UNAVAILABLE", error_type=type(error).__name__)
    return row


with ThreadPoolExecutor(max_workers=6) as pool:
    results = list(pool.map(fetch, TARGETS))
(OUT / "ACQUISITION.json").write_text(
    json.dumps(
        {
            "method": "Direct HTTPS with TLS verification; independent of search/browser retrieval",
            "results": results,
            "activation": "NOT_EXECUTED",
            "official_package": "NOT_YET_QUALIFIED",
        },
        indent=2,
    )
    + "\n",
    encoding="utf-8",
)
print(
    json.dumps(
        [
            {k: row[k] for k in ("requested_url", "result", "status") if k in row}
            for row in results
        ]
    )
)
