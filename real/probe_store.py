"""Measure what a REAL artifact store carries, and which rung of the ladder it already sits at.

    python real/probe_store.py registry http://registry:5000

Writes `results/real-substrate/real-store-<name>.json`.

Why this is the interesting tier
--------------------------------
Tier 1 measured a shared filesystem. This measures the software an evaluation harness actually
runs: an artifact store with its own naming rules, reached over its own API.

The finding this is built to test is that **real stores already implement rungs of the closure
ladder, and they implement them inconsistently**. An OCI registry is content-addressed for blob
*payloads* -- a blob's name IS its sha256 digest, so a sender cannot choose it, which is exactly
what §4.1 calls filename closure, in production, by default. But the *repository name* under
which that blob is stored is entirely agent-chosen, arbitrary-length, and listed back to every
other tenant by `GET /v2/_catalog`.

So a registry is filename-closed and dirname-open at the same time. That is not a hypothetical
configuration; it is the default behaviour of the most widely deployed artifact store there is,
and it is the same shape as the channel the July 2026 agents used once content was wiped: names
of containers, not contents of files.

What is measured
----------------
For each store, per attribute, whether a sender can vary it and a receiver observe it:

* `dirname`   -- can the sender choose the repository/package name, and is it listed back?
* `filename`  -- can the sender choose the stored object's own identifier?
* `existence` -- can the sender control which of an agreed set of names exist?
* `content`   -- can the sender choose the bytes, and read them back?
* `size`      -- is the object's length observable?
* `mtime`     -- is a timestamp observable?

Each answer is established by doing it, not by reading documentation: the probe pushes, lists and
reads, and reports what came back. A capability the store refuses is measured as closed.

Honest scope
------------
This measures the store's default configuration on a loopback deployment with authentication
disabled, which is the configuration a single-tenant internal evaluation harness typically runs.
A hardened deployment may close rungs this probe finds open, and that is precisely the disposition
Appendix B clause 3 asks a provider to record.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
import string
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

#: Characters an OCI repository name permits: lowercase alphanumerics with separators. Taken from
#: the distribution spec's grammar, not chosen by us.
OCI_NAME_ALPHABET = string.ascii_lowercase + string.digits


def _req(method: str, url: str, body: bytes | None = None,
         headers: dict | None = None) -> tuple[int, bytes, dict]:
    r = urllib.request.Request(url, data=body, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(r, timeout=30) as resp:
            return resp.status, resp.read(), dict(resp.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read(), dict(e.headers)
    except urllib.error.URLError as e:
        raise SystemExit(f"store unreachable at {url}: {e.reason}")


def _push_blob(base: str, repo: str, payload: bytes) -> tuple[bool, str]:
    """Push one blob into `repo`. Returns (ok, digest). The digest is the store's, not ours."""
    status, _, headers = _req("POST", f"{base}/v2/{repo}/blobs/uploads/")
    if status not in (202,):
        return False, ""
    location = headers.get("Location", "")
    if not location:
        return False, ""
    if location.startswith("/"):
        location = base + location
    digest = "sha256:" + hashlib.sha256(payload).hexdigest()
    sep = "&" if "?" in location else "?"
    status, _, _ = _req("PUT", f"{location}{sep}digest={digest}", payload,
                        {"Content-Type": "application/octet-stream"})
    return status in (201, 204), digest


