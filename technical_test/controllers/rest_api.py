# -*- coding: utf-8 -*-
import json
from datetime import datetime, time, timezone
from odoo import http, _
from odoo.http import request, Response


class RestApiController(http.Controller):

    def _pagination(self, page, limit):
        try:
            page = int(page)
            limit = int(limit)
        except (TypeError, ValueError):
            raise ValueError(_("page and limit must be positive integers."))
        if page < 1 or limit < 1:
            raise ValueError(_("page and limit must be positive integers."))
        limit = min(limit, 100)
        return page, limit, (page - 1) * limit

    def _json_response(self, data, status=200):
        return Response(
            json.dumps(data, default=str),
            content_type='application/json;charset=utf-8',
            status=status,
        )

    def _json_error(self, message, status=400):
        return Response(
            json.dumps({'status': 'error', 'message': message}),
            content_type='application/json;charset=utf-8',
            status=status,
        )

    def _parse_datetime_bound(self, value, end_of_day=False):
        value = value.strip()
        if len(value) == 10:
            parsed_date = datetime.strptime(value, '%Y-%m-%d').date()
            parsed_datetime = datetime.combine(
                parsed_date, time.max if end_of_day else time.min
            )
        else:
            parsed_datetime = datetime.fromisoformat(value.replace('Z', '+00:00'))
            if parsed_datetime.tzinfo:
                parsed_datetime = parsed_datetime.astimezone(timezone.utc).replace(tzinfo=None)
        return parsed_datetime.strftime('%Y-%m-%d %H:%M:%S')

    # API Task 1: Show all Orders within start / end date
    @http.route(['/api/orders', '/api/v1/orders'], type='http', auth='user', methods=['GET'])
    def get_orders_by_date(self, start_date=None, end_date=None, page=1, limit=100, **kwargs):
        """
        API Task 1: Show all Orders within start / end date.
        """
        if not start_date or not end_date:
            return self._json_error(_("Both start_date and end_date are required."))
        try:
            start_bound = self._parse_datetime_bound(start_date)
            end_bound = self._parse_datetime_bound(end_date, end_of_day=True)
        except (TypeError, ValueError):
            return self._json_error(_("Invalid date format. Use YYYY-MM-DD or an ISO 8601 datetime."))
        if start_bound > end_bound:
            return self._json_error(_("start_date must be earlier than or equal to end_date."))
        try:
            page, limit, offset = self._pagination(page, limit)
        except ValueError as error:
            return self._json_error(str(error))
        domain = [
            ('date_order', '>=', start_bound),
            ('date_order', '<=', end_bound),
        ]

        # Search Sale Orders
        sale_model = request.env['sale.order']
        sale_count = sale_model.search_count(domain)
        sale_orders = sale_model.search_read(
            domain,
            [
                'id', 'name', 'date_order', 'partner_id', 'state',
                'amount_untaxed', 'amount_tax', 'amount_total',
            ],
            order='date_order desc',
            limit=limit,
            offset=offset,
        )
        sale_order_ids = [so['id'] for so in sale_orders]
        sale_lines_by_order = {}
        if sale_order_ids:
            sale_lines = request.env['sale.order.line'].search_read(
                [('order_id', 'in', sale_order_ids)],
                ['id', 'order_id', 'product_id', 'product_uom_qty', 'price_unit', 'price_subtotal'],
            )
            for line in sale_lines:
                sale_lines_by_order.setdefault(line['order_id'][0], []).append(line)

        orders_data = []
        for so in sale_orders:
            partner = so.get('partner_id')
            orders_data.append({
                'id': so['id'],
                'name': so['name'],
                'type': 'sale_order',
                'date_order': str(so['date_order']),
                'partner_id': partner[0] if partner else None,
                'partner_name': partner[1] if partner else '',
                'state': so['state'],
                'amount_untaxed': so['amount_untaxed'],
                'amount_tax': so['amount_tax'],
                'amount_total': so['amount_total'],
                'lines': [
                    {
                        'line_id': line['id'],
                        'product_id': line['product_id'][0] if line['product_id'] else None,
                        'product_name': line['product_id'][1] if line['product_id'] else '',
                        'qty': line['product_uom_qty'],
                        'price_unit': line['price_unit'],
                        'price_subtotal': line['price_subtotal'],
                    }
                    for line in sale_lines_by_order.get(so['id'], [])
                ],
            })

        # Also search POS Orders
        pos_model = request.env['pos.order']
        pos_count = pos_model.search_count(domain)
        pos_orders = pos_model.search_read(
            domain,
            [
                'id', 'name', 'pos_reference', 'session_id', 'date_order',
                'partner_id', 'state', 'amount_tax', 'amount_total',
            ],
            order='date_order desc',
            limit=limit,
            offset=offset,
        )
        pos_order_ids = [po['id'] for po in pos_orders]
        pos_lines_by_order = {}
        if pos_order_ids:
            pos_lines = request.env['pos.order.line'].search_read(
                [('order_id', 'in', pos_order_ids)],
                ['id', 'order_id', 'product_id', 'qty', 'price_unit', 'price_subtotal_incl'],
            )
            for line in pos_lines:
                pos_lines_by_order.setdefault(line['order_id'][0], []).append(line)

        for po in pos_orders:
            partner = po.get('partner_id')
            session = po.get('session_id')
            orders_data.append({
                'id': po['id'],
                'name': po['name'],
                'type': 'pos_order',
                'pos_reference': po['pos_reference'],
                'session_id': session[0] if session else None,
                'date_order': str(po['date_order']),
                'partner_id': partner[0] if partner else None,
                'partner_name': partner[1] if partner else 'Walk-in Customer',
                'state': po['state'],
                'amount_tax': po['amount_tax'],
                'amount_total': po['amount_total'],
                'lines': [
                    {
                        'line_id': line['id'],
                        'product_id': line['product_id'][0] if line['product_id'] else None,
                        'product_name': line['product_id'][1] if line['product_id'] else '',
                        'qty': line['qty'],
                        'price_unit': line['price_unit'],
                        'price_subtotal_incl': line['price_subtotal_incl'],
                    }
                    for line in pos_lines_by_order.get(po['id'], [])
                ],
            })

        return self._json_response({
            'status': 'success',
            'count': len(orders_data),
            'total_count': sale_count + pos_count,
            'page': page,
            'limit': limit,
            'has_more': sale_count > offset + limit or pos_count > offset + limit,
            'start_date': start_bound,
            'end_date': end_bound,
            'orders': orders_data,
        })

    # API Task 2: Show all products that have ROP Count
    @http.route(['/api/products/rop', '/api/v1/products/rop'], type='http', auth='user', methods=['GET'])
    def get_products_with_rop(self, page=1, limit=100, **kwargs):
        """
        API Task 2: Show all products that have ROP Count.
        """
        try:
            page, limit, offset = self._pagination(page, limit)
        except ValueError as error:
            return self._json_error(str(error))
        domain = [
            ('has_rop', '=', True),
            ('rop_count', '>', 0),
        ]
        product_model = request.env['product.template']
        total_count = product_model.search_count(domain)
        products = product_model.search_read(
            domain,
            [
                'id', 'name', 'default_code', 'has_rop', 'rop_count',
                'same_rop_count', 'qty_available', 'list_price',
            ],
            limit=limit,
            offset=offset,
        )

        product_list = []
        for p in products:
            product_list.append({
                'id': p['id'],
                'name': p['name'],
                'default_code': p['default_code'] or '',
                'has_rop': p['has_rop'],
                'rop_count': p['rop_count'],
                'same_rop_count': p['same_rop_count'],
                'qty_available': p['qty_available'],
                'list_price': p['list_price'],
            })

        return self._json_response({
            'status': 'success',
            'count': len(product_list),
            'total_count': total_count,
            'page': page,
            'limit': limit,
            'has_more': total_count > offset + limit,
            'products': product_list,
        })

    # API Task 3: Add/Update A ROP Count for specific Product
    @http.route([
        '/api/product/<int:product_id>/rop',
        '/api/v1/product/<int:product_id>/rop',
        '/api/product/rop',
        '/api/v1/product/rop'
    ], type='http', auth='user', methods=['POST', 'PUT'])
    def add_or_update_product_rop(self, product_id=None, **kwargs):
        """
        API Task 3: Add A ROP Count for specific Product.
        Accepts product_id in path or body/params, along with rop_count (and optional has_rop).
        """
        # Parse payload
        data = {}
        if request.httprequest.data:
            try:
                data = json.loads(request.httprequest.data)
            except json.JSONDecodeError:
                return self._json_error(_("Invalid JSON request body."))
            if not isinstance(data, dict):
                return self._json_error(_("The JSON request body must be an object."))

        pid = product_id or data.get('product_id') or kwargs.get('product_id')
        if not pid:
            return self._json_error(_("product_id is required."))
        try:
            pid = int(pid)
            if pid <= 0:
                raise ValueError
        except (ValueError, TypeError):
            return self._json_error(_("Invalid product_id."))

        rop_count = data.get('rop_count') if 'rop_count' in data else kwargs.get('rop_count')
        if rop_count is None:
            return self._json_error(_("rop_count is required."))

        if isinstance(rop_count, bool) or not str(rop_count).isdigit():
            return self._json_error(_("Invalid rop_count integer value."))
        rop_count_val = int(rop_count)

        has_rop = data.get('has_rop', True)
        if isinstance(has_rop, str):
            if has_rop.lower() not in ('true', 'false'):
                return self._json_error(_("has_rop must be a boolean."))
            has_rop = has_rop.lower() == 'true'
        elif not isinstance(has_rop, bool):
            return self._json_error(_("has_rop must be a boolean."))

        if not (
            request.env.user.has_group('base.group_system')
            or request.env.user.has_group('stock.group_stock_manager')
        ):
            return self._json_error(_("Only system or inventory managers can update ROP values."), status=403)

        # Find product template or product product
        tmpl = request.env['product.template'].sudo().browse(pid)
        if not tmpl or not tmpl.exists():
            prod = request.env['product.product'].sudo().browse(pid)
            if prod and prod.exists():
                tmpl = prod.product_tmpl_id
        if (not tmpl or not tmpl.exists()):
            tmpl = request.env['product.template'].sudo().search([('id', '=', pid)], limit=1)
        if (not tmpl or not tmpl.exists()):
            prod = request.env['product.product'].sudo().search([('id', '=', pid)], limit=1)
            if prod and prod.exists():
                tmpl = prod.product_tmpl_id

        if not tmpl or not tmpl.exists():
            return self._json_error(_("Product not found with id %s.", pid), status=404)

        tmpl.write({
            'has_rop': bool(has_rop),
            'rop_count': rop_count_val,
        })

        return self._json_response({
            'status': 'success',
            'message': _("ROP Count updated successfully."),
            'product': {
                'id': tmpl.id,
                'name': tmpl.name,
                'has_rop': tmpl.has_rop,
                'rop_count': tmpl.rop_count,
                'same_rop_count': tmpl.same_rop_count,
            }
        })

    # API Task 4: Get all Orders inside a POS Session
    @http.route([
        '/api/pos/session/<int:session_id>/orders',
        '/api/v1/pos/session/<int:session_id>/orders',
        '/api/pos/orders',
        '/api/v1/pos/orders'
    ], type='http', auth='user', methods=['GET'])
    def get_pos_session_orders(self, session_id=None, page=1, limit=100, **kwargs):
        """
        API Task 4: Get all Orders inside a POS Session.
        """
        sid = session_id or kwargs.get('session_id')
        if not sid:
            return self._json_error(_("session_id is required."))

        try:
            sid = int(sid)
            if sid <= 0:
                raise ValueError
        except (ValueError, TypeError):
            return self._json_error(_("Invalid session_id."))

        session = request.env['pos.session'].browse(sid).exists()
        if not session:
            return self._json_error(_("POS Session not found with id %s.", sid), status=404)

        try:
            page, limit, offset = self._pagination(page, limit)
        except ValueError as error:
            return self._json_error(str(error))
        order_domain = [
            ('session_id', '=', session.id),
        ]
        order_model = request.env['pos.order']
        total_count = order_model.search_count(order_domain)
        pos_orders = order_model.search_read(
            order_domain,
            [
                'id', 'name', 'pos_reference', 'date_order', 'partner_id',
                'state', 'amount_total', 'amount_tax', 'amount_paid',
                'amount_return',
            ],
            order='date_order desc',
            limit=limit,
            offset=offset,
        )
        pos_order_ids = [o['id'] for o in pos_orders]
        lines_by_order = {}
        payments_by_order = {}
        if pos_order_ids:
            order_lines = request.env['pos.order.line'].search_read(
                [('order_id', 'in', pos_order_ids)],
                ['id', 'order_id', 'product_id', 'qty', 'price_unit', 'price_subtotal_incl'],
            )
            for line in order_lines:
                lines_by_order.setdefault(line['order_id'][0], []).append(line)
            payments = request.env['pos.payment'].search_read(
                [('pos_order_id', 'in', pos_order_ids)],
                ['id', 'pos_order_id', 'payment_method_id', 'amount'],
            )
            for payment in payments:
                payments_by_order.setdefault(payment['pos_order_id'][0], []).append(payment)

        orders_list = []
        for o in pos_orders:
            partner = o.get('partner_id')
            orders_list.append({
                'id': o['id'],
                'name': o['name'],
                'pos_reference': o['pos_reference'],
                'date_order': str(o['date_order']),
                'partner_id': partner[0] if partner else None,
                'partner_name': partner[1] if partner else 'Walk-in Customer',
                'state': o['state'],
                'amount_total': o['amount_total'],
                'amount_tax': o['amount_tax'],
                'amount_paid': o['amount_paid'],
                'amount_return': o['amount_return'],
                'payment_lines': [
                    {
                        'id': p['id'],
                        'name': p['payment_method_id'][1] if p['payment_method_id'] else '',
                        'amount': p['amount'],
                    }
                    for p in payments_by_order.get(o['id'], [])
                ],
                'lines': [
                    {
                        'id': l['id'],
                        'product_id': l['product_id'][0] if l['product_id'] else None,
                        'product_name': l['product_id'][1] if l['product_id'] else '',
                        'qty': l['qty'],
                        'price_unit': l['price_unit'],
                        'price_subtotal_incl': l['price_subtotal_incl'],
                    }
                    for l in lines_by_order.get(o['id'], [])
                ],
            })

        return self._json_response({
            'status': 'success',
            'session_id': session.id,
            'session_name': session.name,
            'session_state': session.state,
            'orders_count': len(orders_list),
            'total_count': total_count,
            'page': page,
            'limit': limit,
            'has_more': total_count > offset + limit,
            'orders': orders_list,
        })
