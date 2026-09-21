#!/usr/bin/env python3
"""Resume an explicit handoff, or display a picker without changing state."""
import argparse
import lib


def main(args):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("selector", nargs="?")
    options = parser.parse_args(args)
    if options.selector is None:
        print(lib.rows_text(lib.recent_handoffs(5), picker=True))
        return
    path = lib.resolve_id(options.selector)
    if path is None:
        raise ValueError("no handoff matches %r. Use $session-handoff:session-handoff list to see IDs." % options.selector)
    lib.emit_loaded(path)


if __name__ == "__main__":
    lib.run(main)
