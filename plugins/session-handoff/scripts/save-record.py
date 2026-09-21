#!/usr/bin/env python3
"""Validate and publish a prepared handoff, then record its topic."""
import argparse
import lib


def main(args):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path")
    parser.add_argument("topic")
    options = parser.parse_args(args)
    final, bound = lib.finish_save(options.path, options.topic)
    print("Saved: " + lib.rel(final))
    print("ID: " + lib.handoff_id(final))
    print("Topic: " + options.topic)
    if not bound:
        print("NOTICE: No thread binding is available. Use save --topic " + options.topic + " on subsequent saves.")
    notice = lib.ignored_notice(final)
    if notice:
        print("NOTICE: " + notice)


if __name__ == "__main__":
    lib.run(main)
