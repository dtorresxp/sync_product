# -*- coding: utf-8 -*-
# Part of Odoo. See COPYRIGHT & LICENSE files for full copyright and licensing details.

{
    'name': 'Import Product From odoo database',
    'version': '13.0.0.1',
    'category': 'sale',
    'summary': 'Allow to sync product between two odoo database',
    'description': """
    Sync all product between two database of odoo.
    """,
    'author': 'Wizard Technolab',
    'website': 'http://www.wizardtechnolab.com',
    'depends': ['website', 'mail', 'stock', 'sale'],
    'data': [
        'security/ir.model.access.csv',
        'views/product_sync_view.xml',
        'views/product_template_view.xml',
        'views/ir_cron_view.xml',
    ],
    'license': 'OPL-1',
}
