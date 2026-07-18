import os
import sys
import platform
import subprocess

print("=== APPSAIL DIAGNOSTICS ===", flush=True)
print(f"Python version: {sys.version}", flush=True)
print(f"Platform: {platform.platform()}", flush=True)
print(f"Architecture: {platform.machine()}", flush=True)
print(f"CWD: {os.getcwd()}", flush=True)
print(f"Files in CWD: {os.listdir('.')}", flush=True)

try:
    import fastapi
    print("fastapi: OK", flush=True)
except Exception as e:
    print(f"fastapi: FAILED ({e})", flush=True)

try:
    import pydantic
    print("pydantic: OK", flush=True)
except Exception as e:
    print(f"pydantic: FAILED ({e})", flush=True)

try:
    import pydantic_core
    print("pydantic_core: OK", flush=True)
except Exception as e:
    print(f"pydantic_core: FAILED ({e})", flush=True)

sys.exit(0)
