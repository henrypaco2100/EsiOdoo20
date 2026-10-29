"""Keep source sizes; complete adult footwear even without opening stock."""
import unicodedata


def normalized(value):
    return unicodedata.normalize('NFKD', str(value or '')).encode('ascii', 'ignore').decode().upper()


def is_children_line(row):
    # The supplied catalogue calls the children's line ESCOLAR (ES-*).
    family = normalized(row.get('family'))
    return 'INFANTIL' in family or 'ESCOLAR' in family


def required_sizes(row):
    source = {int(size) for size in row['sizes']}
    return sorted(source if is_children_line(row) else source | set(range(34, 47)))
