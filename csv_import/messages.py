"""Russian presentation of upload errors; technical details stay in server logs."""
import re
from flask_babel import gettext

_PATTERNS = ['Unknown reference in (.+): (\\d+) matches; exactly one required', 'Ambiguous reference in (.+): (\\d+) matches; exactly one required', 'Unknown or ambiguous (informators|collectors) code: (\\d+) matches', 'Question reference has (\\d+) matches; exactly one required', 'Letter (.+) has no question number', 'Unsupported question token (.+)', '(.+)\\.(.+) cannot be null', '(.+)\\.(.+) exceeds (\\d+) characters', '(.+)\\.(.+) exceeds (\\d+) UTF-8 bytes', 'Ambiguous (.+) village (.+)', 'Reference could not be inserted: (.+)', 'Missing or nontransactional tables: (.+)']
_EXACT = {'Required column is missing', 'Ambiguous village: multiple existing records', 'Multiple existing people have this code', 'Expected region, district, village (three nonempty comma-separated parts)', 'Empty or duplicate column names', 'Duplicate informant code in supplied CSV', 'Duplicate source code; identity is ambiguous', 'Text is required', 'Supported databases: MySQL/InnoDB and SQLite', 'Multiple collectors have the same name and code', 'Question program is required', 'Existing person has different name/biography; refusing to overwrite or discard input', 'No question references could be parsed', 'Required value is empty'}
_FIELDS = {'database', 'header', 'row', 'transaction', 'file'}

def russian_upload_errors(errors):
    translated = []
    for error in errors:
        item = dict(error)
        message = str(item.get('message', ''))
        if message in _EXACT:
            item['message'] = gettext(message)
        else:
            for pattern in _PATTERNS:
                if re.fullmatch(pattern, message):
                    item['message'] = re.sub(pattern, gettext(pattern), message)
                    break
            else:
                # Already localized errors are emitted by the upload parser.
                # Do not expose untranslated DBAPI, filesystem or CSV diagnostics.
                if re.match(r'^[А-Яа-яЁё]', message):
                    item['message'] = message
                elif message.startswith("'utf-8' codec can't decode"):
                    item['message'] = 'Не удалось прочитать файл: сохраните его в кодировке UTF-8 и загрузите снова.'
                elif item.get('field') in ('database', 'transaction'):
                    item['message'] = 'Ошибка базы данных при импорте. Изменения отменены; подробности доступны администратору в журнале сервера.'
                else:
                    item['message'] = 'Не удалось обработать данные. Проверьте формат файла и значение; подробности доступны в журнале сервера.'
        item['field'] = gettext(item['field']) if item.get('field') in _FIELDS else item.get('field')
        if item.get('file') == 'database':
            item['file'] = 'база данных'
        translated.append(item)
    return translated
