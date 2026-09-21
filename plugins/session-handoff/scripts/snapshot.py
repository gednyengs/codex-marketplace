#!/usr/bin/env python3
"""Print repository facts without executing detected build commands."""
import argparse
import lib


def main(args):
    argparse.ArgumentParser(description=__doc__).parse_args(args)
    print(lib.facts())


if __name__ == "__main__":
    lib.run(main)
