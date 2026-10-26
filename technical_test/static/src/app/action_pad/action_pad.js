/** @odoo-module **/

import { ActionpadWidget } from "@point_of_sale/app/screens/product_screen/action_pad/action_pad";
import { patch } from "@web/core/utils/patch";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { _t } from "@web/core/l10n/translation";

patch(ActionpadWidget.prototype, {
    async onCashNowClick() {
        const order = this.pos.get_order();
        if (!order || order.get_orderlines().length === 0) {
            return this.env.services.popup.add(ErrorPopup, {
                title: _t("Empty Order"),
                body: _t("Please add at least one product before proceeding with Cash now."),
            });
        }

        if (!(await order.checkRopStock())) {
            return;
        }

        // Select the real system administrator customer loaded for this POS.
        const partners = this.pos.db.get_partners_sorted();
        const hasRequiredPhone = (partner) =>
            [partner.phone, partner.mobile].some(
                (phone) => phone && phone.trim().startsWith("+2")
            );
        const adminPartner = partners.find((p) => p.is_admin && hasRequiredPhone(p));
        console.log("Admin Partner Found:", adminPartner); // Debugging line
        if (!adminPartner) {``
            return this.env.services.popup.add(ErrorPopup, {
                title: _t("Cash now Customer Not Configured"),
                body: _t("Configure the system administrator with a phone or mobile number starting with +2 to use Cash now."),
            });
        }
        order.set_partner(adminPartner);

        const cashMethod = this.pos.payment_methods.find(
            (method) => method.is_cash_count || method.type === "cash"
        );
        if (!cashMethod) {
            return this.env.services.popup.add(ErrorPopup, {
                title: _t("Payment Method Error"),
                body: _t("No cash payment method is configured for this POS."),
            });
        }

        while (order.get_paymentlines().length > 0) {
            order.remove_paymentline(order.get_paymentlines()[0]);
        }

        const paymentline = order.add_paymentline(cashMethod) || order.selected_paymentline;
        if (!paymentline) {
            return this.env.services.popup.add(ErrorPopup, {
                title: _t("Payment Error"),
                body: _t("Unable to create the cash payment line for this order."),
            });
        }
        paymentline.set_amount(order.get_total_with_tax());
        order.set_to_invoice(true);
        order.cashNow = true;
        this.pos.showScreen("PaymentScreen");
    },
});
