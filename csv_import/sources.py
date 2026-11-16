"""CSV source definitions and parsing."""
import csv
import hashlib
import io

FILES = {
    'tblSobirately.csv': ('Код собирателя', 'ФИО собирателя'),
    'tblInformators.csv': ('инициалы', 'ФИО', 'биография', 'село'),
    'tblCards.csv': ('текст', 'программа', 'вопрос', 'год', 'ключевые слова', 'село')
    + tuple('собиратель%d' % i for i in range(1, 5))
    + tuple('информант%d' % i for i in range(1, 5)),
}
TABLES = ('texts', 'collectors', 'informators', 'vills_inf', 'i2vi',
          'keywords', 'questions', 'rayons', 'years', 'vills_txt',
          'vt2r', 't2s', 't2i', 't2k', 't2q', 't2y', 't2v')


def normalize_header(column, filename):
    column = column.lower()
    if filename.endswith('tblCards.csv'):
        return {'собиратель': 'собиратель1', 'информант': 'информант1'}.get(column, column)
    return column


def issue(errors, file, row, field, value, message):
    errors.append(dict(file=file, row=row, field=field, value=value, message=message))


def detect_delimiter(content, required):
    """Choose a separator using only the first line and expected column names."""
    header_line = content.splitlines()[0] if content else ''
    expected = {column.lower() for column in required}
    candidates = []
    for delimiter in (',', ';', '\t', '|'):
        try:
            header = next(csv.reader([header_line], delimiter=delimiter, strict=True), [])
        except csv.Error:
            continue
        if len(header) > 1:
            names = {column.lower() for column in header}
            if 'собиратель1' in expected and 'собиратель' in names:
                names.add('собиратель1')
            if 'информант1' in expected and 'информант' in names:
                names.add('информант1')
            candidates.append((len(names & expected), delimiter))
    if not candidates or max(score for score, _ in candidates) == 0:
        raise ValueError('Не удалось определить разделитель по заголовку')
    best = max(score for score, _ in candidates)
    matches = [delimiter for score, delimiter in candidates if score == best]
    if len(matches) != 1:
        raise ValueError('Неоднозначный разделитель в заголовке')
    return matches[0]


def read_sources(directory, errors):
    """Keep strings (including literal NA, leading zeros, and whitespace) intact."""
    sources = {}
    for filename, required in FILES.items():
        try:
            raw = (directory / filename).read_bytes()
            content = raw.decode('utf-8-sig')
            delimiter = detect_delimiter(content, required)
            reader = csv.reader(io.StringIO(content, newline=''), delimiter=delimiter, strict=True)
            header = next(reader, [])
            records = []
            sources[filename] = dict(sha256=hashlib.sha256(raw).hexdigest(),
                                     header=header, records=records)
            normalized = [normalize_header(col, filename) for col in header]
            if not header or len(normalized) != len(set(normalized)):
                issue(errors, filename, 1, 'header', header, 'Empty or duplicate column names')
            for field in required:
                if field.lower() not in normalized:
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
        except (OSError, UnicodeError, csv.Error, ValueError) as exc:
            issue(errors, filename, None, 'file', None, str(exc))
    return sources


def records(sources, filename):
    source = sources.get(filename, {})
    header = [normalize_header(col, filename) for col in source.get('header', [])]
    for record in source.get('records', []):
        if len(record['values']) == len(header) and len(header) == len(set(header)):
            yield record['line'], dict(zip(header, record['values']))


