/** @odoo-module **/

import { Order } from "@point_of_sale/app/store/models";
import { patch } from "@web/core/utils/patch";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { _t } from "@web/core/l10n/translation";

patch(Order.prototype, {
    async checkRopStock() {
        const stockableLines = this.orderlines.filter((line) => {
            const product = line.get_product();
            return product && product.type === "product";
        });

        const productIds = [...new Set(stockableLines.map((line) => line.get_product().id))];
        let lowStockIds = [];
        if (productIds.length) {
            try {
                lowStockIds = await this.pos.orm.call("pos.session", "notify_warehouse_rop", [productIds]);
            } catch (err) {
                console.error("Failed to validate stock and notify warehouse admin:", err);
                lowStockIds = stockableLines
                    .filter((line) => line.get_product().qty_available === undefined || line.get_product().qty_available <= 5)
                    .map((line) => line.get_product().id);
            }
        }

        if (lowStockIds.length > 0) {
            await this.env.services.popup.add(ErrorPopup, {
                title: _t("Re-Order Point Alert"),
                body: _t("This product under of the Re-Order Point measure"),
            });
            return false;
        }

        return true;
    },

    async pay() {
        if (!this.canPay() || !(await this.checkRopStock())) {
            return;
        }
        return super.pay(...arguments);
    },
});
