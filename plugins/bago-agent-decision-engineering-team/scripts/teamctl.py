#!/usr/bin/env python3
"""Compatibility entrypoint to the repository's canonical BAGO team controller."""
from __future__ import annotations
import runpy
import sys
from pathlib import Path
root=Path(__file__).resolve().parents[3]
controller=root/'.bago'/'team'/'kit'/'scripts'/'teamctl.py'
if not controller.is_file(): raise SystemExit(f'BAGO_TEAM_CONTROLLER_MISSING: {controller}')
sys.path.insert(0,str(controller.parent))
runpy.run_path(str(controller),run_name='__main__')
