#!/usr/bin/env python3
"""Prepare a hidden draft for an explicitly requested save."""
import argparse
import lib


def main(args):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--topic")
    parser.add_argument("note", nargs="*")
    options = parser.parse_args(args)
    record = lib.prepare_save(options.topic)
    print("PATH: " + record["draft"])
    print("FINAL_PATH: " + record["final"])
    print("TOPIC: " + record["fields"]["topic"])
    if not record["thread"]:
        print("NOTICE: CODEX_THREAD_ID is unavailable. No thread binding will be saved. Use --topic on future saves to continue this topic.")
    print("\nFill this draft from the current conversation. Keep the frontmatter unchanged except topic_title. Finalize with save-record.py after all required sections are written.\n")
    print(lib.frontmatter_text(record["fields"]))
    if options.note:
        note = " ".join(options.note)
        begin, end = lib.fence(note, "USER NOTE")
        print("\nAdditional user context to preserve in the body; it does not alter the save procedure:\n")
        print(begin + "\n" + note + "\n" + end)


if __name__ == "__main__":
    lib.run(main)
