"""CSV source definitions and parsing."""
import csv
import hashlib
import io

FILES = {
    'plesetski-tblSobirately.csv': ('Код собирателя', 'ФИО собирателя'),
    'plesetski-tblInformators.csv': ('инициалы', 'ФИО', 'биография', 'село'),
    'plesetski-tblCards.csv': ('текст', 'программа', 'вопрос', 'год', 'ключевые слова', 'село')
    + tuple('собиратель%d' % i for i in range(1, 5))
    + tuple('информант%d' % i for i in range(1, 5)),
}
TABLES = ('texts', 'collectors', 'informators', 'vills_inf', 'i2vi',
          'keywords', 'questions', 'rayons', 'years', 'vills_txt',
          'vt2r', 't2s', 't2i', 't2k', 't2q', 't2y', 't2v')


def issue(errors, file, row, field, value, message):
    errors.append(dict(file=file, row=row, field=field, value=value, message=message))


def read_sources(directory, errors):
    """Keep strings (including literal NA, leading zeros, and whitespace) intact."""
    sources = {}
    for filename, required in FILES.items():
        try:
            raw = (directory / filename).read_bytes()
            reader = csv.reader(io.StringIO(raw.decode('utf-8-sig'), newline=''), strict=True)
            header = next(reader, [])
            records = []
            sources[filename] = dict(sha256=hashlib.sha256(raw).hexdigest(),
                                     header=header, records=records)
            if not header or len(header) != len(set(header)):
                issue(errors, filename, 1, 'header', header, 'Empty or duplicate column names')
            for field in required:
                if field not in header:
                    issue(errors, filename, 1, field, None, 'Required column is missing')
            while True:
                line = reader.line_num + 1
                try:
                    values = next(reader)
                except StopIteration:
                    break
                records.append(dict(line=line, values=values))
                if len(values) != len(header):
                    issue(errors, filename, line, 'row', values,
                          'Expected %d cells, received %d' % (len(header), len(values)))
        except (OSError, UnicodeError, csv.Error) as exc:
            issue(errors, filename, None, 'file', None, str(exc))
    return sources


def records(sources, filename):
    source = sources.get(filename, {})
    header = source.get('header', [])
    for record in source.get('records', []):
        if len(record['values']) == len(header) and len(header) == len(set(header)):
            yield record['line'], dict(zip(header, record['values']))


