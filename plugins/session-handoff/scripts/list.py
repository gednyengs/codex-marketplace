#!/usr/bin/env python3
"""List recent handoffs across the project without writing any files."""
import argparse
import lib


def main(args):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("limit", type=int, nargs="?", default=5)
    options = parser.parse_args(args)
    print(lib.rows_text(lib.recent_handoffs(options.limit)))


if __name__ == "__main__":
    lib.run(main)
