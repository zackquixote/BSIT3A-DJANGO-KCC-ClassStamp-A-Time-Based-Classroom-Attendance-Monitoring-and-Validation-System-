"""Minimal stand-in for CPython's `venv` module.

The bundled interpreter has no `venv` and no `ensurepip`. pip-audit imports
`venv` at module load (`class VirtualEnv(venv.EnvBuilder)`), so without this the
tool cannot even start. It only builds a real environment to resolve a
requirements file or to apply `--fix`; the static path used by
`tools/dep_audit.py` never calls `create()`, and anything that does fails loudly
here rather than silently producing a partial audit.
"""


class EnvBuilder:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def create(self, env_dir):
        raise RuntimeError(
            'This Python build has no venv module, so pip-audit cannot create an '
            'environment. Resolve the requirements first (tools/dep_audit.py does '
            'this with pip --dry-run --report) and audit the pinned result.'
        )

    def ensure_directories(self, env_dir):
        raise RuntimeError('This Python build has no venv module.')
