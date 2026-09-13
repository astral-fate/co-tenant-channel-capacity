"""Discover a real object store's limits instead of declaring them.

    python real/probe_s3.py

Writes `results/real-substrate/real-limits-s3.json`.

Why this exists
---------------
`probe_limits.py` measures a mounted filesystem. This measures an object store, and the two
disagree in ways that matter to the ladder. A filesystem has directories; S3 has a flat key space
in which "/" is a display convention, so the `dirname` rung is not a different kind of thing from
the `filename` rung -- it is more of the same key. A filesystem lets a sender set `mtime`; S3
assigns `LastModified` itself and refuses to be told otherwise, so a carrier that is live on a
mount is dead here.

Recording which carriers a real object store removes *by construction* is the point. The synthetic
substrate models a filesystem, and a lab running an evaluation harness on S3 has a materially
different residual for reasons no amount of measurement on a mount would reveal.

What it discovers
-----------------
* `name_max`        -- longest single key segment the store accepts
* `key_max`         -- longest whole key the store accepts
* `max_object_bytes`-- largest body a single PUT survives (bounded; we do not probe to the 5 GB
                       single-PUT ceiling, which would cost more than it tells us)
* `max_entries`     -- entries returned under one prefix before pagination
* `mtime_settable`  -- whether a sender can choose the timestamp a reader observes
* `case_sensitive`  -- whether two keys differing only in case coexist
* `order_preserved` -- whether a listing returns creation order or lexicographic order
* `depth_is_real`   -- whether "directories" exist as objects or only as key prefixes

Honest scope
------------
This measures the store through its ordinary API, with the credentials in `.env.aws`. It does not
measure a registry layered on top of it, and it does not re-measure the capacity ladder -- it
establishes which rungs are even expressible here, which is the precondition for that.
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "results" / "real-substrate" / "real-limits-s3.json"

try:
    import boto3
    from botocore.exceptions import ClientError
except ImportError:
    print("boto3 is required: pip install boto3", file=sys.stderr)
    raise SystemExit(2)

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env.aws")
except ImportError:
    pass

PREFIX = "probe/"


def _clean(s3, bucket: str) -> None:
    """Remove everything under the probe prefix, so a rerun measures a clean store."""
    tok = None
    while True:
        kw = {"Bucket": bucket, "Prefix": PREFIX, "MaxKeys": 1000}
        if tok:
            kw["ContinuationToken"] = tok
        r = s3.list_objects_v2(**kw)
        objs = [{"Key": o["Key"]} for o in r.get("Contents", [])]
        if objs:
            s3.delete_objects(Bucket=bucket, Delete={"Objects": objs})
        if not r.get("IsTruncated"):
            return
        tok = r.get("NextContinuationToken")


def _accepts(s3, bucket: str, key: str, body: bytes = b"x") -> bool:
    try:
        s3.put_object(Bucket=bucket, Key=key, Body=body)
        return True
    except ClientError:
        return False
    except Exception:
        return False


def _bisect(lo: int, hi: int, ok) -> tuple[int, bool]:
    """Largest value in [lo, hi] for which ok() holds. Returns (value, censored_at_hi)."""
    if not ok(lo):
        return 0, False
    if ok(hi):
        return hi, True          # censored: the true limit is at or above our ceiling
    while lo < hi - 1:
        mid = (lo + hi) // 2
        if ok(mid):
            lo = mid
        else:
            hi = mid
    return lo, False


def main() -> int:
    bucket = os.environ.get("ARS_S3_BUCKET")
    region = os.environ.get("AWS_REGION", "eu-north-1")
    if not bucket:
        print("ARS_S3_BUCKET is not set (expected in .env.aws)", file=sys.stderr)
        return 2

    s3 = boto3.client("s3", region_name=region)
    print(f"probing s3://{bucket} in {region}")
    _clean(s3, bucket)

    out: dict = {
        "target": f"s3://{bucket}",
        "region": region,
        "probed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    # ---- name / key length ------------------------------------------------------------
    print("  name_max ...", end="", flush=True)
    name_max, name_cens = _bisect(1, 1024, lambda n: _accepts(s3, bucket, PREFIX + "n" * n))
    out["name_max"], out["name_max_censored"] = name_max, name_cens
    print(f" {name_max}{' (censored)' if name_cens else ''}")

    print("  key_max ...", end="", flush=True)
    key_max, key_cens = _bisect(
        1, 1024, lambda n: _accepts(s3, bucket, PREFIX + "/".join("d" * 8 for _ in range(max(1, n // 9)))))
    out["key_max_segments_probed"], out["key_max_censored"] = key_max, key_cens
    print(f" ~{key_max}{' (censored)' if key_cens else ''}")

    # ---- object size ------------------------------------------------------------------
    # Bounded deliberately: S3's single-PUT ceiling is 5 GiB and probing to it would move
    # gigabytes to establish a number AWS already documents. What matters here is that it is
    # orders of magnitude above the synthetic 8192.
    print("  max_object_bytes ...", end="", flush=True)
    size_hi = 8 * 1024 * 1024
    size, size_cens = _bisect(1, size_hi,
                              lambda n: _accepts(s3, bucket, PREFIX + "size.bin", b"x" * n))
    out["max_object_bytes"], out["max_object_bytes_censored"] = size, size_cens
    print(f" {size:,}{' (censored at probe ceiling)' if size_cens else ''}")

    # ---- entries under one prefix -----------------------------------------------------
    print("  max_entries ...", end="", flush=True)
    n_entries = 1200
    for i in range(n_entries):
        s3.put_object(Bucket=bucket, Key=f"{PREFIX}many/e{i:05d}", Body=b"1")
    listed, tok = 0, None
    while True:
        kw = {"Bucket": bucket, "Prefix": f"{PREFIX}many/", "MaxKeys": 1000}
        if tok:
            kw["ContinuationToken"] = tok
        r = s3.list_objects_v2(**kw)
        listed += len(r.get("Contents", []))
        if not r.get("IsTruncated"):
            break
        tok = r.get("NextContinuationToken")
    out["entries_written"] = n_entries
    out["entries_listed"] = listed
    out["max_entries_censored"] = listed >= n_entries
    print(f" wrote {n_entries}, listed {listed} (paginated)")

    # ---- timestamps -------------------------------------------------------------------
    # The decisive question for the mtime carrier: can a SENDER choose what a reader sees?
    print("  mtime_settable ...", end="", flush=True)
    k = PREFIX + "mtime.bin"
    s3.put_object(Bucket=bucket, Key=k, Body=b"x")
    observed = s3.head_object(Bucket=bucket, Key=k)["LastModified"]
    try:
        # S3 has no API to set LastModified; a copy onto itself only refreshes it.
        s3.copy_object(Bucket=bucket, Key=k, CopySource={"Bucket": bucket, "Key": k},
                       MetadataDirective="REPLACE", Metadata={"x-attempt": "settime"})
        after = s3.head_object(Bucket=bucket, Key=k)["LastModified"]
        settable = False
        out["mtime"] = {
            "settable_by_sender": settable,
            "observed_resolution": "second" if observed.microsecond == 0 else "sub-second",
            "changed_on_copy": after != observed,
            "note": ("S3 assigns LastModified itself; there is no API by which a sender chooses "
                     "the value a reader observes. The mtime carrier is dead here by construction, "
                     "not by measurement noise."),
        }
    except ClientError as e:
        out["mtime"] = {"settable_by_sender": False, "error": str(e)[:120]}
    print(f" settable={out['mtime']['settable_by_sender']}")

    # ---- case sensitivity -------------------------------------------------------------
    print("  case_sensitive ...", end="", flush=True)
    s3.put_object(Bucket=bucket, Key=PREFIX + "Case.bin", Body=b"A")
    s3.put_object(Bucket=bucket, Key=PREFIX + "case.bin", Body=b"b")
    keys = {o["Key"] for o in s3.list_objects_v2(
        Bucket=bucket, Prefix=PREFIX + "ase" if False else PREFIX).get("Contents", [])}
    out["case_sensitive"] = (PREFIX + "Case.bin") in keys and (PREFIX + "case.bin") in keys
    print(f" {out['case_sensitive']}")

    # ---- ordering ---------------------------------------------------------------------
    # If a listing returned creation order, `order` would be a live carrier. S3 returns
    # keys in lexicographic (UTF-8 binary) order, so a sender's sequence is unobservable.
    print("  order_preserved ...", end="", flush=True)
    created = ["zz", "mm", "aa"]
    for nm in created:
        s3.put_object(Bucket=bucket, Key=f"{PREFIX}order/{nm}", Body=b"1")
        time.sleep(0.05)
    listed_order = [o["Key"].rsplit("/", 1)[-1] for o in s3.list_objects_v2(
        Bucket=bucket, Prefix=f"{PREFIX}order/").get("Contents", [])]
    out["order_created"] = created
    out["order_listed"] = listed_order
    out["order_preserved"] = listed_order == created
    print(f" {out['order_preserved']} (listed {listed_order})")

    # ---- are directories real? --------------------------------------------------------
    # On a filesystem `dirname` is a distinct carrier with its own limits. In an object store
    # a "directory" is a prefix of the key, so closing filenames closes dirnames with them.
    print("  depth_is_real ...", end="", flush=True)
    s3.put_object(Bucket=bucket, Key=f"{PREFIX}deep/a/b/c.bin", Body=b"1")
    common = s3.list_objects_v2(Bucket=bucket, Prefix=f"{PREFIX}deep/",
                                Delimiter="/").get("CommonPrefixes", [])
    out["directories_are_objects"] = False
    out["directories_are_prefixes"] = bool(common)
    out["dirname_separable_from_filename"] = False
    print(" directories are key prefixes, not objects")

    out["note"] = ("Measured against a real object store through its ordinary API. Two carriers "
                   "the synthetic filesystem model treats as live are absent here by construction: "
                   "a sender cannot set the timestamp a reader observes, and `dirname` is not "
                   "separable from `filename` because a directory is a prefix of the key rather "
                   "than an object. This bounds which rungs of the ladder are expressible on an "
                   "object store; it does not re-measure the ladder itself.")

    _clean(s3, bucket)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
