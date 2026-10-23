"""Install isolated demo catalog using the public ORM; no existing POS settings changed."""
from odoo.tools.binary import BinaryBytes
import logging
from pathlib import Path

_logger = logging.getLogger(__name__)
ROOT = Path(__file__).parent
PREFIX = 'DEMO-POL-'

# Estimated values are clearly labelled and editable. Sales prices for pollo: supplied by user.
POS_CATEGORIES = ['Pollos a la brasa', 'Gaseosas', 'Acompañamientos', 'Aderezos y extras']
PRODUCTS = [
 # code, name, price, cost, POS category, image, description, sale, purchase
 ('POL-ECO','Pollo a la brasa económico',15,8,'Pollos a la brasa','pollo_economico','Incluye arroz, papa, fideo y salsas. Porción referencial.',True,False),
 ('POL-CUARTO','1/4 de pollo a la brasa',25,13,'Pollos a la brasa','pollo_cuarto','Incluye arroz, papa, fideo y salsas.',True,False),
 ('POL-MEDIO','1/2 pollo a la brasa',55,29,'Pollos a la brasa','pollo_medio','Incluye acompañamientos y salsas.',True,False),
 ('POL-ENTERO','Pollo entero a la brasa',110,58,'Pollos a la brasa','pollo_entero','Incluye porciones familiares de acompañamientos y salsas.',True,False),
 ('CC15','Coca-Cola 1,5 litros',15,10,'Gaseosas','cocacola','Precio estimado, editable.',True,True),
 ('CC20','Coca-Cola 2 litros',19,13,'Gaseosas','cocacola','Precio estimado, editable.',True,True),
 ('CC30','Coca-Cola 3 litros',24,17,'Gaseosas','cocacola','Precio estimado, editable.',True,True),
 ('FA15','Fanta 1,5 litros',15,10,'Gaseosas','fanta','Precio estimado, editable.',True,True),
 ('FA20','Fanta 2 litros',19,13,'Gaseosas','fanta','Precio estimado, editable.',True,True),
 ('FA30','Fanta 3 litros',24,17,'Gaseosas','fanta','Precio estimado, editable.',True,True),
 ('SP15','Sprite 1,5 litros',15,10,'Gaseosas','sprite','Precio estimado, editable.',True,True),
 ('SP20','Sprite 2 litros',19,13,'Gaseosas','sprite','Precio estimado, editable.',True,True),
 ('SP30','Sprite 3 litros',24,17,'Gaseosas','sprite','Precio estimado, editable.',True,True),
 ('PE15','Pepsi 1,5 litros',14,9,'Gaseosas','pepsi','Precio estimado, editable.',True,True),
 ('SE20','Seven Up 2 litros',18,12,'Gaseosas','sevenup','Precio estimado, editable.',True,True),
 ('AG05','Agua mineral 500 ml',5,3,'Gaseosas','agua','Precio estimado, editable.',True,True),
 ('ARZ','Porción adicional de arroz',5,2,'Acompañamientos','arroz','Precio estimado, editable.',True,False),
 ('PAP','Porción adicional de papa',7,3,'Acompañamientos','papas','Precio estimado, editable.',True,False),
 ('FID','Porción adicional de fideo',5,2,'Acompañamientos','fideo','Precio estimado, editable.',True,False),
 ('MAY','Mayonesa adicional',2,0.7,'Aderezos y extras','mayonesa','Precio estimado, editable.',True,False),
 ('KET','Ketchup adicional',2,0.7,'Aderezos y extras','ketchup','Precio estimado, editable.',True,False),
 ('MOS','Mostaza adicional',2,0.7,'Aderezos y extras','mostaza','Precio estimado, editable.',True,False),
 ('AJI','Ají adicional',2,0.7,'Aderezos y extras','aji','Precio estimado, editable.',True,False),
 ('ENV','Envase para llevar',2,1,'Aderezos y extras','envase','Precio estimado, editable. Usar cuando aplique.',True,True),
 # Raw materials are purchasable, not visible on POS.
 ('INS-POL','Pollo crudo entero (unidad)',0,39,None,'ins_pollo','Insumo para preparación; costo estimado.',False,True),
 ('INS-ARR','Arroz crudo (kg)',0,9,None,'arroz','Materia prima; costo estimado.',False,True),
 ('INS-PAP','Papa cruda (kg)',0,7,None,'papas','Materia prima; costo estimado.',False,True),
 ('INS-FID','Fideo seco (kg)',0,11,None,'fideo','Materia prima; costo estimado.',False,True),
 ('INS-ACE','Aceite comestible (litro)',0,16,None,'aceite','Materia prima; costo estimado.',False,True),
 ('INS-SAL','Sal (kg)',0,4,None,'sal','Materia prima; costo estimado.',False,True),
 ('INS-CAR','Carbón para brasa (kg)',0,8,None,'carbon','Materia prima; costo estimado.',False,True),
 ('INS-CON','Condimentos para pollo (kg)',0,22,None,'condimentos','Materia prima; costo estimado.',False,True),
 ('INS-MAY','Mayonesa a granel (kg)',0,24,None,'mayonesa','Materia prima; costo estimado.',False,True),
 ('INS-KET','Ketchup a granel (kg)',0,23,None,'ketchup','Materia prima; costo estimado.',False,True),
 ('INS-MOS','Mostaza a granel (kg)',0,22,None,'mostaza','Materia prima; costo estimado.',False,True),
 ('INS-AJI','Ají para salsa (kg)',0,18,None,'aji','Materia prima; costo estimado.',False,True),
 ('INS-BOL','Bolsas para llevar (unidad)',0,0.5,None,'envase','Material de empaque; costo estimado.',False,True),
 ('INS-SER','Servilletas (paquete)',0,10,None,'servilletas','Material consumible; costo estimado.',False,True),
]


