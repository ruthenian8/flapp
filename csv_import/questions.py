"""Question reference parsing."""
import re

def parse_questions(value):
    """Parse only explicit numbers, letters, and доп.; never delete unknown tokens."""
    tokens = re.findall(r'\d+|[^\W\d_]+|[^\s]', value, re.UNICODE)
    result = []
    number = None
    has_letter = False
    problems = []
    for token in tokens:
        if token.isdecimal():
            if number is not None and not has_letter:
                result.append((number, ''))
            number, has_letter = str(int(token)), False
        elif token in (',', '.', ';'):
            continue
        elif token == 'доп':
            if number is None:
                result.append(('доп', ''))
            else:
                result.append((number, ''))
                number, has_letter = None, False
        elif len(token) == 1 and token.isalpha():
            if number is None:
                problems.append('Letter %r has no question number' % token)
            else:
                result.append((number, token.replace('a', 'а')))
                has_letter = True
        else:
            problems.append('Unsupported question token %r' % token)
    if number is not None and not has_letter:
        result.append((number, ''))
    if value.strip() and not result:
        problems.append('No question references could be parsed')
    return list(dict.fromkeys(result)), problems


