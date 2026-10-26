# -*- coding: utf-8 -*-
import json
from odoo import http, _
from odoo.http import request, Response


class WebsiteROPController(http.Controller):

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

    def _check_rop_access(self):
        """Check if current user is admin, warehouse admin, or internal user."""
        user = request.env.user
        if not user or user._is_public():
            return False
        return any(user.has_group(group) for group in (
            'base.group_user',
            'stock.group_stock_manager',
            'stock.group_stock_user',
            'base.group_system',
        ))

    def _check_stock_update_access(self):
        return request.env.user.has_group('stock.group_stock_manager')

    @http.route(['/shop/rop'], type='http', auth='user', website=True, sitemap=False)
    def website_rop_view(self, page=1, limit=100, **kwargs):
        """
        Ecommerce Task 1: View of all products with quantity < 5 called ROP View.
        Restricted to admin, warehouse admin, internal user.
        """
        if not self._check_rop_access():
            return request.redirect('/web/login?redirect=/shop/rop')

        try:
            page, limit, offset = self._pagination(page, limit)
        except ValueError as error:
            return Response(
                json.dumps({'status': 'error', 'message': str(error)}),
                content_type='application/json;charset=utf-8',
                status=400,
            )
        domain = [
            ('sale_ok', '=', True),
            ('type', '=', 'product'),
            ('qty_available', '<', 5),
        ]
        product_model = request.env['product.template']
        total_count = product_model.search_count(domain)
        rop_products = product_model.search(domain, limit=limit, offset=offset)

        values = {
            'products': rop_products,
            'page': page,
            'limit': limit,
            'has_previous': page > 1,
            'has_next': total_count > offset + limit,
            'title': _("ROP View - Products with Low Stock (< 5)"),
            'page_type': 'rop_low_stock',
        }
        return request.render('technical_test.website_rop_view_template', values)

    @http.route(['/shop/rop/update-qty'], type='json', auth='user', methods=['POST'], website=True)
    def website_rop_update_qty(self, product_tmpl_id=None, product_id=None, new_qty=0, **kwargs):
        """
        Ecommerce Task 2: Button under image opens popup to update quantity on hand directly,
        apply it, and notify warehouse/admins.
        """
        if not self._check_stock_update_access():
            return {'error': _("Access Denied: You do not have permission to update product quantity.")}

        if isinstance(new_qty, bool) or not str(new_qty).isdigit():
            return {'error': _("Invalid quantity value.")}
        new_quantity = int(new_qty)

        product = None
        if product_id:
            try:
                product = request.env['product.product'].browse(int(product_id)).exists()
            except (ValueError, TypeError):
                return {'error': _("Invalid product.")}
        elif product_tmpl_id:
            try:
                tmpl = request.env['product.template'].browse(int(product_tmpl_id)).exists()
            except (ValueError, TypeError):
                return {'error': _("Invalid product.")}
            if tmpl:
                product = tmpl.product_variant_id or tmpl.product_variant_ids[:1]

        if not product:
            return {'error': _("Product not found.")}
        if product.product_tmpl_id.company_id and product.product_tmpl_id.company_id != request.env.company:
            return {'error': _("This product belongs to a different company.")}

        # Apply stock update
        warehouse = request.env['stock.warehouse'].search([
            ('company_id', '=', request.env.company.id),
        ], limit=1)
        location = warehouse.lot_stock_id
        if not location:
            return {'error': _("No internal stock location is configured for this company.")}

        request.env['stock.quant'].with_context(inventory_mode=True).create({
            'product_id': product.id,
            'location_id': location.id,
            'inventory_quantity': new_quantity,
        })._apply_inventory()

        # Wizard notification logic to notify other admins & warehouse managers
        wizard = request.env['update.product.qty.wizard'].new({
            'product_id': product.id,
            'new_quantity': new_quantity,
        })
        notified_users = wizard._notify_warehouse_and_admin()

        message = _("Stock quantity updated successfully.")
        if notified_users:
            message = _(
                "Stock quantity updated successfully. %s warehouse administrator(s) have been notified.",
                len(notified_users),
            )
        return {
            'success': True,
            'product_id': product.id,
            'product_tmpl_id': product.product_tmpl_id.id,
            'new_qty': product.qty_available,
            'notified_count': len(notified_users),
            'message': message,
        }

    @http.route(['/shop/realtime-rop'], type='http', auth='public', website=True, sitemap=False)
    def website_realtime_rop_view(self, page=1, limit=100, **kwargs):
        """
        Ecommerce Task 3: View called Real-time ROP that renders products of quantity > 5
        Updates real-time without needing full page refresh.
        """
        try:
            page, limit, offset = self._pagination(page, limit)
        except ValueError as error:
            return Response(
                json.dumps({'status': 'error', 'message': str(error)}),
                content_type='application/json;charset=utf-8',
                status=400,
            )
        domain = [
            ('sale_ok', '=', True),
            ('type', '=', 'product'),
            ('qty_available', '>', 5),
        ]
        product_model = request.env['product.template'].sudo()
        total_count = product_model.search_count(domain)
        high_stock_products = product_model.search(domain, limit=limit, offset=offset)

        values = {
            'products': high_stock_products,
            'page': page,
            'limit': limit,
            'has_previous': page > 1,
            'has_next': total_count > offset + limit,
            'title': _("Real-time ROP View - Products (> 5 Units)"),
            'page_type': 'realtime_rop',
        }
        return request.render('technical_test.website_realtime_rop_template', values)

    @http.route(['/shop/realtime-rop/data'], type='json', auth='public', website=True)
    def website_realtime_rop_data(self, page=1, limit=100, **kwargs):
        """
        API data source for real-time live polling / updates without refreshing the page.
        """
        try:
            page, limit, offset = self._pagination(page, limit)
        except ValueError as error:
            return {'error': str(error)}
        domain = [
            ('sale_ok', '=', True),
            ('type', '=', 'product'),
            ('qty_available', '>', 5),
        ]
        product_model = request.env['product.template'].sudo()
        total_count = product_model.search_count(domain)
        high_stock_products = product_model.search(domain, limit=limit, offset=offset)

        data = []
        for p in high_stock_products:
            data.append({
                'id': p.id,
                'name': p.name,
                'default_code': p.default_code or '',
                'qty_available': p.qty_available,
                'list_price': p.list_price,
                'currency': p.currency_id.symbol,
                'image_url': f'/web/image/product.template/{p.id}/image_512',
            })
        return {
            'products': data,
            'count': len(data),
            'total_count': total_count,
            'page': page,
            'limit': limit,
            'has_more': total_count > offset + limit,
        }

    @http.route(['/rop-product'], type='http', auth='user', methods=['GET'])
    def rop_product_endpoint(self, page=1, limit=100, **kwargs):
        """
        Ecommerce Task 4: Endpoint called '/rop-product' that returns all products with quantity < 5.
        """
        if not self._check_rop_access():
            return Response(
                json.dumps({'status': 'error', 'message': _("Access denied.")}),
                content_type='application/json;charset=utf-8',
                status=403,
            )

        try:
            page, limit, offset = self._pagination(page, limit)
        except ValueError as error:
            return Response(
                json.dumps({'status': 'error', 'message': str(error)}),
                content_type='application/json;charset=utf-8',
                status=400,
            )
        domain = [
            ('sale_ok', '=', True),
            ('type', '=', 'product'),
            ('qty_available', '<', 5),
        ]
        product_model = request.env['product.template']
        total_count = product_model.search_count(domain)
        low_stock_products = product_model.search(domain, limit=limit, offset=offset)

        result = []
        for p in low_stock_products:
            result.append({
                'id': p.id,
                'name': p.name,
                'default_code': p.default_code or '',
                'qty_available': p.qty_available,
                'has_rop': p.has_rop,
                'rop_count': p.rop_count,
                'list_price': p.list_price,
                'uom': p.uom_id.name,
            })

        return Response(
            json.dumps({
                'status': 'success',
                'count': len(result),
                'total_count': total_count,
                'page': page,
                'limit': limit,
                'has_more': total_count > offset + limit,
                'products': result,
            }),
            content_type='application/json;charset=utf-8',
            status=200,
        )
