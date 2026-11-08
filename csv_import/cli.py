"""Command line interface for the CSV importer."""
import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.engine.url import URL
from .sources import read_sources, issue
from .transaction import import_sources

def default_url():
    try:
        from config import CONFIG
    except ImportError:
        from config import CONFIG
    return URL(drivername='mysql+pymysql', username=CONFIG['USER'],
               password=CONFIG['PASSWORD'], host=CONFIG['HOST'],
               port=int(CONFIG.get('PORT', 3306)), database=CONFIG['DATABASE'],
               query={'charset': 'utf8mb4'})


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('dry-run', 'commit'), default='dry-run')
    parser.add_argument('--input-dir', type=Path, default=Path(__file__).resolve().parent.parent / 'north-folklore')
    parser.add_argument('--database-url', default=os.environ.get('DATABASE_URL'))
    parser.add_argument('--archive', type=Path, help='New lossless JSON archive path; never overwritten')
    parser.add_argument('--report', type=Path, help='Optional new JSON report path; never overwritten')
    args = parser.parse_args(argv)
    errors = []
    sources = read_sources(args.input_dir, errors)
    archive = args.archive or Path('import-source-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.json')
    # Persist all source fields before any database write. An archive failure aborts.
    try:
        with archive.open('x', encoding='utf-8') as stream:
            json.dump(dict(input_dir=str(args.input_dir.resolve()), sources=sources), stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
    except OSError as exc:
        print('Cannot preserve source archive: %s' % exc, file=sys.stderr)
        return 2
    status = 'rolled_back'
    engine = None
    try:
        engine = create_engine(args.database_url or default_url())
        status = import_sources(engine, sources, errors, args.mode)
    except Exception as exc:
        issue(errors, 'database', None, 'transaction', None, str(getattr(exc, 'orig', exc)))
    finally:
        if engine is not None:
            engine.dispose()
    report = dict(mode=args.mode, status=status, archive=str(archive.resolve()),
                  error_count=len(errors), errors=errors)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.report:
        try:
            with args.report.open('x', encoding='utf-8') as stream:
                json.dump(report, stream, ensure_ascii=False, indent=2)
        except OSError as exc:
            print('Cannot write report (%s; database status: %s)' % (exc, status), file=sys.stderr)
            return 2
    return 1 if errors else 0


