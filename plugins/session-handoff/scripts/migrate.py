#!/usr/bin/env python3
"""Explicitly import v1 .handoff files while preserving the originals."""
import argparse
import lib


def main(args):
    argparse.ArgumentParser(description=__doc__).parse_args(args)
    print("Imported %d legacy handoff(s). Originals are unchanged." % lib.migrate_legacy())


if __name__ == "__main__":
    lib.run(main)
