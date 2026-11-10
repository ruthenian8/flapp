"""Question reference parsing."""
import re


def parse_questions(value):
    """Parse numbered modifiers and standalone «доп.» without guessing ambiguity."""
    tokens = re.findall(r'\d+|[^\W\d_]+|[^\s]', value, re.UNICODE)
    result = []
    number = None
    has_modifier = False
    previous_modifier = False
    separated = True
    problems = []
    for token in tokens:
        if token.isdecimal():
            if number is not None and not has_modifier:
                result.append((number, ''))
            number, has_modifier = str(int(token)), False
            previous_modifier, separated = False, True
        elif token in (',', ';'):
            separated = True
        elif token == '.':
            # A full stop may be the abbreviation in «доп.»; it does not
            # disambiguate consecutive modifiers.
            continue
        elif token == 'доп' or (len(token) == 1 and token.isalpha()):
            if previous_modifier and not separated:
                problems.append('Adjacent question modifiers require disambiguation in the source: %r' % value)
            if token == 'доп' and number is None:
                result.append(('доп', ''))
            elif number is None:
                problems.append('Letter %r has no question number' % token)
            else:
                result.append((number, token.replace('a', 'а')))
                has_modifier = True
            previous_modifier, separated = True, False
        else:
            problems.append('Unsupported question token %r' % token)
    if number is not None and not has_modifier:
        result.append((number, ''))
    if value.strip() and not result:
        problems.append('No question references could be parsed')
    return list(dict.fromkeys(result)), problems
