#!/usr/bin/env python3
"""Sanitize bearer credentials in captured API output before it is saved or shared."""
import argparse
import json
import sys


SECRET_KEYS = ("token", "url", "password", "pin", "secret")


def sanitize(value, compact_polyline=False):
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            if any(secret in key.lower() for secret in SECRET_KEYS):
                result[key] = "[REDACTED]"
            elif compact_polyline and key == "polyline" and isinstance(item, list):
                result[key] = f"[{len(item)} pontos]"
            else:
                result[key] = sanitize(item, compact_polyline)
        return result
    if isinstance(value, list):
        return [sanitize(item, compact_polyline) for item in value]
    return value


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--compact-polyline", action="store_true")
    args = parser.parse_args()
    payload = json.load(sys.stdin)
    print(json.dumps(sanitize(payload, args.compact_polyline), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
