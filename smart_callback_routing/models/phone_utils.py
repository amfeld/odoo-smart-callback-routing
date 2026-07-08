"""Lightweight phone number normalization without external dependencies.

Goal: turn differently formatted caller IDs (3CX delivers sometimes ``+49…``,
sometimes ``0049…``, sometimes ``089 12 34 56``) into a stable, comparable
form, so that outbound recording and inbound lookup match the same number.

No full E.164 validation — just a deterministic normalization that is
sufficient for the sticky-mapping comparison.
"""

# Values considered anonymous / invalid that must never create a mapping.
# Note: intentionally includes German tokens ('anonym', 'unbekannt') because
# 3CX may deliver localized caller-ID placeholders.
ANONYMOUS_TOKENS = {
    '', 'anonymous', 'anonym', 'unknown', 'unbekannt', 'restricted',
    'private', 'withheld', 'unavailable', 'blocked',
}

# Minimum number of digits for a number to be considered plausible (spam guard).
MIN_DIGITS = 5


def normalize_phone(raw, default_country_prefix='49'):
    """Normalizes a phone number to ``+<countrycode><national>``.

    :param raw: raw caller ID / dialed number (str or None).
    :param default_country_prefix: country prefix without ``+`` (default
        Germany = 49), applied to national numbers (leading ``0``).
    :return: normalized number (e.g. ``+491701234567``) or ``None`` if the
        number is anonymous/invalid.
    """
    if not raw:
        return None

    text = str(raw).strip().lower()
    if text in ANONYMOUS_TOKENS:
        return None

    # 3CX sometimes appends suffixes like "@from-internal" or "<...>".
    for sep in ('@', '<', '>', ';'):
        if sep in text:
            text = text.split(sep)[0].strip()

    has_plus = text.lstrip().startswith('+') or text.lstrip().startswith('00')

    # Keep digits only.
    digits = ''.join(ch for ch in text if ch.isdigit())

    if not digits or len(digits) < MIN_DIGITS:
        return None

    # 00 prefix (international dialing) → real plus.
    if digits.startswith('00'):
        digits = digits[2:]
        has_plus = True

    if has_plus:
        return '+' + digits

    # National number with leading 0 → prepend the country prefix.
    if digits.startswith('0'):
        return '+' + default_country_prefix + digits[1:]

    # Already without leading 0 and without plus: best-effort assumption —
    # treat as an international number if it starts with the default prefix,
    # otherwise prepend the default prefix.
    if digits.startswith(default_country_prefix):
        return '+' + digits
    return '+' + default_country_prefix + digits
