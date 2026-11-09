"""Parse the three admin CSV uploads for the transactional importer."""
import csv
import io
import re
from collections import defaultdict
from sqlalchemy import select
from . import FILES, Importer, issue, records

KINDS = {
    'collectors': 'tblSobirately.csv',
    'informants': 'tblInformators.csv',
    'cards': 'tblCards.csv',
}


def parse_uploads(files, errors):
    sources = {}
    for field, name in KINDS.items():
        upload = files.get(field)
        if not upload or not upload.filename:
            issue(errors, name, None, 'file', None, 'Выберите CSV-файл')
            continue
        try:
            content = upload.stream.read().decode('utf-8-sig')
            header_line = content.splitlines()[0] if content else ''
            # Inspect only the header; quoted delimiters are handled by csv.reader.
            candidates = []
            required = next(columns for filename, columns in FILES.items() if filename.endswith(name))
            for delimiter in (',', ';', '\t', '|'):
                header = next(csv.reader([header_line], delimiter=delimiter, strict=True), [])
                score = len(set(header).intersection(required))
                if len(header) > 1:
                    candidates.append((score, delimiter))
            if not candidates or max(score for score, _ in candidates) == 0:
                raise ValueError('Не удалось определить разделитель по заголовку')
            best = max(score for score, _ in candidates)
            matches = [d for score, d in candidates if score == best]
            if len(matches) != 1:
                raise ValueError('Неоднозначный разделитель в заголовке')
            reader = csv.reader(io.StringIO(content, newline=''), delimiter=matches[0], strict=True)
            header = next(reader, [])
            records = []
            sources[name] = {'header': header, 'records': records}
            if not header or len(header) != len(set(header)):
                issue(errors, name, 1, 'header', header, 'Пустые или повторяющиеся имена столбцов')
            for col in required:
                if col not in header:
                    issue(errors, name, 1, col, None, 'Обязательный столбец отсутствует')
            while True:
                line = reader.line_num + 1
                try:
                    values = next(reader)
                except StopIteration:
                    break
                if len(values) == len(header):
                    for i, col in enumerate(header):
                        if col in ('Код собирателя', 'ФИО собирателя', 'инициалы', 'ФИО') or col in tuple('собиратель%d' % n for n in range(1, 5)) + tuple('информант%d' % n for n in range(1, 5)):
                            values[i] = values[i].strip()
                records.append({'line': line, 'values': values})
                if len(values) != len(header):
                    issue(errors, name, line, 'row', values,
                          'Ожидалось столбцов: %d; получено: %d' % (len(header), len(values)))
        except (UnicodeError, csv.Error, ValueError) as exc:
            issue(errors, name, None, 'file', None, str(exc))
    return sources


class UploadImporter(Importer):
    """Resolve uploaded people without conflating informants sharing a code."""
    def prepare_people(self):
        self.years_to_insert = {}
        self.upload_codes = {'collectors': defaultdict(list), 'informators': defaultdict(list)}
        collectors = self.tables['collectors']
        existing = defaultdict(list)
        self.collector_codes = defaultdict(list)
        for identity, code, name in self.db.execute(select([collectors.c.id, collectors.c.code, collectors.c.name])):
            code, name = (code or '').strip(), (name or '').strip()
            existing[(code, name)].append(identity)
            self.collector_codes[code].append(identity)
        for filename, table, code_field, name_field in (
            ('tblSobirately.csv', 'collectors', 'Код собирателя', 'ФИО собирателя'),
            ('tblInformators.csv', 'informators', 'инициалы', 'ФИО'),
        ):
            source_pairs = {}
            for line, row in records(self.sources, filename):
                code = row.get(code_field, '').strip()
                name = row.get(name_field, '').strip()
                location = (filename, line, code_field)
                for field, value in ((code_field, code), (name_field, name)):
                    if not value:
                        issue(self.errors, filename, line, field, row.get(field), 'Required value is empty')
                values = {'code': code, 'name': name}
                if table == 'informators':
                    values['bio'] = row.get('биография') or None
                self.validate_values(table, values, location)
                if table == 'collectors' and (code, name) in source_pairs:
                    identity = source_pairs[(code, name)]
                elif table == 'collectors' and existing.get((code, name)):
                    matches = existing[(code, name)]
                    if len(matches) != 1:
                        issue(self.errors, *location, code, 'Multiple collectors have the same name and code')
                    identity = matches[0]
                else:
                    # An informant always gets a new row, including when the database
                    # already contains this code. Duplicate source codes are ambiguous.
                    identity = (table, code, name) if table == 'collectors' else (table, code)
                    self.people_to_insert.append((table, values, filename, line))
                    self.people[identity] = identity
                if table == 'collectors':
                    source_pairs[(code, name)] = identity
                if identity not in self.upload_codes[table][code]:
                    self.upload_codes[table][code].append(identity)
                elif table == 'informators':
                    issue(self.errors, *location, code, 'Duplicate informant code in supplied CSV')
                if table == 'informators' and row.get('село'):
                    self.validate_values('vills_inf', {'v_name': row['село']}, (filename, line, 'село'))

    def resolve(self, table, columns, values, location):
        if table == 'years' and columns == ['year']:
            year = values[0].strip()
            if not re.fullmatch(r'[0-9]{4}', year) or not 1901 <= int(year) <= 2155:
                issue(self.errors, *location, values[0], 'Год должен быть четырёхзначным числом от 1901 до 2155')
                return None
            matches = self.index('years', ['year']).get((year,), [])
            if len(matches) > 1:
                issue(self.errors, *location, year, 'В базе найдено несколько записей для этого года')
                return None
            if matches:
                return matches[0]
            marker = ('years', year)
            self.years_to_insert.setdefault(year, location)
            return marker
        if table not in ('informators', 'collectors') or columns != ['code']:
            return super().resolve(table, columns, values, location)
        code = values[0].strip()
        matches = self.upload_codes[table].get(code, [])
        if table == 'collectors' and not matches:
            matches = self.collector_codes.get(code, [])
        if len(matches) != 1:
            issue(self.errors, *location, values[0],
                  '%s %s code: %d matches' % ('Unknown or ambiguous', table, len(matches)))
            return None
        return matches[0]

    def write(self):
        for year, location in self.years_to_insert.items():
            self.attempt(location[0], location[1], lambda year=year: self.add_year(year))
        super().write()

    def add_year(self, year):
        table = self.tables['years']
        matches = list(self.db.execute(select([table.c.id]).where(table.c.year == int(year))))
        if len(matches) > 1:
            raise ValueError('В базе найдено несколько записей для года ' + year)
        self.people[('years', year)] = matches[0][0] if matches else self.insert('years', {'year': int(year)})

    def add_person(self, table, values):
        key = ((table, values['code'], values['name']) if table == 'collectors'
               else (table, values['code']))
        self.people[key] = self.insert(table, values)
