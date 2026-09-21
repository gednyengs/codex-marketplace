#!/usr/bin/env python3
"""Check installed skill discovery and run helper tests from Codex's cache.

Run after installing session-handoff@sekekama. No model call is made.
"""
import json
from pathlib import Path
import queue
import subprocess
import sys
import tempfile
import threading
import time


def main():
    with tempfile.TemporaryDirectory(prefix="handoff-installed-") as project, tempfile.TemporaryFile() as errors:
        server = subprocess.Popen(["codex", "app-server", "--stdio"], stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, stderr=errors, text=True, bufsize=1)
        messages = queue.Queue()

        def collect():
            for line in server.stdout:
                try:
                    messages.put(json.loads(line))
                except ValueError:
                    pass

        reader = threading.Thread(target=collect, daemon=True)
        reader.start()

        def rpc(identifier, method, params):
            server.stdin.write(json.dumps({"id": identifier, "method": method, "params": params}) + "\n")
            server.stdin.flush()
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                message = messages.get(timeout=max(0.01, deadline - time.monotonic()))
                if message.get("id") != identifier:
                    continue
                if "error" in message:
                    raise RuntimeError(message["error"])
                return message["result"]
            raise RuntimeError("timed out waiting for " + method)

        try:
            rpc(1, "initialize", {"clientInfo": {"name": "session_handoff_smoke", "version": "1.0.0"},
                                  "capabilities": {"experimentalApi": True}})
            server.stdin.write(json.dumps({"method": "initialized", "params": {}}) + "\n")
            server.stdin.flush()
            result = rpc(2, "skills/list", {"cwds": [project], "forceReload": True})
            entries = result["data"]
            matches = [skill for entry in entries for skill in entry["skills"]
                       if skill.get("pluginId") == "session-handoff@sekekama"
                       or "session-handoff" in skill["name"]]
            if len(matches) != 1:
                raise RuntimeError("expected one installed handoff skill, found: %s" % matches)
            skill = matches[0]
            if not skill["enabled"]:
                raise RuntimeError("installed skill is disabled")
            skill_path = Path(skill["path"])
            plugin = skill_path.parents[2]
            metadata = (skill_path.parent / "agents/openai.yaml").read_text()
            if "allow_implicit_invocation: false" not in metadata:
                raise RuntimeError("installed skill is missing its explicit invocation policy")
            if (plugin / "hooks").exists():
                raise RuntimeError("unexpected installed hooks")
            print(json.dumps({"skill": skill["name"], "path": str(skill_path),
                              "enabled": skill["enabled"], "implicitInvocation": False}, indent=2), flush=True)
        finally:
            server.terminate()
            try:
                server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=5)
            server.stdin.close()
            reader.join(timeout=2)
            server.stdout.close()

        # Execute the installed tests, so imports resolve to cached helpers.
        subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", str(plugin / "tests")], check=True)


if __name__ == "__main__":
    main()