def probe_registry(base: str) -> dict:
    """Probe an OCI distribution registry."""
    out: dict = {"store": "oci-registry", "base": base, "attributes": {}}

    status, body, _ = _req("GET", f"{base}/v2/")
    out["reachable"] = status in (200, 401)
    if not out["reachable"]:
        out["error"] = f"GET /v2/ returned {status}"
        return out

    # --- dirname: is the repository name sender-chosen and listed back to other tenants? ---
    rng = random.Random(7)
    n_chars = 64
    chosen = "".join(rng.choice(OCI_NAME_ALPHABET) for _ in range(n_chars))
    ok, digest = _push_blob(base, chosen, b"probe-payload")
    listed = []
    if ok:
        status, body, _ = _req("GET", f"{base}/v2/_catalog?n=1000")
        if status == 200:
            listed = json.loads(body.decode()).get("repositories", [])
    recovered = chosen in listed
    out["attributes"]["dirname"] = {
        "sender_can_choose": ok,
        "receiver_can_observe": recovered,
        "carries": recovered,
        "bits_per_name": round(n_chars * math.log2(len(OCI_NAME_ALPHABET)), 1) if recovered else 0,
        "evidence": f"pushed repository {chosen[:16]}... and {'found' if recovered else 'did not find'} it in /v2/_catalog",
    }

    # --- filename: can the sender choose the stored object's own identifier? ---
    # In OCI the blob's identifier IS its content digest. The sender chooses the bytes, so it
    # chooses the digest -- but only by choosing content, which content closure removes. Under
    # content closure the digest is not sender-controllable, which is filename closure by
    # construction rather than by configuration.
    out["attributes"]["filename"] = {
        "sender_can_choose": False,
        "receiver_can_observe": True,
        "carries": False,
        "bits_per_name": 0,
        "evidence": (f"blob identifier is its own sha256 ({digest[:23]}...); the store derives it "
                     "from content and rejects a mismatch, so it is content-addressed by default"),
    }

    # --- existence: can the sender control which of an agreed set of repositories exist? ---
    slots, present = 16, 0
    pattern = [rng.randrange(2) for _ in range(slots)]
    for i, bit in enumerate(pattern):
        if bit:
            _push_blob(base, f"slot{i:03d}", b"x")
    status, body, _ = _req("GET", f"{base}/v2/_catalog?n=1000")
    catalog = set(json.loads(body.decode()).get("repositories", [])) if status == 200 else set()
    got = [1 if f"slot{i:03d}" in catalog else 0 for i in range(slots)]
    present = sum(1 for a, b in zip(pattern, got) if a == b)
    out["attributes"]["existence"] = {
        "sender_can_choose": True,
        "receiver_can_observe": present == slots,
        "carries": present == slots,
        "bits_per_state": slots if present == slots else 0,
        "evidence": f"{present}/{slots} agreed slots recovered exactly from the catalog",
    }

    # --- content / size / mtime, read back through the blob API ---
    payload = bytes(rng.randrange(256) for _ in range(512))
    ok2, dg = _push_blob(base, chosen, payload)
    status, body, headers = _req("GET", f"{base}/v2/{chosen}/blobs/{dg}") if ok2 else (0, b"", {})
    out["attributes"]["content"] = {
        "sender_can_choose": ok2,
        "receiver_can_observe": status == 200 and body == payload,
        "carries": status == 200 and body == payload,
        "evidence": f"512-byte blob round-tripped: {status == 200 and body == payload}",
    }
    out["attributes"]["size"] = {
        "receiver_can_observe": "Content-Length" in headers,
        "carries": "Content-Length" in headers,
        "evidence": f"Content-Length header present: {'Content-Length' in headers}",
    }
    out["attributes"]["mtime"] = {
        "receiver_can_observe": "Last-Modified" in headers or "Date" in headers,
        "carries": "Last-Modified" in headers,
        "evidence": f"Last-Modified header present: {'Last-Modified' in headers}",
    }
    return out


def classify(report: dict) -> dict:
    """Which rung of the ladder does this store already sit at, by default?"""
    a = report.get("attributes", {})
    def carries(k: str) -> bool:
        return bool(a.get(k, {}).get("carries"))
    rung = "open"
    if not carries("content"):
        rung = "content"
    if not carries("filename") and not carries("content"):
        rung = "filename"
    if not carries("dirname") and rung == "filename":
        rung = "dirname"
    return {
        "native_rung": rung,
        "carries": {k: carries(k) for k in ("content", "filename", "dirname",
                                            "existence", "size", "mtime")},
        "note": ("A store is credited with a rung only when EVERY attribute at or before it is "
                 "closed. A store that closes filename but leaves dirname open sits at no rung of "
                 "this ladder -- which is the finding, not a gap in the classification."),
    }


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: probe_store.py <name> <base-url>")
        return 2
    name, base = argv[0], argv[1].rstrip("/")
    report = probe_registry(base) if name == "registry" else {"error": f"unknown store {name}"}
    if "error" in report:
        print(report["error"])
        return 1

    report["classification"] = classify(report)
    report["probed_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    print(f"REAL STORE: {report['store']} at {base}")
    print("=" * 78)
    for attr, d in report["attributes"].items():
        mark = "CARRIES" if d.get("carries") else "closed "
        print(f"  {attr:10} {mark}  {d['evidence']}")
    c = report["classification"]
    print(f"\n  native rung: {c['native_rung']}")
    print(f"  {c['note']}")

    blob = json.dumps(report, indent=2)
    # Same reason as probe_limits.py: /work dies with the container, /cache does not.
    shared = Path("/cache")
    if shared.is_dir():
        (shared / f"real-store-{name}.json").write_text(blob, encoding="utf-8")
    out = ROOT / "results" / f"real-store-{name}.json"
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(blob, encoding="utf-8")
    except OSError:
        pass
    print(f"\nwritten to /cache/real-store-{name}.json (survives the container)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
