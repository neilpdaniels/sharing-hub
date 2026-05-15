"""Phone number utilities for formatting, validation, and masking UK mobile numbers."""


def format_to_e164(raw_number):
    """
    Convert raw UK mobile number input to E.164 format (+44XXXXXXXXXX).

    Handles various input formats:
    - 07xxx xxx xxx → +447xxx
    - +447xxx → +447xxx
    - 007xxx → +447xxx
    - 447xxx → +447xxx

    Args:
        raw_number (str): Raw phone number input

    Returns:
        str: Formatted E.164 phone number or empty string if invalid
    """
    if not raw_number:
        return ''

    # Remove all spaces and dashes
    cleaned = raw_number.replace(' ', '').replace('-', '')

    # Handle +00 prefix
    if cleaned.startswith('00'):
        return '+' + cleaned[2:]

    # Extract only digits
    digits = ''.join(ch for ch in cleaned if ch.isdigit())

    # Handle 44 prefix (UK international code without +)
    if digits.startswith('44'):
        return '+' + digits

    # Handle 0 prefix (UK domestic format)
    if digits.startswith('0'):
        return '+44' + digits[1:]

    # Default: assume missing 0 prefix and add UK country code
    return '+44' + digits


def normalize_to_domestic(raw_number):
    """
    Convert phone number to UK domestic format (0XXXXXXXXXX).

    Args:
        raw_number (str): Raw phone number input

    Returns:
        str: Normalized domestic format number
    """
    number = (raw_number or '').strip()

    # Strip leading + and country code if user typed +44
    if number.startswith('+44'):
        number = '0' + number[3:].lstrip()

    # If no leading 0, prepend one
    if number and not number.startswith('0'):
        number = '0' + number

    # Remove spaces/dashes for storage
    return number.replace(' ', '').replace('-', '')


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

    # UK mobile numbers should have 11 digits (including leading 0)
    # or 12 digits (with 44 prefix)
    if digits.startswith('44'):
        return len(digits) == 12
    elif digits.startswith('0'):
        return len(digits) == 11
    else:
        # If no prefix, should be 10 digits
        return len(digits) == 10
