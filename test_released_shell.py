"""Run against downloaded, immutable Desktop 1.0 binaries, never a rebuilt shell.

MATE_FROZEN_EXECUTABLE and MATE_REPO opt in to native integration tests. All
payload execution uses disposable app data without credentials or vehicle commands.
"""
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import time
import urllib.request

import pytest

EXECUTABLE = os.environ.get('MATE_FROZEN_EXECUTABLE')
MATE = os.environ.get('MATE_REPO')
pytestmark = pytest.mark.skipif(not (EXECUTABLE and MATE), reason='requires released shell and Mate source')


@pytest.fixture
def installed(tmp_path):
    current = tmp_path / 'payload' / 'current'
    for part in ('poller', 'web'):
        shutil.copytree(Path(MATE) / part, current / part,
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    env = dict(os.environ, MATE_APP_DIR=str(tmp_path), DB_PATH=str(tmp_path / 'mate.db'),
               DATA_CERT_DIR=str(tmp_path / 'certs'), CERT_DIR=str(tmp_path / 'certs'),
               MATE_DESKTOP='1', MATE_DESKTOP_VERSION='1.0.0', MATE_SKIP_UPDATE='1',
               PYTHONUTF8='1', PYTHONIOENCODING='utf-8')
    # Do not inherit a developer's real account or authentication material.
    for key in list(env):
        if key in ('ACCOUNT', 'PASSWORD', 'VIN', 'CERT_PATH', 'KEY_PATH') or key.startswith('LEAPMOTOR_'):
            env.pop(key)
    return tmp_path, current, env


def probe(installed, source):
    app, current, env = installed
    script = current / 'poller' / '_shell_probe.py'
    output = app / 'probe.json'
    script.write_text('import json, pathlib\n' + source +
                      '\npathlib.Path(' + repr(str(output)) + ').write_text(json.dumps(result))\n')
    with (app / 'probe.log').open('wb') as log:
        run = subprocess.run([EXECUTABLE, '--mate-child', 'poller', str(script)],
                             env=env, cwd=current / 'poller', stdout=log, stderr=log, timeout=45)
    assert run.returncode == 0, (app / 'probe.log').read_text(errors='replace')
    assert output.exists(), (app / 'probe.log').read_text(errors='replace')
    return json.loads(output.read_text())


def test_released_shell_accepts_requirements_and_migration_imports(installed):
    result = probe(installed, '''
import updater, sys, importlib
modules = ['ctypes', 'ctypes.wintypes', 'argparse', 'binascii', 'copy', 'errno',
           'functools', 'http.client', 'stat', 'tempfile', 'statistics', 'zlib']
modules.append('msvcrt' if sys.platform == 'win32' else 'fcntl')
for module in modules:
    importlib.import_module(module)
sys.path.insert(0, str(pathlib.Path(__file__).parent / 'vendor'))
import leapmotor_cloud
from leapmotor_cloud.private_storage import ensure_private_directory
ensure_private_directory(pathlib.Path(__file__).parents[3] / "private-probe")
from mate_api_runtime.process_lock import exclusive
with exclusive(pathlib.Path(__file__).parents[3] / "private-probe" / "migration.lock"):
    pass
result = {'missing': updater.unsatisfied_requirements(pathlib.Path(__file__).parents[1]),
          'frozen': bool(getattr(sys, 'frozen', False)), 'imports': modules}
''')
    assert result['frozen'] is True
    assert result['missing'] == []


def test_released_shell_runs_both_new_payload_entrypoints(installed):
    app, current, env = installed
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    assert port not in range(4000, 4004)
    env['WEB_PORT'] = str(port)
    children = []
    handles = []
    try:
        for part in ('poller', 'web'):
            handle = (app / (part + '.log')).open('wb')
            handles.append(handle)
            children.append(subprocess.Popen(
                [EXECUTABLE, '--mate-child', part, str(current / part / 'main.py')],
                cwd=current / part, env=env, stdin=subprocess.DEVNULL, stdout=handle, stderr=handle))
        deadline = time.monotonic() + 25
        ready = False
        while time.monotonic() < deadline:
            if any(child.poll() is not None for child in children):
                break
            try:
                with urllib.request.urlopen(f'http://127.0.0.1:{port}/', timeout=1) as response:
                    ready = response.status == 200
                if ready:
                    break
            except (OSError, urllib.error.URLError):
                time.sleep(.2)
        logs = lambda: '\n'.join((app / (p + '.log')).read_text(errors='replace') for p in ('poller', 'web'))
        assert ready, logs()
        time.sleep(2)
        assert all(child.poll() is None for child in children), logs()
    finally:
        for child in children:
            if child.poll() is None:
                child.terminate()
        for child in children:
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=5)
        for handle in handles:
            handle.close()


def test_released_shell_automatically_rolls_back_before_readiness(installed):
    """Exercise the v1.0 supervisor with its released frozen runtime and real children."""
    app, current, env = installed
    original = subprocess.check_output(['git', 'show', 'v1.0.0:mate_desktop/launcher.py'],
                                       cwd=Path(__file__).parent)
    old_launcher = app / 'released_launcher.py'
    old_launcher.write_bytes(original)
    result = probe(installed, '''
import runpy, os, socket
app = pathlib.Path(os.environ['MATE_APP_DIR'])
namespace = runpy.run_path(str(app / 'released_launcher.py'), run_name='released_launcher')
Services = namespace['Services']
g = Services.run.__globals__
assert g['SHELL_VERSION'] == '1.0.0'
assert g['STARTUP_GRACE_S'] == 25
current, previous = g['CURRENT'], g['PREVIOUS']
for part in ('poller', 'web'):
    (previous / part).mkdir(parents=True)
    (current / part / 'main.py').write_text('raise RuntimeError("migration rejected before bind")\\n')
(previous / 'poller' / 'main.py').write_text('import time\\ntime.sleep(60)\\n')
(previous / 'web' / 'main.py').write_text('MATE_VERSION = "3.4.50"\\nimport socket, os, time\\ns = socket.socket()\\ns.bind(("127.0.0.1", int(os.environ["WEB_PORT"])))\\ns.listen()\\ntime.sleep(60)\\n')
marker = app / 'preserved-data.bin'
marker.write_bytes(b'original database and credentials')
g['free_port'] = lambda: namespace['free_port'](0)
g['STARTUP_GRACE_S'] = 2
g['demo_requested'] = lambda: False
service = Services(fresh_payload=True)
def finish():
    service.stop()
    return 0
service._watch = finish
service.run()
assert service.ready.is_set() and service.url, 'previous payload never became ready'
assert g['updater'].payload_version(current) == '3.4.50'
assert marker.read_bytes() == b'original database and credentials'
result = {'restored': True, 'exit_code': service.exit_code}
''')
    assert result == {'restored': True, 'exit_code': 0}
