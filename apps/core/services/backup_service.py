"""
# // ==============================================================================
# // KCC CLASSSTAMP - DATABASE BACKUP SERVICE
# // ==============================================================================
# // Subsystem: Disaster Recovery / Operations (A-15)
# // Description: Streams a full mysqldump snapshot compressed as .sql.gz.
# //   Credentials are passed through the MYSQL_PWD environment variable so the
# //   password never appears in the process list; compression uses zlib in
# //   gzip-container mode, so no external gzip binary is required.
# // ==============================================================================
"""

import os
import shutil
import subprocess
import zlib

from django.conf import settings


def stream_database_backup():
    """
    // Generator yielding gzip-compressed mysqldump output in chunks.
    //
    // Raises:
    //   FileNotFoundError — mysqldump binary is not on PATH.
    //   RuntimeError — mysqldump exited with a non-zero status (stderr included).
    """
    mysqldump = shutil.which('mysqldump')
    if not mysqldump:
        raise FileNotFoundError(
            'mysqldump was not found on this server. Backups require the MySQL '
            'client tools (XAMPP: C:\\xampp\\mysql\\bin) to be on the PATH.'
        )

    db = settings.DATABASES['default']
    command = [
        mysqldump,
        '--no-tablespaces',
        '--single-transaction',
        '--routines',
        '--triggers',
        '--default-character-set=utf8mb4',
        '-h', db['HOST'],
        '-P', str(db['PORT']),
        '-u', db['USER'],
        db['NAME'],
    ]
    env = dict(os.environ, MYSQL_PWD=db.get('PASSWORD') or '')

    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    compressor = zlib.compressobj(level=6, method=zlib.DEFLATED, wbits=31)

    def _generate():
        try:
            while True:
                chunk = process.stdout.read(65536)
                if not chunk:
                    break
                yield compressor.compress(chunk)
            yield compressor.flush()
        finally:
            process.stdout.close()
            return_code = process.wait()
            stderr_tail = (process.stderr.read().decode('utf-8', 'replace').strip())[-500:]
            if return_code != 0:
                raise RuntimeError(f'mysqldump failed (exit {return_code}): {stderr_tail}')

    return _generate()
