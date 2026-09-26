/* Customer page: live total of the chosen items, signature pad and the approve/reject call. No framework on purpose:
 * this page must open fast on a cheap phone over 4G. */
(function () {
    "use strict";
    const bar = document.getElementById("wo-actionbar");
    if (!bar) {
        return;
    }
    const token = bar.dataset.token;
    const dialog = document.getElementById("wo-dialog");
    const form = document.getElementById("wo-form");
    const nameInput = document.getElementById("wo-name");
    const errorBox = document.getElementById("wo-error");
    const title = document.getElementById("wo-dialog-title");
    const signBlock = document.getElementById("wo-sign-block");
    const canvas = document.getElementById("wo-sign");
    const checks = Array.from(document.querySelectorAll(".wo-line__check"));
    const totalOut = document.getElementById("wo-approve-total");
    const money = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
    let mode = "approve";
    let signed = false;

    function refreshTotal() {
        const total = checks.filter((c) => c.checked).reduce((sum, c) => sum + Number(c.dataset.amount || 0), 0);
        totalOut.textContent = money.format(total);
        bar.querySelector("[data-wo-open='approve']").disabled = !checks.some((c) => c.checked);
    }
    checks.forEach((c) => c.addEventListener("change", () => {
        c.closest(".wo-line").classList.toggle("wo-line--rejected", !c.checked);
        refreshTotal();
    }));

    // Signature pad: pointer events cover finger, pen and mouse.
    const ctx = canvas.getContext("2d");
    function sizeCanvas() {
        const ratio = window.devicePixelRatio || 1;
        const rect = canvas.getBoundingClientRect();
        canvas.width = rect.width * ratio;
        canvas.height = rect.height * ratio;
        ctx.scale(ratio, ratio);
        ctx.lineWidth = 2.4;
        ctx.lineCap = "round";
        ctx.strokeStyle = "#111827";
        signed = false;
    }
    let drawing = false;
    canvas.addEventListener("pointerdown", (e) => {
        drawing = true;
        signed = true;
        canvas.setPointerCapture(e.pointerId);
        ctx.beginPath();
        ctx.moveTo(e.offsetX, e.offsetY);
    });
    canvas.addEventListener("pointermove", (e) => {
        if (drawing) {
            ctx.lineTo(e.offsetX, e.offsetY);
            ctx.stroke();
        }
    });
    ["pointerup", "pointercancel", "pointerleave"].forEach((t) => canvas.addEventListener(t, () => (drawing = false)));
    document.getElementById("wo-sign-clear").addEventListener("click", sizeCanvas);

    bar.querySelectorAll("[data-wo-open]").forEach((btn) => btn.addEventListener("click", () => {
        mode = btn.dataset.woOpen;
        title.textContent = document.getElementById(mode === "approve" ? "wo-t-approve" : "wo-t-reject").textContent;
        signBlock.hidden = mode !== "approve";
        errorBox.hidden = true;
        dialog.showModal();
        if (mode === "approve") {
            sizeCanvas();
        }
        nameInput.focus();
    }));
    document.getElementById("wo-cancel").addEventListener("click", () => dialog.close());

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        const submit = document.getElementById("wo-submit");
        submit.disabled = true;
        errorBox.hidden = true;
        const params = {
            approve: mode === "approve",
            name: nameInput.value,
            line_ids: mode === "approve" ? checks.filter((c) => c.checked).map((c) => Number(c.value)) : null,
            signature: mode === "approve" && signed ? canvas.toDataURL("image/png") : null,
        };
        try {
            const response = await fetch(`/os/${token}/decision`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ jsonrpc: "2.0", method: "call", params }),
            });
            const payload = await response.json();
            if (payload.error) {
                throw new Error(payload.error.data?.message || payload.error.message);
            }
            window.location.reload();
        } catch (error) {
            errorBox.textContent = error.message;
            errorBox.hidden = false;
            submit.disabled = false;
        }
    });
    refreshTotal();
})();
