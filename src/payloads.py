"""Externally fixed payload sizes, so the residual is compared against something we did not set.

    python src/payloads.py

Writes `results/capacity/payloads.json`.

Why this exists
---------------
The paper reported its residual as a multiple of the benchmark task's passcode. A reviewer put
the objection precisely: the substrate's parameters are author-chosen and so is the passcode, so
both sides of that ratio are set by the same hand and the multiplier is partly circular.

The fix is not to drop the comparison but to anchor it to payloads whose sizes are fixed by
somebody else -- credential and identifier formats defined by third parties, of the kind the
July 2026 incident actually moved between agents. Nobody involved in this study chose how many
bits are in a UUID.

Each entry below records the size, its derivation, and the authority that fixes it. Sizes are the
information content an attacker must move to convey the secret, not the on-wire encoding length:
a UUIDv4 is 36 printable characters but only 122 bits are random, and it is the 122 that a
receiver must recover.

What this does NOT claim
------------------------
That any of these specific secrets moved in the incident. The public record says agents exchanged
"credentials, commands and results"; it does not enumerate formats. These are reference points for
"what does a real secret cost in bits", chosen for having externally fixed sizes, not evidence
about what was sent.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


@dataclass
class Payload:
    name: str
    bits: float
    derivation: str
    authority: str

    def as_dict(self) -> dict:
        return asdict(self)


def _b(n_symbols: int, alphabet: int) -> float:
    return n_symbols * math.log2(alphabet)


PAYLOADS: list[Payload] = [
    Payload(
        "IPv4 address and port",
        32 + 16,
        "32-bit address plus a 16-bit port number.",
        "RFC 791; RFC 793",
    ),
    Payload(
        "AWS access key ID",
        _b(16, 32),
        "20 characters, of which a fixed 4-character prefix ('AKIA') is not information; the "
        "remaining 16 are base32.",
        "AWS IAM identifier format",
    ),
    Payload(
        "UUID version 4",
        122,
        "128 bits less 4 version bits and 2 variant bits, which are fixed by the standard.",
        "RFC 4122 section 4.4",
    ),
    Payload(
        "GitHub personal access token",
        _b(36, 62),
        "36 base62 characters following a fixed 'ghp_' prefix that carries no information.",
        "GitHub token format",
    ),
    Payload(
        "Ed25519 public key",
        256,
        "A 32-byte group element.",
        "RFC 8032",
    ),
]


def main() -> int:
    rows = [p.as_dict() for p in PAYLOADS]
    smallest = min(PAYLOADS, key=lambda p: p.bits)
    largest = max(PAYLOADS, key=lambda p: p.bits)

    report = {
        "note": ("Payload sizes fixed by third-party specifications, used so the residual is not "
                 "compared only against a quantity this study defined. Not a claim about what "
                 "the July 2026 incident actually transmitted."),
        "payloads": rows,
        "smallest": {"name": smallest.name, "bits": smallest.bits},
        "largest": {"name": largest.name, "bits": largest.bits},
    }

    out = ROOT / "results" / "capacity" / "payloads.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("EXTERNALLY FIXED PAYLOAD SIZES")
    print("=" * 78)
    for p in PAYLOADS:
        print(f"  {p.name:32} {p.bits:>7.0f} bits   [{p.authority}]")
        print(f"  {'':32} {p.derivation}")
    print(f"\nwritten to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
