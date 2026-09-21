#!/usr/bin/env python3
"""Load a reference and record a dependency without switching topics."""
import argparse
import lib


def main(args):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("selector")
    options = parser.parse_args(args)
    path = lib.resolve_id(options.selector)
    if path is None:
        raise ValueError("no handoff matches %r. Use $session-handoff:session-handoff list to see IDs." % options.selector)
    lib.emit_loaded(path, reference=True)


if __name__ == "__main__":
    lib.run(main)
