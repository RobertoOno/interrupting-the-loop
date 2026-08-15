#!/usr/bin/env python3
"""Watch macOS thermal pressure during long local runs — no root needed.

Reads NSProcessInfo.thermalState, the same signal macOS uses to decide
CPU/GPU throttling: nominal < fair < serious (already throttling) <
critical. Prints one line per sample and one alert line on level changes.

    python scripts/thermal_watch.py --interval 60
"""

from __future__ import annotations

import argparse
import ctypes
import ctypes.util
import time
from datetime import datetime

LEVELS = {0: "nominal", 1: "fair", 2: "serious", 3: "critical"}


def thermal_state() -> int:
    ctypes.cdll.LoadLibrary(ctypes.util.find_library("Foundation"))
    objc = ctypes.cdll.LoadLibrary(ctypes.util.find_library("objc"))
    objc.objc_getClass.restype = ctypes.c_void_p
    objc.sel_registerName.restype = ctypes.c_void_p
    objc.objc_msgSend.restype = ctypes.c_void_p
    objc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    info = objc.objc_msgSend(
        objc.objc_getClass(b"NSProcessInfo"), objc.sel_registerName(b"processInfo")
    )
    objc.objc_msgSend.restype = ctypes.c_long
    return int(objc.objc_msgSend(info, objc.sel_registerName(b"thermalState")))


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--interval", type=float, default=60.0)
    p.add_argument("--once", action="store_true")
    args = p.parse_args()
    last = None
    while True:
        state = thermal_state()
        name = LEVELS.get(state, str(state))
        stamp = datetime.now().strftime("%H:%M:%S")
        if state != last:
            tag = "ALERT" if state >= 2 else ("warm" if state == 1 else "ok")
            print(f"{stamp} thermal {name} [{tag}]", flush=True)
            last = state
        else:
            print(f"{stamp} thermal {name}", flush=True)
        if args.once:
            break
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
