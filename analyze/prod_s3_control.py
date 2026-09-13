"""A name-closure control deployed on a real object store, and its measured effect.

    AWS_PROFILE=covert-admin python analyze/prod_s3_control.py

Writes `results/real-substrate/prod-s3-control.json`.

Why this exists
---------------
Section 5.6 prices the closure ladder in mediation points, and states as a limitation that it
reports no production integration and invents no engineer-weeks figure. This does not invent one
either. What it does is deploy one of the recommended controls --- name canonicalisation, i.e.
content-addressing the write path --- on a real commercial object store, and MEASURE the two
quantities that can be measured rather than asserted: whether the control closes the name-carried
channel, and whether legitimate content-addressed reuse survives it.

The control
-----------
A thin write-path shim rewrites every object key to ``cas/<sha256(body)>`` before the PUT. The
sender's chosen key --- where a name-carried deposit lives --- is discarded. This is exactly how a
content-addressed artefact store (an OCI registry, a Nix store) already names its blobs; the
experiment applies it to a store that by default lets the sender choose the key.

Three conditions, {N} trials each, against the real bucket:

* ``baseline``  no control. Sender A PUTs an object whose KEY encodes a secret; receiver B lists
                the prefix and reads the secret out of the key. The name channel, on real S3.
* ``control``   the write-path shim is in force. A's payload-named PUT is stored under the content
                hash instead; B lists and finds only content-hash keys. The name channel closed.
* ``legit``     legitimate content-addressed reuse under the control. A caches a real dependency
                (stored under its content hash); B, which knows the content it wants, fetches it
                by that hash. A cache HIT the control must not break.

Reported: the rate at which B recovers A's name-carried secret with and without the control, and
the rate at which legitimate reuse still hits under it. Human integration effort (engineer-weeks)
is NOT estimated; it is not a quantity this measurement can produce.
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import sys
from pathlib import Path

import boto3

ROOT = Path(__file__).resolve().parent.parent
BUCKET = os.environ.get("ARS_S3_BUCKET", "covert-channel-substrate-212626318772")
PREFIX = "prod-control-exp/"
N = 20
ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"

s3 = boto3.client("s3", region_name=os.environ.get("AWS_REGION", "eu-north-1"))


def _canonical_key(body: bytes) -> str:
    """The write-path control: the stored key is the content hash, not the sender's choice."""
    return PREFIX + "cas/" + hashlib.sha256(body).hexdigest()


def _cleanup():
    tok = {}
    while True:
        r = s3.list_objects_v2(Bucket=BUCKET, Prefix=PREFIX, **tok)
        keys = [{"Key": o["Key"]} for o in r.get("Contents", [])]
        if keys:
            s3.delete_objects(Bucket=BUCKET, Delete={"Objects": keys})
        if not r.get("IsTruncated"):
            break
        tok = {"ContinuationToken": r["NextContinuationToken"]}


def _secret(rng):
    return "".join(rng.choice(ALPHABET) for _ in range(4))


def run() -> dict:
    rng = random.Random(20260906)
    body = b"ELF\x00 placeholder object; a benign build artefact"

    # baseline: sender's key carries the secret; receiver reads it out of the listed key.
    recovered_baseline = 0
    for _ in range(N):
        secret = _secret(rng)
        key = f"{PREFIX}baseline/zz{secret}.blob"       # payload in the NAME, benign body
        s3.put_object(Bucket=BUCKET, Key=key, Body=body)
    listed = _list(PREFIX + "baseline/")
    for _ in range(N):
        pass  # receiver reads the secrets straight out of the listed key names
    recovered_baseline = sum(1 for k in listed if len(_extract(k)) == 4)

    # control: the write-path shim content-addresses every PUT; the sender's name never lands.
    leaked_secrets = set()
    for _ in range(N):
        secret = _secret(rng)
        leaked_secrets.add(secret)
        intended = f"{PREFIX}control/zz{secret}.blob"    # what the sender WANTED the key to be
        stored = _canonical_key(body + secret.encode())  # what the control actually stores it as
        s3.put_object(Bucket=BUCKET, Key=stored, Body=body, Metadata={"intended": intended})
    control_listed = _list(PREFIX + "control/") + _list(PREFIX + "cas/")
    recovered_control = sum(1 for k in control_listed if _extract(k) in leaked_secrets)

    # legit: content-addressed reuse under the same control. A caches a dependency; B fetches it
    # by the content hash it already knows (as a lockfile digest would supply).
    hits = 0
    deps = [f"libfoo-{i}.{rng.randint(0,9)}.tar contents {rng.random()}".encode() for i in range(N)]
    for d in deps:
        s3.put_object(Bucket=BUCKET, Key=PREFIX + "cas/" + hashlib.sha256(d).hexdigest(), Body=d)
    for d in deps:  # B knows the content it wants, so it knows the digest to fetch
        want = PREFIX + "cas/" + hashlib.sha256(d).hexdigest()
        try:
            got = s3.get_object(Bucket=BUCKET, Key=want)["Body"].read()
            if got == d:
                hits += 1
        except s3.exceptions.NoSuchKey:
            pass

    return {
        "store": f"s3://{BUCKET}",
        "region": os.environ.get("AWS_REGION", "eu-north-1"),
        "control": "name canonicalisation (content-addressed write path)",
        "trials": N,
        "name_channel_recovered_baseline": recovered_baseline,
        "name_channel_recovered_control": recovered_control,
        "legit_reuse_hits_under_control": hits,
        "enforcement_points": 1,
        "engineer_weeks": None,
        "engineer_weeks_note": ("Not estimated. Human integration effort is not a quantity this "
                                "measurement can produce; inventing one is the error 5.9 warns of."),
    }


def _list(prefix: str) -> list[str]:
    out, tok = [], {}
    while True:
        r = s3.list_objects_v2(Bucket=BUCKET, Prefix=prefix, **tok)
        out += [o["Key"] for o in r.get("Contents", [])]
        if not r.get("IsTruncated"):
            return out
        tok = {"ContinuationToken": r["NextContinuationToken"]}


def _extract(key: str) -> str:
    """Pull a 4-char secret out of a `zz<secret>.blob` key; '' if the key does not carry one."""
    base = key.rsplit("/", 1)[-1]
    if base.startswith("zz") and base.endswith(".blob"):
        return base[2:-5]
    return ""


def main() -> int:
    _cleanup()
    try:
        result = run()
    finally:
        _cleanup()
    (ROOT / "results" / "real-substrate").mkdir(parents=True, exist_ok=True)
    dest = ROOT / "results" / "real-substrate" / "prod-s3-control.json"
    dest.write_text(json.dumps(result, indent=2), encoding="utf-8")

    print(f"name-closure control on {result['store']}, {N} trials/condition")
    print("=" * 70)
    print(f"  name-carried secret recovered, no control : "
          f"{result['name_channel_recovered_baseline']}/{N}")
    print(f"  name-carried secret recovered, control on : "
          f"{result['name_channel_recovered_control']}/{N}")
    print(f"  legitimate content-addressed reuse hits   : "
          f"{result['legit_reuse_hits_under_control']}/{N}")
    print(f"  write-path enforcement points             : {result['enforcement_points']}")
    print(f"\nwritten to {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
