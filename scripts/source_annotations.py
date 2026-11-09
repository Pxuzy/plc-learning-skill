"""Single source-marker grammar and immediate, per-fence binding."""
import re
from markdown_fences import LIST, unquote

ANNOTATION = re.compile(
    r'<!--\s*src:\s*(?:(?P<file>[^\s:;；>]+):)?'
    r'(?:(?P<start>\d+)\s*-\s*(?P<end>\d+)|(?P<none>none))'
    r'(?:\s*[;；]\s*来源/对象[：:]\s*(?P<evidence>[^\n]+?))?\s*-->', re.I)


def source_annotation(raw, block):
    # Blank lines may separate a marker and fence; any other content terminates
    # binding, so a previous fence/heading can never donate its marker.
    lines = raw.splitlines()
    for line in reversed(lines[:block['line'] - 1]):
        line, _ = unquote(line)
        marker = LIST.match(line)
        if marker:
            line = marker[3]
        line = line.strip()
        if not line:
            continue
        match = ANNOTATION.fullmatch(line)
        if match and not match.group('none'):
            if int(match.group('start')) < 1 or int(match.group('end')) < int(match.group('start')):
                return None
        return match
    return None
