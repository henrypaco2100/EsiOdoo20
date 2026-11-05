import ast
from pathlib import Path
import unittest
from lxml import etree

P=Path(__file__).parents[1]

class CenterViewsTests(unittest.TestCase):
    def test_native_views_belong_to_same_workorder_action(self):
        root=etree.parse(str(P/'views/workcenter_route.xml'))
        action=root.xpath("//record[@id='action_center_route']")[0]
        self.assertEqual(action.find("field[@name='res_model']").text,'mrp.workorder')
        self.assertEqual(action.find("field[@name='view_mode']").text,'kanban,list,graph,pivot,form')
        for name in ['center_route_graph','center_route_pivot']:
            self.assertIn(name,action.find("field[@name='view_ids']").get('eval'))
        self.assertFalse(root.xpath("//record[@id='center_route_kanban']//header"))

    def test_additional_menus_are_disabled_on_upgrade(self):
        for filename,menu in [('center_report.xml','center_advance_report_menu'),('center_dashboard.xml','center_dashboard_menu')]:
            root=etree.parse(str(P/'views'/filename))
            records=root.xpath("//record[@id='%s']/field[@name='active']"%menu)
            self.assertEqual(len(records),1)
            self.assertEqual(records[0].get('eval'),'False')

    def test_quantities_stored_for_native_aggregation_and_two_decimals(self):
        tree=ast.parse((P/'models/workcenter_route.py').read_text())
        assignments={n.targets[0].id:n.value for n in ast.walk(tree) if isinstance(n,ast.Assign) and len(n.targets)==1 and isinstance(n.targets[0],ast.Name)}
        for name in ['esi_center_received_qty','esi_center_available_qty']:
            values={v.arg:ast.literal_eval(v.value) for v in assignments[name].keywords}
            self.assertTrue(values['store'])
            self.assertEqual(values['digits'],(16,2))

    def test_inventory_precision_not_changed_globally(self):
        root=etree.parse(str(P/'views/workcenter_route.xml'))
        for field in root.xpath("//record[@id='center_transfer_form']//field[@name='available_qty' or @name='quantity']"):
            self.assertEqual(field.get('digits'),'[16, 2]')
        self.assertNotIn('decimal.precision',(P/'views/workcenter_route.xml').read_text())
