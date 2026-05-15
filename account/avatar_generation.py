import base64
import os
import time

import requests
from django.conf import settings
from django.core.files.base import ContentFile


class AvatarGenerationError(Exception):
    pass


def _build_data_uri(uploaded_image):
    uploaded_image.seek(0)
    content = uploaded_image.read()
    uploaded_image.seek(0)
    mime_type = (getattr(uploaded_image, 'content_type', '') or 'image/jpeg').lower()
    encoded = base64.b64encode(content).decode('ascii')
    return f'data:{mime_type};base64,{encoded}'


def _extract_output_url(output):
    if isinstance(output, str):
        return output
    if isinstance(output, list) and output:
        # Replicate commonly returns a list of URLs
        if isinstance(output[0], str):
            return output[0]
    return None


def generate_avatar_with_replicate(uploaded_image):
    if not getattr(settings, 'AVATAR_GENERATION_ENABLED', False):
        raise AvatarGenerationError('Avatar generation is disabled.')

    token = getattr(settings, 'REPLICATE_API_TOKEN', '')
    version = getattr(settings, 'REPLICATE_AVATAR_MODEL_VERSION', '')
    if not token or not version:
        raise AvatarGenerationError('Replicate is not configured.')

    image_input_field = getattr(settings, 'REPLICATE_AVATAR_IMAGE_FIELD', 'image')
    prompt_field = getattr(settings, 'REPLICATE_AVATAR_PROMPT_FIELD', '').strip()
    prompt_text = getattr(settings, 'REPLICATE_AVATAR_PROMPT', '').strip()
    timeout_seconds = int(getattr(settings, 'REPLICATE_AVATAR_TIMEOUT_SECONDS', 45))

    input_payload = {
        image_input_field: _build_data_uri(uploaded_image),
    }
    if prompt_field and prompt_text:
        input_payload[prompt_field] = prompt_text

    headers = {
        'Authorization': f'Token {token}',
        'Content-Type': 'application/json',
        'Prefer': 'wait=10',
    }

    response = requests.post(
        'https://api.replicate.com/v1/predictions',
        headers=headers,
        json={
            'version': version,
            'input': input_payload,
        },
        timeout=15,
    )
    if response.status_code >= 300:
        raise AvatarGenerationError('Replicate request failed.')

    prediction = response.json()
    status = prediction.get('status')
    deadline = time.time() + timeout_seconds

    while status not in ('succeeded', 'failed', 'canceled') and time.time() < deadline:
        poll_url = prediction.get('urls', {}).get('get')
        if not poll_url:
            break
        time.sleep(1)
        poll_resp = requests.get(poll_url, headers={'Authorization': f'Token {token}'}, timeout=10)
        if poll_resp.status_code >= 300:
            raise AvatarGenerationError('Replicate polling failed.')
        prediction = poll_resp.json()
        status = prediction.get('status')

    if status != 'succeeded':
        raise AvatarGenerationError('Avatar generation timed out or failed.')

    output_url = _extract_output_url(prediction.get('output'))
    if not output_url:
        raise AvatarGenerationError('Replicate returned no output image.')

    image_resp = requests.get(output_url, timeout=20)
    if image_resp.status_code >= 300:
        raise AvatarGenerationError('Could not download generated avatar.')

    filename = f"generated_avatar_{int(time.time())}.png"
    return ContentFile(image_resp.content, name=filename)
