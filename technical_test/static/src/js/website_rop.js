/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";
import { jsonrpc } from "@web/core/network/rpc_service";

publicWidget.registry.WebsiteROP = publicWidget.Widget.extend({
    selector: "#wrap",
    events: {
        "click .btn-update-qty": "_onOpenUpdateQtyModal",
        "click #btnSubmitUpdateQty": "_onSubmitUpdateQty",
    },

    start() {
        this._super(...arguments);
        if (this.el.querySelector("#realtime-rop-container")) {
            this._startRealtimePolling();
        }
    },

    destroy() {
        if (this._pollingInterval) {
            clearInterval(this._pollingInterval);
        }
        this._super(...arguments);
    },

    _getBootstrapModal() {
        return (window.bootstrap && window.bootstrap.Modal) || window.Modal;
    },

    _onOpenUpdateQtyModal(ev) {
        const btn = ev.currentTarget;
        const tmplId = btn.getAttribute("data-product-tmpl-id");
        const prodId = btn.getAttribute("data-product-id");
        const prodName = btn.getAttribute("data-product-name");
        const currQty = btn.getAttribute("data-current-qty");

        const modalEl = document.getElementById("updateQtyModal");
        const Modal = this._getBootstrapModal();
        if (!modalEl || !Modal) return;

        document.getElementById("modalProductTmplId").value = tmplId || "";
        document.getElementById("modalProductId").value = prodId || "";
        document.getElementById("modalProductName").textContent = prodName || "";
        document.getElementById("modalCurrentQty").textContent = currQty || "0";
        document.getElementById("modalNewQty").value = parseInt(currQty, 10) || 0;

        const alertBox = document.getElementById("modalAlert");
        alertBox.className = "alert d-none";
        alertBox.textContent = "";

        const modal = typeof Modal.getOrCreateInstance === "function"
            ? Modal.getOrCreateInstance(modalEl)
            : new Modal(modalEl);
        modal.show();
    },

    async _onSubmitUpdateQty() {
        const tmplId = document.getElementById("modalProductTmplId").value;
        const prodId = document.getElementById("modalProductId").value;
        const newQty = document.getElementById("modalNewQty").value;
        const alertBox = document.getElementById("modalAlert");
        const submitBtn = document.getElementById("btnSubmitUpdateQty");

        if (!/^\d+$/.test(newQty)) {
            alertBox.className = "alert alert-danger";
            alertBox.textContent = "Please enter a valid non-negative integer quantity.";
            return;
        }

        submitBtn.disabled = true;
        submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1" role="status"></span> Updating...';

        try {
            const result = await jsonrpc("/shop/rop/update-qty", {
                product_tmpl_id: tmplId ? parseInt(tmplId, 10) : null,
                product_id: prodId ? parseInt(prodId, 10) : null,
                new_qty: parseInt(newQty, 10),
            });

            if (result.error) {
                alertBox.className = "alert alert-danger";
                alertBox.textContent = result.error;
            } else {
                alertBox.className = "alert alert-success";
                alertBox.textContent = result.message || "Quantity updated successfully!";

                // Notify the acting user that the other warehouse admins were alerted.
                if (result.notified_count) {
                    this._showToast(result.message, "Warehouse admins notified");
                }

                // Update card in UI
                const card = document.querySelector(`.rop-product-card[data-product-id="${tmplId}"]`);
                if (card) {
                    const qtySpan = card.querySelector(".product-qty-display");
                    if (qtySpan) {
                        qtySpan.textContent = result.new_qty;
                    }
                    const btn = card.querySelector(".btn-update-qty");
                    if (btn) {
                        btn.setAttribute("data-current-qty", result.new_qty);
                    }
                }

                setTimeout(() => {
                    const modalEl = document.getElementById("updateQtyModal");
                    const Modal = this._getBootstrapModal();
                    const modal = Modal && Modal.getInstance
                        ? Modal.getInstance(modalEl)
                        : null;
                    if (modal) modal.hide();
                    // If qty is now >= 5, reload or fade out card from low-stock view
                    if (parseInt(newQty, 10) >= 5 && card) {
                        card.style.transition = "opacity 0.5s";
                        card.style.opacity = "0.3";
                    }
                }, 1000);
            }
        } catch (err) {
            alertBox.className = "alert alert-danger";
            alertBox.textContent = "An error occurred while updating quantity.";
            console.error(err);
        } finally {
            submitBtn.disabled = false;
            submitBtn.innerHTML = '<i class="fa fa-check me-1"></i>Apply &amp; Notify';
        }
    },

    _showToast(message, title) {
        let container = document.getElementById("rop-toast-container");
        if (!container) {
            container = document.createElement("div");
            container.id = "rop-toast-container";
            container.className = "toast-container position-fixed bottom-0 end-0 p-3";
            document.body.appendChild(container);
        }

        const toastEl = document.createElement("div");
        toastEl.className = "toast align-items-center text-bg-primary border-0";
        toastEl.setAttribute("role", "alert");
        toastEl.setAttribute("aria-live", "assertive");
        toastEl.setAttribute("aria-atomic", "true");

        const wrapper = document.createElement("div");
        wrapper.className = "d-flex";
        const body = document.createElement("div");
        body.className = "toast-body";
        if (title) {
            const strong = document.createElement("strong");
            strong.className = "d-block";
            strong.textContent = title;
            body.append(strong);
        }
        body.append(message || "");
        const closeBtn = document.createElement("button");
        closeBtn.type = "button";
        closeBtn.className = "btn-close btn-close-white me-2 m-auto";
        closeBtn.setAttribute("data-bs-dismiss", "toast");
        closeBtn.setAttribute("aria-label", "Close");
        wrapper.append(body, closeBtn);
        toastEl.append(wrapper);
        container.appendChild(toastEl);

        const Toast = (window.bootstrap && window.bootstrap.Toast) || window.Toast;
        if (Toast) {
            const toast = new Toast(toastEl, { delay: 5000 });
            toastEl.addEventListener("hidden.bs.toast", () => toastEl.remove());
            toast.show();
        } else {
            setTimeout(() => toastEl.remove(), 5000);
        }
    },

    _startRealtimePolling() {
        this._pollRealtimeData();
        this._pollingInterval = setInterval(() => {
            this._pollRealtimeData();
        }, 4000);
    },

    async _pollRealtimeData() {
        try {
            const page = Number(new URLSearchParams(window.location.search).get("page")) || 1;
            const data = await jsonrpc("/shop/realtime-rop/data", { page, limit: 100 });
            if (!data || !data.products) return;

            const grid = document.getElementById("realtime-products-grid");
            const countEl = document.getElementById("realtime-products-count");
            const emptyAlert = document.getElementById("realtime-empty-alert");

            if (countEl) {
                countEl.textContent = data.count;
            }

            if (data.count === 0) {
                if (grid) grid.innerHTML = "";
                if (emptyAlert) emptyAlert.classList.remove("d-none");
                return;
            }

            if (emptyAlert) emptyAlert.classList.add("d-none");

            if (grid) {
                grid.replaceChildren(...data.products.map((product) => {
                    const column = document.createElement("div");
                    column.className = "col realtime-product-card";
                    column.dataset.productId = product.id;

                    const card = document.createElement("div");
                    card.className = "card h-100 shadow-sm border-success";
                    const imageContainer = document.createElement("div");
                    imageContainer.className = "position-relative";
                    const image = document.createElement("img");
                    image.src = product.image_url;
                    image.alt = product.name;
                    image.className = "card-img-top p-3";
                    image.style.cssText = "height: 220px; object-fit: contain;";
                    imageContainer.append(image);

                    const quantityBadge = document.createElement("span");
                    quantityBadge.className = "position-absolute top-0 end-0 badge bg-success m-2";
                    quantityBadge.append("Qty: ");
                    const quantity = document.createElement("span");
                    quantity.className = "product-qty-val";
                    quantity.textContent = product.qty_available;
                    quantityBadge.append(quantity);
                    imageContainer.append(quantityBadge);

                    const body = document.createElement("div");
                    body.className = "card-body d-flex flex-column";
                    const name = document.createElement("h5");
                    name.className = "card-title text-truncate";
                    name.title = product.name;
                    name.textContent = product.name;
                    body.append(name);

                    const details = document.createElement("div");
                    details.className = "mt-auto d-flex justify-content-between align-items-center";
                    const price = document.createElement("span");
                    price.className = "fw-bold text-success fs-5";
                    price.textContent = `${product.currency} ${Number(product.list_price).toFixed(2)}`;
                    const code = document.createElement("span");
                    code.className = "badge bg-light text-dark border";
                    code.textContent = `Code: ${product.default_code || "N/A"}`;
                    details.append(price, code);
                    body.append(details);
                    card.append(imageContainer, body);
                    column.append(card);
                    return column;
                }));
            }
        } catch (e) {
            console.error("Error polling real-time ROP data:", e);
        }
    },
});

export default publicWidget.registry.WebsiteROP;
