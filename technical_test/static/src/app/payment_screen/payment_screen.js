/** @odoo-module **/

import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { patch } from "@web/core/utils/patch";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { _t } from "@web/core/l10n/translation";

patch(PaymentScreen.prototype, {
    onMounted() {
        if (this.currentOrder.cashNow) {
            this.currentOrder.cashNow = false;
            Promise.resolve().then(() => this.validateOrder(false));
            return;
        }
        super.onMounted(...arguments);
    },

    async _isOrderValid(isForceValidate) {
        // POS Task 3 Validations on Payment Method Select screen:
        // 1- Customer
        const partner = this.currentOrder.get_partner();
        if (!partner) {
            this.popup.add(ErrorPopup, {
                title: _t("Customer Required"),
                body: _t("Make sure that you have selected Customer."),
            });
            return false;
        }

        // 2- Customer with Phone
        const phones = [partner.phone, partner.mobile]
            .filter(Boolean)
            .map((phone) => phone.trim());
        if (!phones.length) {
            this.popup.add(ErrorPopup, {
                title: _t("Customer Phone Required"),
                body: _t("Make sure that you have selected Customer with Phone."),
            });
            return false;
        }

        // 3- Customer with Phone started with +2
        if (!phones.some((phone) => phone.startsWith("+2"))) {
            console.log("Invalid Customer Phone: ", phones);
            this.popup.add(ErrorPopup, {
                title: _t("Invalid Customer Phone"),
                body: _t("Make sure that you have selected Customer with Phone started with +2."),
            });
            return false;
        }

        return super._isOrderValid(...arguments);
    },
});
