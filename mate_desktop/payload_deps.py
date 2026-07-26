"""Everything the payload imports — declared here so the shell actually carries it.

The build tool works out what to bundle by reading the source it is given. It is never given
the payload: that arrives later, over the updater, as downloaded source. So nothing the
payload imports would be packaged, and the app would die on the first `import sqlite3` — which
is exactly how the first build of this prototype failed.

This module is the shell↔payload contract, written down. It is imported once at startup so the
build tool sees these names, and it is deliberately explicit rather than clever: when a release
adds a library, this list and the dependency guard in updater.py are the two places that must
learn about it, and a missing entry shows up here at build time instead of on a user's Mac.

Generated from a full AST scan of web/ and poller/ (see the prototype notes), not by hand.
"""
# Third-party — the compiled ones are the whole reason the shell needs signing at all.
import cryptography          # noqa: F401
import fastapi               # noqa: F401
import leapmotor_api         # noqa: F401
import paho.mqtt.client      # noqa: F401
import uvicorn               # noqa: F401

# Standard library. Frozen builds ship only what they can see being used, and a payload that
# arrives later is invisible — so the ones the payload reaches for are named here.
import asyncio               # noqa: F401
import base64                # noqa: F401
import calendar              # noqa: F401
import collections           # noqa: F401
import contextlib            # noqa: F401
import csv                   # noqa: F401
import dataclasses           # noqa: F401
import datetime              # noqa: F401
import enum                  # noqa: F401
import hashlib               # noqa: F401
import hmac                  # noqa: F401
import html                  # noqa: F401
import io                    # noqa: F401
import json                  # noqa: F401
import logging               # noqa: F401
import math                  # noqa: F401
import pathlib               # noqa: F401
import random                # noqa: F401
import re                    # noqa: F401
import secrets               # noqa: F401
import shutil                # noqa: F401
import socket                # noqa: F401
import sqlite3               # noqa: F401  ← the one that broke the first build
import ssl                   # noqa: F401
import threading             # noqa: F401
import urllib.request        # noqa: F401
import uuid                  # noqa: F401
import xml.etree.ElementTree  # noqa: F401
import zipfile               # noqa: F401
import zoneinfo              # noqa: F401
