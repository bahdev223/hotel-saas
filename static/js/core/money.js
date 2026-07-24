export function formatMoney(amount, currency = 'FCFA') {
    const val = typeof amount === 'string' ? parseFloat(amount) : amount;
    if (isNaN(val)) return `0 ${currency}`;
    return val.toLocaleString('fr-FR', { minimumFractionDigits: 0, maximumFractionDigits: 0 }) + ' ' + currency;
}

export function parseMoney(value) {
    if (typeof value === 'number') return value;
    const cleaned = String(value).replace(/[^0-9.,\-]/g, '').replace(',', '.');
    return parseFloat(cleaned) || 0;
}
