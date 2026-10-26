# -*- coding: utf-8 -*-
from datetime import timedelta
import json
import re
from odoo import fields
from odoo.tests.common import TransactionCase, HttpCase, tagged
from odoo.exceptions import AccessError, ValidationError, UserError


@tagged('post_install', '-at_install')
class TestTechnicalTest(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.warehouse = cls.env['stock.warehouse'].search([('company_id', '=', cls.env.company.id)], limit=1)
        cls.stock_location = cls.warehouse.lot_stock_id
        cls.customer_location = cls.env.ref('stock.stock_location_customers')
        cls.outgoing_picking_type = cls.warehouse.out_type_id
        cls.partner = cls.env['res.partner'].create({
            'name': 'Test Customer Egypt',
            'phone': '+201012345678',
        })

        cls.product_tmpl_1 = cls.env['product.template'].create({
            'name': 'ROP Product 1',
            'type': 'product',
            'has_rop': True,
            'rop_count': 10,
        })
        cls.product_tmpl_2 = cls.env['product.template'].create({
            'name': 'ROP Product 2',
            'type': 'product',
            'has_rop': True,
            'rop_count': 10,
        })
        cls.product_tmpl_3 = cls.env['product.template'].create({
            'name': 'ROP Product 3',
            'type': 'product',
            'has_rop': True,
            'rop_count': 20,
        })

    def test_01_product_template_rop_computation(self):
        """Test ROP computation of same_rop_count."""
        # Product 1 and Product 2 both have rop_count = 10, Product 3 has rop_count = 20
        self.assertEqual(self.product_tmpl_1.same_rop_count, 1)
        self.assertEqual(self.product_tmpl_2.same_rop_count, 1)
        self.assertEqual(self.product_tmpl_3.same_rop_count, 0)
        self.assertEqual(
            (self.product_tmpl_1 | self.product_tmpl_2).mapped('same_rop_count'),
            [1, 1],
        )

        # Action test
        action = self.product_tmpl_1.action_view_same_rop_products()
        self.assertEqual(action['res_model'], 'product.template')
        self.assertIn(('rop_count', '=', 10), action['domain'])

    def test_02_stock_picking_outgoing_validation(self):
        """Test stock.picking constraint for outgoing pickings."""
        today = fields.Datetime.now()
        yesterday = today - timedelta(days=2)
        tomorrow = today + timedelta(days=2)

        # Should fail with past date for outgoing picking
        with self.assertRaises(ValidationError):
            self.env['stock.picking'].create({
                'picking_type_id': self.outgoing_picking_type.id,
                'location_id': self.stock_location.id,
                'location_dest_id': self.customer_location.id,
                'scheduled_date': yesterday,
            })

        # Should succeed with future date
        picking = self.env['stock.picking'].create({
            'picking_type_id': self.outgoing_picking_type.id,
            'location_id': self.stock_location.id,
            'location_dest_id': self.customer_location.id,
            'scheduled_date': tomorrow,
        })
        self.assertTrue(picking.id)

    def test_03_update_product_qty_wizard(self):
        """Test wizard to update quantity on hand and notify warehouse."""
        product = self.product_tmpl_1.product_variant_id
        wizard = self.env['update.product.qty.wizard'].create({
            'product_id': product.id,
            'new_quantity': 15,
        })
        wizard.action_update_quantity()
        self.assertEqual(product.qty_available, 15)
        wizard.write({'new_quantity': 20})
        wizard.action_update_quantity()
        self.assertEqual(product.qty_available, 20)

    def test_04_only_stock_managers_can_update_quantity(self):
        user = self.env['res.users'].create({
            'name': 'ROP Quantity Readonly User',
            'login': 'rop-quantity-readonly',
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id])],
        })
        wizard = self.env['update.product.qty.wizard'].create({
            'product_id': self.product_tmpl_1.product_variant_id.id,
            'new_quantity': 25,
        })
        with self.assertRaises(AccessError):
            wizard.with_user(user).action_update_quantity()

    def test_05_quantity_update_rejects_other_company_product(self):
        other_company = self.env['res.company'].create({'name': 'ROP Other Company'})
        template = self.env['product.template'].create({
            'name': 'Other Company ROP Product',
            'detailed_type': 'product',
            'company_id': other_company.id,
        })
        wizard = self.env['update.product.qty.wizard'].create({
            'product_id': template.product_variant_id.id,
            'new_quantity': 1,
        })
        with self.assertRaises(UserError):
            wizard.action_update_quantity()

    def test_06_pos_session_notify_warehouse_rop(self):
        """Test pos.session helper notify_warehouse_rop."""
        product = self.product_tmpl_1.product_variant_id
        res = self.env['pos.session'].notify_warehouse_rop([product.id])
        self.assertEqual(res, [product.id])
        wizard = self.env['update.product.qty.wizard'].create({
            'product_id': product.id,
            'new_quantity': 6,
        })
        wizard.action_update_quantity()
        self.assertEqual(self.env['pos.session'].notify_warehouse_rop([product.id]), [])

    def test_07_pos_admin_partner_is_loaded(self):
        config = self.env['pos.config'].search([], limit=1)
        if not config:
            self.skipTest("No POS configuration is available.")
        session = self.env['pos.session'].new({'config_id': config.id})
        params = {'search_params': {'fields': ['id', 'name', 'phone', 'mobile']}}
        loaded_partners = session._get_pos_ui_res_partner(params)
        admin_partner = self.env.ref('base.user_admin').partner_id
        admin_record = next(
            (partner for partner in loaded_partners if partner['id'] == admin_partner.id),
            None,
        )
        self.assertIsNotNone(admin_record)
        self.assertTrue(admin_record['is_admin'])
        self.assertFalse(any(
            partner['is_admin'] for partner in loaded_partners if partner['id'] != admin_partner.id
        ))

    def test_08_api_logic(self):
        """Test API business logic on models."""
        self.product_tmpl_1.write({'has_rop': True, 'rop_count': 35})
        self.assertEqual(self.product_tmpl_1.rop_count, 35)

        low_stock = self.env['product.template'].search([('qty_available', '<', 5)])
        self.assertIn(self.product_tmpl_1, low_stock)


