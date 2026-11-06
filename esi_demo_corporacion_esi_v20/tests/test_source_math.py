# Standalone sanity checks for source constants (does not require Odoo runtime).
ASSETS = 5221800.00
LIAB_EQUITY = 5222300.00
PROFIT = 620700.00
assert round(LIAB_EQUITY - ASSETS, 2) == 500.00
assert PROFIT == 2456000.00 - 1468000.00 - 367300.00
