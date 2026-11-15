"""Audit the deployment requirements with pip-audit on a venv-less interpreter.

The bundled Python on this machine ships without `venv`/`ensurepip`, which
breaks `python -m pip_audit` at import time. pip-audit also insists on building
a throwaway environment to resolve a requirements file that is not fully
pinned. Both obstacles are worked around here, without weakening the audit:

1. `pip install --dry-run --report` resolves the file and writes the exact
   versions a fresh deployment would install — the same tree a venv would have
   produced, transitive dependencies included.
2. That resolved set is written to a temporary lock file.
3. pip-audit runs on the lock file with `--no-deps --disable-pip`, i.e. the
   static path, against the OSV database.

Usage:
    python tools/dep_audit.py
    python tools/dep_audit.py --requirements requirements-pa.txt
    python tools/dep_audit.py --service pypi --format json

Exit code is pip-audit's: 1 when vulnerabilities are found.
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = TOOLS_DIR.parent
SHIM_DIR = TOOLS_DIR / '_no_venv_shim'


def resolve(requirements: Path, report_path: Path) -> list[tuple[str, str]]:
    """Resolve the requirements file without installing anything."""
    command = [
        sys.executable, '-m', 'pip', 'install',
        '--dry-run', '--ignore-installed',
        '--report', str(report_path),
        '-r', str(requirements),
        '--quiet', '--disable-pip-version-check',
    ]
    completed = subprocess.run(command, cwd=PROJECT_ROOT, text=True, capture_output=True)
    if completed.returncode != 0 or not report_path.exists():
        sys.stderr.write(completed.stdout + completed.stderr)
        raise SystemExit('pip could not resolve the requirements; see output above.')

    report = json.loads(report_path.read_text(encoding='utf-8'))
    pinned = []
    for item in report.get('install', []):
        metadata = item.get('metadata', {})
        if metadata.get('name') and metadata.get('version'):
            pinned.append((metadata['name'], metadata['version']))
    return sorted(pinned, key=lambda row: row[0].lower())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--requirements', default='requirements.txt', help='requirements file to audit')
    parser.add_argument('--service', default='osv', choices=['osv', 'pypi', 'esms'], help='advisory database')
    parser.add_argument('--format', default='columns', help='pip-audit output format')
    args = parser.parse_args()

    requirements = (PROJECT_ROOT / args.requirements).resolve()
    if not requirements.exists():
        raise SystemExit(f'no such requirements file: {requirements}')

    # The shim must be importable before pip_audit is imported.
    sys.path.insert(0, str(SHIM_DIR))

    with tempfile.TemporaryDirectory() as tmp:
        report_path = Path(tmp) / 'pip-report.json'
        lock_path = Path(tmp) / 'resolved-requirements.txt'

        pinned = resolve(requirements, report_path)
        lock_path.write_text(''.join(f'{name}=={version}\n' for name, version in pinned), encoding='utf-8')
        print(f'resolved {len(pinned)} packages from {args.requirements} '
              f'(transitive dependencies included)')
        print()

        from pip_audit._cli import audit  # imported late: needs the shim on sys.path

        sys.argv = [
            'pip-audit',
            '-r', str(lock_path),
            '--no-deps', '--disable-pip',
            '--vulnerability-service', args.service,
            '--format', args.format,
            '--progress-spinner', 'off',
        ]
        try:
            audit()
        except SystemExit as exc:
            return int(exc.code or 0)
    return 0


if __name__ == '__main__':
    os.chdir(PROJECT_ROOT)
    sys.exit(main())