def _image(name):
    path = ROOT / 'static' / 'description' / 'products' / (name + '.png')
    return BinaryBytes(path.read_bytes(), filename=path.name) if path.exists() else False


def post_init_hook(env):
    """Create own named records, never alter cash sessions, accounts or stock balances."""
    PosCat = env['pos.category'].sudo()
    Product = env['product.template'].sudo()
    Category = env['product.category'].sudo()
    Partner = env['res.partner'].sudo()
    demo_root = Category.search([('name', '=', 'DEMO POLLERÍA | Insumos y productos')], limit=1)
    if not demo_root:
        demo_root = Category.create({'name':'DEMO POLLERÍA | Insumos y productos'})
    cats = {}
    for name in POS_CATEGORIES:
        label = 'DEMO POLLERÍA | ' + name
        cat = PosCat.search([('name', '=', label)], limit=1)
        if not cat:
            cat = PosCat.create({'name':label})
        cats[name] = cat
    # Suppliers are examples only. No purchase orders generated.
    suppliers = []
    for name in ['DEMO Pollería - Distribuidora de pollos', 'DEMO Pollería - Proveedor de abarrotes', 'DEMO Pollería - Distribuidora de bebidas']:
        p = Partner.search([('name', '=', name)], limit=1)
        if not p:
            p = Partner.create({'name':name, 'supplier_rank':1, 'comment':'PROVEEDOR FICTICIO PARA DEMOSTRACIÓN. No usar para compras reales.'})
        suppliers.append(p)
    for code, name, price, cost, poscat, picture, desc, sale, purchase in PRODUCTS:
        sku = PREFIX + code
        existing = Product.search([('default_code', '=', sku)], limit=1)
        if existing:
            continue
        values = {
            'name':name, 'default_code':sku,
            'list_price':price, 'standard_price':cost,
            'sale_ok':sale, 'purchase_ok':purchase,
            'categ_id':demo_root.id,
            'description_sale':desc,
            'description_purchase':'DATOS DE DEMO. Verificar precios, cantidades y proveedor antes de comprar.',
            'image_1920':_image(picture),
        }
        if 'available_in_pos' in Product._fields:
            values['available_in_pos'] = bool(poscat)
        if poscat:
            if 'pos_categ_ids' in Product._fields:
                values['pos_categ_ids'] = [(6, 0, [cats[poscat].id])]
            elif 'pos_categ_id' in Product._fields:
                values['pos_categ_id'] = cats[poscat].id
        if 'type' in Product._fields:
            field = Product._fields['type']
            allowed = dict(field._description_selection(env)) if hasattr(field, '_description_selection') else {}
            # Odoo 20 product type often uses 'consu'; track_inventory separately.
            values['type'] = 'consu' if 'consu' in allowed else 'service'
        if 'is_storable' in Product._fields:
            values['is_storable'] = True
        if 'taxes_id' in Product._fields:
            # Never assume local tax setup: leave Odoo defaults unchanged.
            pass
        prod = Product.create(values)
        # Price hints per supplier, only when purchase vendor information model exists.
        if purchase and 'product.supplierinfo' in env:
            vendor = suppliers[2] if poscat == 'Gaseosas' else suppliers[0] if code == 'INS-POL' else suppliers[1]
            info_model = env['product.supplierinfo'].sudo()
            infovalues = {'partner_id':vendor.id, 'product_tmpl_id':prod.id, 'price':cost, 'min_qty':1}
            if 'currency_id' in info_model._fields:
                infovalues['currency_id'] = env.company.currency_id.id
            info_model.create(infovalues)
    _logger.info('ESI demo polleria: demo catalog created, no historical business records modified.')
