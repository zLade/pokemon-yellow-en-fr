#!/usr/bin/env python3
"""English local build entrypoint: check | build [--verify-release]."""
from tools.build_english_release import main

if __name__ == "__main__":
    raise SystemExit(main())
