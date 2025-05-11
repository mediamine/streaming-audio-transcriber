# src/transcriber/cli.py
import subprocess
import os


def run():
    script_path = os.path.join(os.path.dirname(__file__), "__init__.py")
    subprocess.run(["streamlit", "run", script_path])
