"""Scope the unmodified install/control scripts to a disposable test project."""

import os
import sys

args = sys.argv[1:]
if args and args[0] == "compose":
    # The real scripts select this fixed single-site project. Isolate only in QA.
    if "-p" in args and args[args.index("-p") + 1] == "geo-monitor-collector":
        args[args.index("-p") + 1] = os.environ["ACCEPTANCE_COLLECTOR_PROJECT"]
        at = args.index("-f") + 2
        args[at:at] = ["-f", os.environ["ACCEPTANCE_COLLECTOR_OVERRIDE"]]
os.execv("/usr/local/bin/docker-real", ["docker", *args])