@tagged('post_install', '-at_install')
class TestTechnicalTestHttp(HttpCase):

    def test_06_http_rop_product_endpoint(self):
        """Test /rop-product endpoint."""
        self.authenticate('admin', 'admin')
        res = self.url_open('/rop-product')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data.get('status'), 'success')
        self.assertIn('products', data)

    def test_07_http_api_products_rop(self):
        """Test /api/products/rop endpoint."""
        self.authenticate('admin', 'admin')
        res = self.url_open('/api/products/rop?page=1&limit=500')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data.get('status'), 'success')
        self.assertEqual(data.get('page'), 1)
        self.assertEqual(data.get('limit'), 100)
        invalid_limit = self.url_open('/api/products/rop?page=1&limit=0')
        self.assertEqual(invalid_limit.status_code, 400)

    def test_08_http_api_orders(self):
        """Test /api/orders endpoint."""
        self.authenticate('admin', 'admin')
        res = self.url_open('/api/orders?start_date=2020-01-01&end_date=2030-12-31')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data.get('status'), 'success')
        self.assertIn('orders', data)
        self.assertEqual(data['start_date'], '2020-01-01 00:00:00')
        self.assertEqual(data['end_date'], '2030-12-31 23:59:59')

        invalid_date = self.url_open('/api/orders?start_date=not-a-date&end_date=2030-12-31')
        self.assertEqual(invalid_date.status_code, 400)
        missing_bound = self.url_open('/api/orders?start_date=2020-01-01')
        self.assertEqual(missing_bound.status_code, 400)

    def test_09_http_api_requires_authentication(self):
        """Business endpoints must not expose order/product data to anonymous users."""
        response = self.url_open('/api/products/rop', allow_redirects=False)
        self.assertNotEqual(response.status_code, 200)

    def test_10_http_rop_endpoint_requires_authentication(self):
        """The low-stock inventory endpoint is restricted to authenticated users."""
        response = self.url_open('/rop-product', allow_redirects=False)
        self.assertNotEqual(response.status_code, 200)

    def test_12_http_rop_quantity_update_rejects_non_manager(self):
        user = self.env['res.users'].create({
            'name': 'ROP Website Readonly User',
            'login': 'rop-website-readonly',
            'password': 'test-password',
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id])],
        })
        self.authenticate(user.login, 'test-password')
        response = self.url_open(
            '/shop/rop/update-qty',
            data=json.dumps({
                'jsonrpc': '2.0',
                'method': 'call',
                'params': {'product_tmpl_id': 1, 'new_qty': 99},
                'id': 1,
            }),
            headers={'Content-Type': 'application/json'},
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIn('error', response.json().get('result', {}))

    def test_11_http_api_updates_rop_count(self):
        self.authenticate('admin', 'admin')
        product = self.env['product.template'].create({
            'name': 'API ROP Update Product',
            'has_rop': True,
            'rop_count': 5,
        })
        web_client = self.url_open('/web')
        csrf_match = re.search(r'csrf_token:\s*"([^"]+)"', web_client.text)
        self.assertTrue(csrf_match, "The authenticated web client should provide a CSRF token.")

        response = self.url_open(
            f'/api/product/rop?csrf_token={csrf_match.group(1)}',
            data=json.dumps({'product_id': product.id, 'rop_count': 12, 'has_rop': True}),
            headers={'Content-Type': 'application/json'},
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['product']['rop_count'], 12)

    def test_13_http_api_returns_pos_session_orders(self):
        config = self.env['pos.config'].search([], limit=1)
        if not config:
            self.skipTest("No POS configuration is available.")
        session = self.env['pos.session'].create({
            'name': 'API Test POS Session',
            'config_id': config.id,
            'user_id': self.env.user.id,
            'state': 'opened',
        })
        self.env['pos.order'].create({
            'name': 'API Test POS Order',
            'session_id': session.id,
            'company_id': config.company_id.id,
            'pricelist_id': config.pricelist_id.id,
            'amount_tax': 0,
            'amount_total': 0,
            'amount_paid': 0,
            'amount_return': 0,
        })
        self.authenticate('admin', 'admin')
        response = self.url_open(f'/api/pos/session/{session.id}/orders')
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data['session_id'], session.id)
        self.assertIn('orders', data)
        self.assertEqual(data['orders_count'], 1)


@tagged('post_install', '-at_install')
class TestTechnicalTestPosJs(HttpCase):

    def test_pos_js(self):
        env = self.env(user=self.env.ref('base.user_admin'))
        payment_method = env['pos.payment.method'].create({
            'name': 'Technical Test JS Cash',
        })
        env['product.product'].create({
            'name': 'Technical Test JS Product',
            'available_in_pos': True,
        })
        config = env['pos.config'].create({
            'name': 'Technical Test JS POS',
            'payment_method_ids': [(4, payment_method.id)],
        })
        config.open_ui()
        config.current_session_id.set_cashbox_pos(0, None)
        self.browser_js(
            '/pos/ui/tests?mod=web',
            '',
            '',
            login='admin',
            timeout=1800,
        )
