"""Phone number utilities for formatting, validation, and masking UK mobile numbers."""


def format_to_e164(raw_number):
    """
    Convert raw UK mobile number input to E.164 format (+44XXXXXXXXXX).

    Handles various input formats:
    - 07xxx xxx xxx → +447xxx
    - +447xxx → +447xxx
    - 00447xxx → +447xxx
    - 447xxx → +447xxx

    Args:
        raw_number (str): Raw phone number input

    Returns:
        str: Formatted E.164 phone number or empty string if invalid
    """
    if not raw_number:
        return ''

    domestic = normalize_to_domestic(raw_number)
    if not is_valid_uk_phone(domestic):
        return ''
    return '+44' + domestic[1:]


def normalize_to_domestic(raw_number):
    """
    Convert phone number to UK domestic format (0XXXXXXXXXX).

    Args:
        raw_number (str): Raw phone number input

    Returns:
        str: Normalized domestic format number
    """
    digits = ''.join(ch for ch in (raw_number or '') if ch.isdigit())
    if digits.startswith('0044'):
        digits = digits[2:]
    if digits.startswith('44'):
        digits = '0' + digits[2:]
    elif digits.startswith('7') and len(digits) == 10:
        digits = '0' + digits
    return digits


def mask_mobile_number(raw_number):
    """
    Mask a mobile number for display, showing only last 4 digits.

    Args:
        raw_number (str): Raw phone number to mask

    Returns:
        str: Masked phone number (e.g., '******1234')
    """
    digits = ''.join(ch for ch in (raw_number or '') if ch.isdigit())
    if len(digits) < 4:
        return 'your mobile number'
    return '******' + digits[-4:]


def is_valid_uk_phone(raw_number):
    """
    Check if a phone number is a valid UK mobile format.

    Args:
        raw_number (str): Phone number to validate

    Returns:
        bool: True if valid UK mobile number
    """
    if not raw_number:
        return False

    digits = ''.join(ch for ch in (raw_number or '') if ch.isdigit())

    domestic = normalize_to_domestic(digits)
    return len(domestic) == 11 and domestic.startswith('07')
