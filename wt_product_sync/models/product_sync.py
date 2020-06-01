from odoo import api, fields, models, _
import xmlrpc.client
from odoo.exceptions import AccessError
import datetime


class ProductSync(models.Model):
    _name = 'product.sync'
    _description = 'Product Store'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Store Name', required=True, tracking=1,
                       help="Store Name you would like to have")
    url = fields.Char(string='Url', tracking=1,
                      help="url of database you want to fetch data http://wizardtechnolab.com", required=True)
    database = fields.Char(string='Database', tracking=1, help="database name of the target url", required=True)
    username = fields.Char(string='User Name', tracking=1, help="admin user name of target url", required=True)
    password = fields.Char(string='Password', tracking=1, help="password of user name of target url", required=True)
    active = fields.Boolean(default=True)
    interval_number = fields.Integer(default=1, help="Repeat every x.")
    interval_type = fields.Selection([('minutes', 'Minutes'),
                                      ('hours', 'Hours'),
                                      ('days', 'Days'),
                                      ('weeks', 'Weeks'),
                                      ('months', 'Months')], string='Interval Unit', default='months')
    cron_id = fields.Many2one('ir.cron', 'Cron Id', readonly=True)

    @api.model
    def create(self, vals):
        res = super(ProductSync, self).create(vals)
        if res:
            ir_model = self.env['ir.model'].sudo().search([('model', '=', res._name)])
            date = datetime.datetime.now() + datetime.timedelta(minutes=2)
            cron = self.env['ir.cron'].create({
                'name': '[' + res.name + ']' + ' : Sync Product data',
                'model_id': ir_model.id,
                'state': 'multi',
                'interval_number': res.interval_number,
                'interval_type': res.interval_type,
                'active': True,
                'numbercall': -1,
                'store_id': res.id,
                'nextcall': date,
            })
            res.cron_id = cron.id
        return res

    def write(self, vals):
        res_update = super(ProductSync, self).write(vals)
        if vals.get('name'):
            self.cron_id.name = '[' + vals.get('name') + ']' + ' : Sync Product data'
        if vals.get('interval_number'):
            self.cron_id.interval_number = vals.get('interval_number')
        if vals.get('interval_type'):
            self.cron_id.interval_type = vals.get('interval_type')
        return res_update

    def unlink(self):
        for rec in self:
            if rec.cron_id:
                rec.sudo().cron_id.unlink()
        return super(ProductSync, self).unlink()

    def action_sync(self):
        try:
            xmlrpc.client.ServerProxy(self.url)
            url, db, username, password = self.url, self.database, self.username, self.password
            common = xmlrpc.client.ServerProxy('{}/xmlrpc/2/common'.format(url))
            uid = common.authenticate(db, username, password, {})
            models = xmlrpc.client.ServerProxy('{}/xmlrpc/2/object'.format(url))
            product_obj = self.env['product.template']
            attribute_obj = self.env['product.attribute']
            tmpl_attribute_line_obj = self.env['product.template.attribute.line']
            attribute_value_obj = self.env['product.attribute.value']
            warehouse = self.env['stock.warehouse'].search(
                [('company_id', '=', self.env.company.id)], limit=1
            )
            db_products = models.execute_kw(db, uid, password,
                                            'product.template', 'search_read',
                                            [[['description_pickingin', '=', 'koxul']]])
            if db_products:
                for db_product in db_products:
                    values = {
                        'name': db_product.get('name'),
                        'type': db_product.get('type'),
                        'lst_price': db_product.get('lst_price'),
                        'default_code': db_product.get('default_code'),
                        'description': db_product.get('description'),
                        'price': db_product.get('price'),
                        'standard_price': db_product.get('standard_price'),
                        'volume': db_product.get('volume'),
                        'volume_uom_name': db_product.get('volume_uom_name'),
                        'weight': db_product.get('weight'),
                        'weight_uom_name': db_product.get('weight_uom_name'),
                        'uom_name': db_product.get('uom_name'),
                        'barcode': db_product.get('barcode'),
                        'image_1920': db_product.get('image_1920'),
                        'description_sale': db_product.get('description_sale'),
                        'is_published': db_product.get('is_published'),
                        'description_pickingin': db_product.get('description_pickingin'),
                    }
                    sync_unique_id = str(self.id) + str(db_product.get('id'))
                    product_tmpl_id = product_obj.search([('product_qnique_id', '=', sync_unique_id)])
                    if not product_tmpl_id:
                        product_tmpl_id = product_obj.create(values)
                        product_tmpl_id.product_qnique_id = sync_unique_id
                        product_tmpl_id.store_id = self.id
                    else:
                        product_tmpl_id.write(values)

                    product_tmpl_id.list_price = db_product.get('list_price')

                    db_tmpl_attribute_line = db_product.get('valid_product_template_attribute_line_ids')
                    if not db_tmpl_attribute_line:
                        varient_id = self.env['product.product'].search([('product_tmpl_id', '=', product_tmpl_id.id)])
                        if varient_id and db_product.get('qty_available'):
                            self.env['stock.quant'].with_context(inventory_mode=True).create({
                                'product_id': varient_id.id,
                                'location_id': warehouse.lot_stock_id.id,
                                'inventory_quantity': db_product.get('qty_available'),
                            })
                    product_tmpl_id.product_template_image_ids.unlink()
                    db_tmpl_image_ids = db_product.get('product_template_image_ids')
                    for image in db_tmpl_image_ids:
                        db_tmpl_image_id = models.execute_kw(db, uid, password,
                                                             'product.image', 'search_read',
                                                             [[['id', '=', image]]])
                        if db_tmpl_image_id:
                            product_tmpl_id.write({
                                'product_template_image_ids': [
                                    (0, 0, {'name': db_tmpl_image_id[0].get('name'),
                                            'image_1920': db_tmpl_image_id[0].get('image_1920')})]
                            })

                    product_tmpl_id.attribute_line_ids.unlink()
                    if db_tmpl_attribute_line:
                        for tmpl_attribute_line in db_tmpl_attribute_line:
                            db_tmpl_line = models.execute_kw(db, uid, password,
                                                             'product.template.attribute.line', 'search_read',
                                                             [[['id', '=', tmpl_attribute_line]]])

                            if db_tmpl_line:
                                db_att_name = db_tmpl_line[0].get('attribute_id')
                                self_attribute = attribute_obj.search([('name', '=', db_att_name[1])])
                                if not self_attribute:
                                    self_attribute = attribute_obj.create({'name': db_att_name[1]})
                                db_att_value_ids = []
                                for value_id in db_tmpl_line[0].get('value_ids'):
                                    db_att_value = models.execute_kw(db, uid, password, 'product.attribute.value',
                                                                     'search_read', [[['id', '=', value_id]]])
                                    if db_att_value:
                                        self_att_value = attribute_value_obj.search(
                                            [('name', '=', db_att_value[0].get('name'))])
                                        if self_att_value:
                                            db_att_value_ids.append(self_att_value.id)
                                        if not self_att_value:
                                            self_att_value = attribute_value_obj.create({
                                                'name': db_att_value[0].get('name'),
                                                'attribute_id': self_attribute.id,
                                            })
                                            db_att_value_ids.append(self_att_value.id)

                                tmpl_attribute_line_obj.create({
                                    'product_tmpl_id': product_tmpl_id.id,
                                    'attribute_id': self_attribute.id,
                                    'value_ids': [(6, 0, db_att_value_ids)]
                                })

                        db_product_varients = models.execute_kw(db, uid, password,
                                                                'product.product', 'search_read',
                                                                [[['product_tmpl_id', '=', db_product.get('id')]]])
                        for varient_rec in db_product_varients:
                            self_varients = self.env['product.product'].search(
                                [('partner_ref', '=', varient_rec.get('partner_ref'))])
                            update_varients = self_varients.filtered(
                                lambda x: x.partner_ref == varient_rec.get(
                                    'partner_ref') and x.product_tmpl_id.id == product_tmpl_id.id)
                            if not update_varients:
                                varient_ref = varient_rec.get('partner_ref').split('] ')[1]
                                update_varients = self_varients.filtered(
                                    lambda x: x.partner_ref == varient_ref and
                                              x.product_tmpl_id.id == product_tmpl_id.id)
                            update_varients.update({
                                'name': varient_rec.get('name'),
                                'type': varient_rec.get('type'),
                                'price': varient_rec.get('price'),
                                'lst_price': varient_rec.get('lst_price'),
                                'default_code': varient_rec.get('default_code'),
                                'code': varient_rec.get('code'),
                                'barcode': varient_rec.get('barcode'),
                                'standard_price': varient_rec.get('standard_price'),
                                'volume': varient_rec.get('volume'),
                                'weight': varient_rec.get('weight'),
                                'description': varient_rec.get('description'),
                                'list_price': varient_rec.get('list_price'),
                                'volume_uom_name': varient_rec.get('volume_uom_name'),
                                'weight_uom_name': varient_rec.get('weight_uom_name'),
                                'image_variant_1920': varient_rec.get('image_variant_1920'),
                                'description_sale': db_product.get('description_sale'),
                                'is_published': db_product.get('is_published'),
                                'description_pickingin': db_product.get('description_pickingin'),
                            })

                            for varient in varient_rec.get('product_template_attribute_value_ids'):
                                att_value = models.execute_kw(db, uid, password,
                                                              'product.template.attribute.value', 'search_read',
                                                              [[['id', '=', varient]]])
                                self_att_val = self.env['product.template.attribute.value'].search(
                                    [('product_tmpl_id', '=', product_tmpl_id.id),
                                     ('name', '=', att_value[0].get('name')),
                                     ('display_name', '=', att_value[0].get('display_name'))])
                                if self_att_val:
                                    self_att_val.price_extra = att_value[0].get('price_extra')

                            if varient_rec.get('qty_available'):
                                self.env['stock.quant'].with_context(inventory_mode=True).create({
                                    'product_id': update_varients.id,
                                    'location_id': warehouse.lot_stock_id.id,
                                    'inventory_quantity': varient_rec.get('qty_available'),
                                })

        except:
            raise AccessError(_("[Errno 111] Connection refused"))


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    product_qnique_id = fields.Char(string='Store Id', readonly=True)
    store_id = fields.Many2one('product.sync', string='Store', readonly=True)


class IrCron(models.Model):
    _inherit = 'ir.cron'

    store_id = fields.Many2one('product.sync', string='Store', readonly=True)

    def product_sync_crons(self):
        now_datetime = datetime.datetime.now().strftime('%m/%d/%Y %H:%M')
        crons = self.env['ir.cron'].search([])
        if crons:
            for cron in crons:
                if cron and cron.nextcall.strftime('%m/%d/%Y %H:%M') == now_datetime and cron.store_id:
                    cron.store_id.action_sync()
