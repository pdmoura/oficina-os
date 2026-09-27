import { _t } from "@web/core/l10n/translation";
import { user } from "@web/core/user";

const { DateTime } = luxon;

/**
 * OWL hoists the names an event-handler arrow calls (`() => set("x", 1)`) into locals and calls them bare, so a
 * screen's methods lose `this` there. Screens bind their own methods once in setup().
 */
export function bindMethods(component) {
    const proto = Object.getPrototypeOf(component);
    for (const name of Object.getOwnPropertyNames(proto)) {
        const descriptor = Object.getOwnPropertyDescriptor(proto, name);
        if (name !== "constructor" && name !== "setup" && typeof descriptor.value === "function") {
            component[name] = descriptor.value.bind(component);
        }
    }
}

/** The user's theme for the app screens ("dark" or "light"), kept in their Odoo user settings. */
export function workshopTheme() {
    return user.settings.workshop_theme === "light" ? "light" : "dark";
}

export function saveWorkshopTheme(theme) {
    return user.setUserSettings("workshop_theme", theme);
}

/** CSS variables for the company's accent; the light theme adds the darker shade used for text on white. */
export function brandStyle(company, theme) {
    if (!company) {
        return "";
    }
    const style = `--wo-accent: ${company.accent}; --wo-accent-ink: ${company.accent_ink};`;
    return theme === "light" ? `${style} --wo-accent-text: ${company.accent_text};` : style;
}

/** 'abc-1d23' -> 'ABC1D23' */
export function normalizePlate(value) {
    return (value || "").replace(/[^a-z0-9]/gi, "").toUpperCase().slice(0, 7);
}

export function isValidPlate(plate) {
    return /^[A-Z]{3}[0-9][A-Z0-9][0-9]{2}$/.test(plate);
}

/** Old plates are shown as ABC-1234, Mercosur plates as ABC1D23. */
export function displayPlate(plate) {
    plate = normalizePlate(plate);
    return plate.length === 7 && /\d/.test(plate[4]) ? `${plate.slice(0, 3)}-${plate.slice(3)}` : plate;
}

export function parseServerDate(value) {
    return value ? DateTime.fromSQL(value, { zone: "utc" }).toLocal() : null;
}

export function elapsedSince(value, now = DateTime.now()) {
    const since = parseServerDate(value);
    if (!since) {
        return "";
    }
    const minutes = Math.max(0, Math.floor(now.diff(since, "minutes").minutes));
    if (minutes < 60) {
        return _t("%(m)s min", { m: minutes });
    }
    const hours = Math.floor(minutes / 60);
    if (hours < 24) {
        return _t("%(h)sh %(m)smin", { h: hours, m: minutes % 60 });
    }
    return _t("%(d)sd %(h)sh", { d: Math.floor(hours / 24), h: hours % 24 });
}

export function shortDate(value) {
    const date = parseServerDate(value);
    return date ? date.toFormat("dd/MM HH:mm") : "";
}

/**
 * Shrinks a phone photo before upload: a 12 MP picture (4-6 MB) becomes ~300 KB at 1600 px, which matters on 4G
 * in a workshop yard and keeps the database or Cloudinary account small.
 */
export async function compressImage(file, maxSide = 1600, quality = 0.82) {
    let source;
    try {
        source = await createImageBitmap(file, { imageOrientation: "from-image" });
    } catch {
        source = await new Promise((resolve, reject) => {
            const img = new Image();
            img.onload = () => resolve(img);
            img.onerror = reject;
            img.src = URL.createObjectURL(file);
        });
    }
    const width = source.width || source.naturalWidth;
    const height = source.height || source.naturalHeight;
    const scale = Math.min(1, maxSide / Math.max(width, height));
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(width * scale);
    canvas.height = Math.round(height * scale);
    canvas.getContext("2d").drawImage(source, 0, 0, canvas.width, canvas.height);
    return new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", quality));
}

function blobToBase64(blob) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(String(reader.result).split(",")[1]);
        reader.onerror = reject;
        reader.readAsDataURL(blob);
    });
}

/** Sends a photo to Cloudinary (signed by the server) or to Odoo, and returns the refreshed order. */
export async function uploadPhoto(orm, orderId, file, kind) {
    const blob = await compressImage(file);
    const ticket = await orm.call("workshop.order.photo", "upload_ticket", []);
    if (ticket.storage === "cloudinary") {
        const form = new FormData();
        form.append("file", blob, "photo.jpg");
        form.append("api_key", ticket.api_key);
        form.append("timestamp", ticket.timestamp);
        form.append("signature", ticket.signature);
        form.append("folder", ticket.folder);
        const response = await fetch(ticket.url, { method: "POST", body: form });
        const result = await response.json();
        if (!response.ok || result.error) {
            throw new Error(result.error?.message || _t("Cloudinary did not accept the photo."));
        }
        return orm.call("workshop.order.photo", "add_photo", [orderId, {
            secure_url: result.secure_url, public_id: result.public_id, kind,
        }]);
    }
    return orm.call("workshop.order.photo", "add_photo", [orderId, {
        data: await blobToBase64(blob), name: `photo-${Date.now()}.jpg`, kind,
    }]);
}

/** Opens WhatsApp (or the phone's share sheet) with the customer link. */
export async function shareLink(url, text) {
    if (navigator.share) {
        try {
            await navigator.share({ title: text, text, url });
            return;
        } catch {
            // user closed the sheet: fall back to WhatsApp below only if sharing is unsupported
            return;
        }
    }
    window.open(`https://wa.me/?text=${encodeURIComponent(`${text} ${url}`)}`, "_blank");
}
