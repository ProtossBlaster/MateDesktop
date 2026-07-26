"""Close the app at the exact instant the services are restarting, many times over.

That is the moment that produced the ghost: the old processes were told to stop while new
ones were already being started, and the newcomers outlived the app. Each round fires stop()
from a competing thread at a randomised point in the startup, then checks that nothing is left.
"""
import os, pathlib, random, subprocess, sys, threading, time
sys.path.insert(0, "mate_desktop")
os.environ["MATE_SKIP_UPDATE"] = "1"
os.environ["MATE_APP_DIR"] = str(pathlib.Path("racetest").resolve())
import launcher

leaked = 0
for r in range(1, 9):
    svc = launcher.Services(fresh_payload=False)
    svc.start()
    # stop() lands anywhere between "about to spawn" and "just spawned"
    delay = random.uniform(0.05, 2.5)
    threading.Timer(delay, svc.stop).start()
    svc.join(timeout=45)
    time.sleep(1.5)
    out = subprocess.run(["pgrep", "-f", "mate-child|payload/current"],
                         capture_output=True, text=True).stdout.strip()
    alive = [p for p in out.splitlines() if p]
    status = "OK " if not alive else "!! FANTASMA"
    if alive:
        leaked += 1
        subprocess.run(["kill"] + alive)
    print(f"{status} round {r}: stop dopo {delay:.2f}s — processi rimasti: {len(alive)}", flush=True)

print(f"\nRISULTATO: {leaked} fantasmi su 8 round")
