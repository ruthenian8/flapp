"""Validation and database writes for CSV imports."""
import re
from collections import defaultdict
from sqlalchemy import MetaData, and_, select, text
from sqlalchemy.exc import SQLAlchemyError
from .sources import issue, records, TABLES
from .questions import parse_questions

class Importer:
    def __init__(self, connection, sources, errors):
        self.db, self.sources, self.errors = connection, sources, errors
        metadata = MetaData()
        metadata.reflect(bind=connection, only=list(TABLES))
        self.tables = metadata.tables
        self.people = {}
        self.cards = []
        self.people_to_insert = []
        self.indexes = {}

    def index(self, table, columns):
        key = (table, tuple(columns))
        if key not in self.indexes:
            t = self.tables[table]
            index = defaultdict(list)
            for row in self.db.execute(select([t.c.id] + [t.c[c] for c in columns])):
                index[tuple(str(v) if v is not None else '' for v in row[1:])].append(row[0])
            self.indexes[key] = index
        return self.indexes[key]

    def resolve(self, table, columns, values, location):
        ids = self.index(table, columns).get(tuple(values), [])
        if len(ids) != 1:
            issue(self.errors, *location, list(values),
                  '%s reference in %s: %d matches; exactly one required'
                  % ('Unknown' if not ids else 'Ambiguous', table, len(ids)))
            return None
        return ids[0]

    def validate_values(self, table, values, location):
        for name, value in values.items():
            column = self.tables[table].c[name]
            if value is None:
                if not column.nullable:
                    issue(self.errors, *location, value, '%s.%s cannot be null' % (table, name))
                continue
            limit = getattr(column.type, 'length', None)
            byte_limit = {'TINYTEXT': 255, 'TEXT': 65535, 'MEDIUMTEXT': 16777215,
                          'LONGTEXT': 4294967295}.get(column.type.__class__.__name__)
            if limit and len(str(value)) > limit:
                issue(self.errors, *location, value, '%s.%s exceeds %d characters' % (table, name, limit))
            if byte_limit and len(str(value).encode('utf-8')) > byte_limit:
                issue(self.errors, *location, value, '%s.%s exceeds %d UTF-8 bytes' % (table, name, byte_limit))

    def prepare_people(self):
        for filename, table, code_field, name_field in (
            ('tblSobirately.csv', 'collectors', 'Код собирателя', 'ФИО собирателя'),
            ('tblInformators.csv', 'informators', 'инициалы', 'ФИО'),
        ):
            index = self.index(table, ['code'])
            seen = set()
            for line, row in records(self.sources, filename):
                code = row.get(code_field, '')
                location = (filename, line, code_field)
                for field in (code_field, name_field):
                    if not row.get(field, '').strip():
                        issue(self.errors, filename, line, field, row.get(field), 'Required value is empty')
                if code in seen:
                    issue(self.errors, *location, code, 'Duplicate source code; identity is ambiguous')
                    continue
                seen.add(code)
                values = dict(code=code, name=row.get(name_field))
                if table == 'informators':
                    values['bio'] = row.get('биография') or None
                self.validate_values(table, values, location)
                existing = index.get((code,), [])
                if existing:
                    if len(existing) != 1:
                        issue(self.errors, *location, code, 'Multiple existing people have this code')
                    else:
                        t = self.tables[table]
                        old = self.db.execute(select([t]).where(t.c.id == existing[0])).fetchone()
                        if any(old[k] != v for k, v in values.items()):
                            issue(self.errors, *location, code, 'Existing person has different name/biography; refusing to overwrite or discard input')
                        self.people[(table, code)] = existing[0]
                else:
                    marker = (table, code)
                    index[(code,)].append(marker)
                    self.people[(table, code)] = marker
                    self.people_to_insert.append((table, values, filename, line))
                if table == 'informators' and row.get('село'):
                    self.validate_values('vills_inf', {'v_name': row['село']}, (filename, line, 'село'))

    def prepare_cards(self):
        for line, row in records(self.sources, 'tblCards.csv'):
            def loc(field):
                return ('tblCards.csv', line, field)
            plan = dict(row=row, line=line, links=[])
            self.cards.append(plan)
            if not row.get('текст', '').strip():
                issue(self.errors, *loc('текст'), row.get('текст'), 'Text is required')
            # Preserve the original transcription conversion; raw text is archived.
            plan['text'] = row.get('текст', '').replace('\\', '́').replace('_', ' ̄')
            self.validate_values('texts', {'text': plan['text']}, loc('текст'))
            for prefix, table, link, foreign in (
                ('собиратель', 'collectors', 't2s', 's_id'),
                ('информант', 'informators', 't2i', 'i_id'),
            ):
                for i in range(1, 5):
                    field = prefix + str(i)
                    code = row.get(field, '')
                    if code:
                        identity = self.resolve(table, ['code'], [code], loc(field))
                        plan['links'].append((link, foreign, identity))
            for keyword in row.get('ключевые слова', '').split(','):
                if keyword.strip():
                    keyword = re.sub(r' +', ' ', keyword.strip())
                    identity = self.resolve('keywords', ['keyword'], [keyword], loc('ключевые слова'))
                    plan['links'].append(('t2k', 'k_id', identity))
            program = row.get('программа', '').replace('а', 'a').replace('Х', 'X')
            questions, problems = parse_questions(row.get('вопрос', ''))
            for problem in problems:
                issue(self.errors, *loc('вопрос'), row.get('вопрос'), problem)
            if not program.strip():
                issue(self.errors, *loc('программа'), program, 'Question program is required')
            for number, letter in questions:
                if 'q_list' in self.tables['questions'].c:
                    identity = self.resolve('questions', ['q_list', 'q_num', 'q_let'],
                                            [program, number, letter], loc('вопрос'))
                else:
                    # Modern schema stores program membership in q2ql.
                    identity = self.resolve_modern_question(program, number, letter, loc('вопрос'))
                plan['links'].append(('t2q', 'q_id', identity))
            year = row.get('год', '').strip()
            identity = self.resolve('years', ['year'], [year], loc('год'))
            plan['links'].append(('t2y', 'y_id', identity))
            parts = row.get('село', '').split(',')
            if len(parts) != 3 or not all(p.strip() for p in parts):
                issue(self.errors, *loc('село'), row.get('село'), 'Expected region, district, village (three nonempty comma-separated parts)')
            else:
                region, rayon, village = [p.strip() for p in parts]
                rayon = re.sub(r' +', ' ', rayon.replace('р-н', 'район'))
                plan['rayon'] = self.resolve('rayons', ['ray'], [rayon], loc('село'))
                # Hyphens are part of the village name; never discard the prefix.
                plan['village'] = village
                self.validate_values('vills_txt', {'v_name': village}, loc('село'))
                ids = self.index('vills_txt', ['v_name']).get((village,), [])
                if len(ids) > 1:
                    issue(self.errors, *loc('село'), village, 'Ambiguous village: multiple existing records')

    def resolve_modern_question(self, program, number, letter, location):
        metadata = next(iter(self.tables.values())).metadata
        if 'q_lists' not in self.tables:
            metadata.reflect(bind=self.db, only=['q_lists', 'q2ql'])
        q, lists, links = [self.tables[n] for n in ('questions', 'q_lists', 'q2ql')]
        ids = list(self.db.execute(select([q.c.id]).select_from(
            q.join(links, q.c.id == links.c.q_id).join(lists, lists.c.id == links.c.ql_id)
        ).where(and_(lists.c.code == program, q.c.q_num == number, q.c.q_let == letter))))
        unique = set(r[0] for r in ids)
        if len(unique) != 1:
            issue(self.errors, *location, [program, number, letter],
                  'Question reference has %d matches; exactly one required' % len(unique))
            return None
        return unique.pop()

    def insert(self, table, values):
        result = self.db.execute(self.tables[table].insert().values(**values))
        if self.db.dialect.name == 'mysql':
            warnings = list(self.db.execute(text('SHOW WARNINGS')))
            if warnings:
                raise ValueError('Database warnings: %s' % '; '.join(str(tuple(w)) for w in warnings))
        return result.inserted_primary_key[0]

    def village(self, table, name):
        t = self.tables[table]
        ids = list(self.db.execute(select([t.c.id]).where(t.c.v_name == name)))
        if len(ids) > 1:
            raise ValueError('Ambiguous %s village %r' % (table, name))
        return ids[0][0] if ids else self.insert(table, {'v_name': name})

    def link(self, table, values):
        t = self.tables[table]
        if not self.db.execute(select([t.c.id]).where(and_(*[t.c[k] == v for k, v in values.items()]))).fetchone():
            self.insert(table, values)

    def write(self):
        # Each failed unit rolls back to a savepoint, allowing later errors to be collected.
        for table, values, filename, line in self.people_to_insert:
            self.attempt(filename, line, lambda: self.add_person(table, values))
        for line, row in records(self.sources, 'tblInformators.csv'):
            if row.get('село'):
                self.attempt('tblInformators.csv', line, lambda: self.link('i2vi', {
                    'i_id': self.people[('informators', row['инициалы'])],
                    'v_id': self.village('vills_inf', row['село'])}))
        for plan in self.cards:
            self.attempt('tblCards.csv', plan['line'], lambda: self.add_card(plan))

    def attempt(self, filename, line, operation):
        savepoint = self.db.begin_nested()
        try:
            operation()
            savepoint.commit()
        except (SQLAlchemyError, ValueError, KeyError) as exc:
            savepoint.rollback()
            # DBAPI's original message avoids SQLAlchemy dumping full SQL parameters.
            issue(self.errors, filename, line, 'database', None, str(getattr(exc, 'orig', exc)))

    def add_person(self, table, values):
        self.people[(table, values['code'])] = self.insert(table, values)

    def add_card(self, plan):
        identity = self.insert('texts', {'text': plan['text']})
        for table, foreign, target in plan['links']:
            if isinstance(target, tuple):
                target = self.people[target]
            if not isinstance(target, int):
                raise ValueError('Reference could not be inserted: %r' % (target,))
            self.link(table, {'t_id': identity, foreign: target})
        village = self.village('vills_txt', plan['village'])
        self.link('vt2r', {'v_id': village, 'r_id': plan['rayon']})
        self.link('t2v', {'t_id': identity, 'v_id': village})


