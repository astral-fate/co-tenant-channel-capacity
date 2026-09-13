"""Hardware autoconfiguration for `TransformersProvider`, tested without a GPU.

    python runner/test_autoconfig.py

The decision this covers cannot be exercised on the development machine -- it has no CUDA torch
at all -- and it is exactly the kind of choice that fails silently: loading 4-bit on an A100
produces correct output at roughly a third of the achievable speed, which looks like a slow
model rather than a misconfiguration. A stub device makes the branch testable anywhere.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from providers import TransformersProvider  # noqa: E402


class _Props:
    def __init__(self, name, gib, major, minor=0):
        self.name = name
        self.total_memory = int(gib * 1024 ** 3)
        self.major = major
        self.minor = minor


class _Backends:
    class cuda:
        class matmul:
            allow_tf32 = False

    class cudnn:
        allow_tf32 = False


class _Torch:
    """The minimum surface `autoconfig` touches."""

    def __init__(self, props, bf16, available=True):
        self._props = props
        self._bf16 = bf16
        self._available = available
        self.backends = _Backends()

        outer = self

        class _Cuda:
            @staticmethod
            def is_available():
                return outer._available

            @staticmethod
            def get_device_properties(_):
                return outer._props

            @staticmethod
            def is_bf16_supported():
                return outer._bf16

        self.cuda = _Cuda()


A100_40 = _Torch(_Props("NVIDIA A100-SXM4-40GB", 39.6, 8, 0), bf16=True)
A100_80 = _Torch(_Props("NVIDIA A100-SXM4-80GB", 79.2, 8, 0), bf16=True)
T4 = _Torch(_Props("Tesla T4", 14.7, 7, 5), bf16=False)
L4 = _Torch(_Props("NVIDIA L4", 22.5, 8, 9), bf16=True)
CPU = _Torch(None, bf16=False, available=False)

CHECKS: list[tuple[str, bool]] = []


def check(label: str, cond: bool) -> None:
    CHECKS.append((label, bool(cond)))


def _clear_env() -> None:
    for k in ("ARS_LOAD_4BIT", "ARS_DTYPE", "ARS_ATTN"):
        os.environ.pop(k, None)


def main() -> int:
    _clear_env()

    a40 = TransformersProvider.autoconfig(A100_40)
    check("A100-40 does not quantise", a40["load_in_4bit"] is False)
    check("A100-40 uses bfloat16", a40["dtype"] == "bfloat16")
    check("A100-40 uses SDPA attention", a40["attn"] == "sdpa")
    check("A100-40 enables TF32 matmul", A100_40.backends.cuda.matmul.allow_tf32 is True)

    a80 = TransformersProvider.autoconfig(A100_80)
    check("A100-80 does not quantise", a80["load_in_4bit"] is False)

    t4 = TransformersProvider.autoconfig(T4)
    check("T4 quantises to 4-bit", t4["load_in_4bit"] is True)
    check("T4 uses float16, having no bf16", t4["dtype"] == "float16")
    check("T4 uses eager attention", t4["attn"] == "eager")

    # An L4 is Ampere-class but only 22.5 GiB: bf16 8B weights plus KV cache would not fit
    # comfortably, so it must still quantise even though its compute capability allows SDPA.
    l4 = TransformersProvider.autoconfig(L4)
    check("L4 quantises despite being Ampere", l4["load_in_4bit"] is True)
    check("L4 still uses bfloat16 and SDPA",
          l4["dtype"] == "bfloat16" and l4["attn"] == "sdpa")

    cpu = TransformersProvider.autoconfig(CPU)
    check("no CUDA falls back to fp32 eager",
          cpu["load_in_4bit"] is False and cpu["dtype"] == "float32"
          and cpu["attn"] == "eager")

    # Overrides
    os.environ["ARS_LOAD_4BIT"] = "1"
    check("ARS_LOAD_4BIT=1 forces quantisation on an A100",
          TransformersProvider.autoconfig(A100_40)["load_in_4bit"] is True)
    os.environ["ARS_LOAD_4BIT"] = "0"
    check("ARS_LOAD_4BIT=0 forces it off on a T4",
          TransformersProvider.autoconfig(T4)["load_in_4bit"] is False)
    _clear_env()

    os.environ["ARS_DTYPE"] = "float16"
    check("ARS_DTYPE overrides the detected dtype",
          TransformersProvider.autoconfig(A100_40)["dtype"] == "float16")
    _clear_env()

    os.environ["ARS_ATTN"] = "eager"
    check("ARS_ATTN overrides the detected kernel",
          TransformersProvider.autoconfig(A100_40)["attn"] == "eager")
    _clear_env()

    check("the bf16 floor sits above 8B bf16 weights (~16 GiB)",
          TransformersProvider.BF16_VRAM_FLOOR_GIB >= 20)

    width = max(len(label) for label, _ in CHECKS)
    for label, ok in CHECKS:
        print(f"  {'ok  ' if ok else 'FAIL'} {label:<{width}}")
    failed = [label for label, ok in CHECKS if not ok]
    print(f"\n{len(CHECKS) - len(failed)}/{len(CHECKS)} checks pass")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
