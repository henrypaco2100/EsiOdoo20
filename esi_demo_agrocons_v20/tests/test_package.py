"""Static checks for the distributable module (no live Odoo required)."""
from pathlib import Path
import csv
from lxml import etree
import ast

ROOT = Path(__file__).resolve().parents[1]

def test_manifest_and_source():
    manifest = ast.literal_eval((ROOT / '__manifest__.py').read_text())
    assert manifest['version'].startswith('20.0.')
    for path in manifest['data']:
        assert (ROOT / path).exists(), path
    for py in ROOT.rglob('*.py'):
        ast.parse(py.read_text())

def test_views_and_security():
    for xml in ROOT.rglob('*.xml'):
        etree.parse(str(xml))
    acl = ROOT/'security/ir.access.csv'
    with acl.open() as file:
        rows = list(csv.DictReader(file))
    assert rows and set(rows[0]) == {'id', 'name', 'model_id', 'group_id/id', 'operation', 'domain'}
    assert all(set(row['operation']) <= set('crud') for row in rows)
    assert not (ROOT/'security/ir.model.access.csv').exists()
