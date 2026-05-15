from io import BytesIO
import re
from urllib.parse import urlencode

import requests
from django.core.files.base import ContentFile
from PIL import Image, ImageDraw, ImageFont


AVATAR_STYLE_CHOICES = (
    ('avataaars', 'Avataaars'),
)

AVATAR_HAIR_COLOR_CHOICES = (
    ('', 'Any hair color'),
    ('0e0e0e', 'Jet black'),
    ('2c1b18', 'Black'),
    ('562306', 'Dark brown'),
    ('724133', 'Brown'),
    ('ac6511', 'Chestnut'),
    ('a55728', 'Auburn'),
    ('d6b370', 'Blonde'),
    ('b55239', 'Red'),
    ('afafaf', 'Platinum'),
    ('9ea0a3', 'Gray'),
    ('592454', 'Burgundy'),
)

AVATAR_GENDER_VIBE_CHOICES = (
    ('neutral', 'Neutral'),
    ('masculine', 'Masculine'),
    ('feminine', 'Feminine'),
)

AVATAR_HAIR_LENGTH_CHOICES = (
    ('short', 'Short'),
    ('long', 'Long'),
)

AVATAR_EYES_CHOICES = (
    ('default', 'Default'),
    ('happy', 'Happy'),
    ('wink', 'Wink'),
    ('surprised', 'Surprised'),
    ('squint', 'Squint'),
    ('closed', 'Closed'),
)

AVATAR_MOUTH_CHOICES = (
    ('smile', 'Smile'),
    ('default', 'Default'),
    ('serious', 'Serious'),
    ('twinkle', 'Twinkle'),
    ('tongue', 'Tongue'),
)

AVATAR_CLOTHING_CHOICES = (
    ('hoodie', 'Hoodie'),
    ('graphicShirt', 'Graphic shirt'),
    ('overall', 'Overall'),
    ('shirtCrewNeck', 'Crew neck'),
    ('shirtVNeck', 'V-neck'),
    ('blazerAndShirt', 'Blazer + shirt'),
)

AVATAR_ACCESSORIES_CHOICES = (
    ('none', 'None'),
    ('round', 'Round glasses'),
    ('prescription01', 'Prescription 1'),
    ('prescription02', 'Prescription 2'),
    ('wayfarers', 'Wayfarers'),
    ('sunglasses', 'Sunglasses'),
    ('kurt', 'Kurt'),
    ('eyepatch', 'Eyepatch'),
)

SKIN_TONE_LEVEL_CHOICES = (
    ('1', 'Very light'),
    ('2', 'Light'),
    ('3', 'Medium light'),
    ('4', 'Medium'),
    ('5', 'Medium dark'),
    ('6', 'Dark'),
)

SKIN_TONE_HEX_SCALE = {
    '1': 'f2d3b1',
    '2': 'e8c39e',
    '3': 'd9a07b',
    '4': 'c6865f',
    '5': 'a56b46',
    '6': '7a4a2f',
}

HEX_COLOR_RE = re.compile(r'^(transparent|[a-fA-F0-9]{6})$')


def normalize_avatar_options(
    style: str,
    hair_color: str,
    gender_vibe: str,
    skin_tone_level: str = '4',
    hair_length: str = 'short',
    glasses: bool = False,
    facial_hair_level: int = 25,
    facial_hair_color: str = '',
    eyes: str = 'default',
    mouth: str = 'smile',
    clothing: str = 'hoodie',
    accessories: str = 'none',
    clothes_color: str = '',
    accessories_color: str = '',
):
    valid_styles = {choice[0] for choice in AVATAR_STYLE_CHOICES}
    valid_gender_vibes = {choice[0] for choice in AVATAR_GENDER_VIBE_CHOICES}
    valid_skin_tones = {choice[0] for choice in SKIN_TONE_LEVEL_CHOICES}
    valid_hair_lengths = {choice[0] for choice in AVATAR_HAIR_LENGTH_CHOICES}
    valid_eyes = {choice[0] for choice in AVATAR_EYES_CHOICES}
    valid_mouth = {choice[0] for choice in AVATAR_MOUTH_CHOICES}
    valid_clothing = {choice[0] for choice in AVATAR_CLOTHING_CHOICES}
    valid_accessories = {choice[0] for choice in AVATAR_ACCESSORIES_CHOICES}

    style = (style or 'avataaars').strip()
    hair_color = (hair_color or '').strip().lower()
    gender_vibe = (gender_vibe or 'neutral').strip()
    skin_tone_level = str(skin_tone_level or '4').strip()
    hair_length = (hair_length or 'short').strip()
    facial_hair_color = (facial_hair_color or '').strip().lower()
    eyes = (eyes or 'default').strip()
    mouth = (mouth or 'smile').strip()
    clothing = (clothing or 'hoodie').strip()
    accessories = (accessories or 'none').strip()
    clothes_color = (clothes_color or '').strip().lower()
    accessories_color = (accessories_color or '').strip().lower()

    if style not in valid_styles:
        style = 'avataaars'
    if hair_color and not HEX_COLOR_RE.match(hair_color):
        hair_color = ''
    if gender_vibe not in valid_gender_vibes:
        gender_vibe = 'neutral'
    if skin_tone_level not in valid_skin_tones:
        skin_tone_level = '4'
    if hair_length not in valid_hair_lengths:
        hair_length = 'short'
    if facial_hair_color and not HEX_COLOR_RE.match(facial_hair_color):
        facial_hair_color = ''
    if eyes not in valid_eyes:
        eyes = 'default'
    if mouth not in valid_mouth:
        mouth = 'smile'
    if clothing not in valid_clothing:
        clothing = 'hoodie'
    if accessories not in valid_accessories:
        accessories = 'none'
    if clothes_color and not HEX_COLOR_RE.match(clothes_color):
        clothes_color = ''
    if accessories_color and not HEX_COLOR_RE.match(accessories_color):
        accessories_color = ''

    glasses = bool(glasses)
    try:
        facial_hair_level = int(facial_hair_level)
    except (TypeError, ValueError):
        facial_hair_level = 25
    facial_hair_level = max(0, min(100, facial_hair_level))

    return (
        style,
        hair_color,
        gender_vibe,
        skin_tone_level,
        hair_length,
        glasses,
        facial_hair_level,
        facial_hair_color,
        eyes,
        mouth,
        clothing,
        accessories,
        clothes_color,
        accessories_color,
    )


def resolve_avatar_style(style: str, gender_vibe: str) -> str:
    # Keep API compatibility with existing call sites.
    del gender_vibe
    return style or 'avataaars'


def _resolve_beard_stage(facial_hair_level: int) -> str:
    if facial_hair_level <= 0:
        return 'off'
    if facial_hair_level <= 33:
        return 'light'
    if facial_hair_level <= 66:
        return 'medium'
    return 'majestic'


def build_dicebear_avatar_url(
    seed: str,
    style: str,
    hair_color: str,
    gender_vibe: str,
    skin_tone_level: str = '4',
    hair_length: str = 'short',
    glasses: bool = False,
    facial_hair_level: int = 25,
    facial_hair_color: str = '',
    eyes: str = 'default',
    mouth: str = 'smile',
    clothing: str = 'hoodie',
    accessories: str = 'none',
    clothes_color: str = '',
    accessories_color: str = '',
    size: int = 512,
    image_format: str = 'png',
) -> str:
    del glasses
    selected_style = resolve_avatar_style(style, gender_vibe)

    query = {
        'seed': seed,
        'size': size,
    }

    if hair_color:
        query['hairColor'] = hair_color
    if skin_tone_level in SKIN_TONE_HEX_SCALE:
        query['skinColor'] = SKIN_TONE_HEX_SCALE[skin_tone_level]

    facial_hair_level = max(0, min(100, int(facial_hair_level)))

    if hair_length == 'short':
        query['top'] = 'shortFlat,shortRound,shortWaved,theCaesar,theCaesarAndSidePart,sides,shavedSides,dreads01,dreads02,frizzle,shaggyMullet,shortCurly'
    elif hair_length == 'long':
        query['top'] = 'longButNotTooLong,straight01,straight02,straightAndStrand,bun,bob,curly,curvy,miaWallace,frida,bigHair'

    query['top'] = query.get('top') or 'shortFlat,shortRound,shortWaved,theCaesar'
    query['eyes'] = eyes
    query['mouth'] = mouth
    query['clothing'] = clothing

    if clothes_color:
        query['clothesColor'] = clothes_color

    if accessories == 'none':
        query['accessoriesProbability'] = 0
    else:
        query['accessories'] = accessories
        query['accessoriesProbability'] = 100
        if accessories_color:
            query['accessoriesColor'] = accessories_color

    beard_stage = _resolve_beard_stage(facial_hair_level)
    if beard_stage == 'off':
        query['facialHairProbability'] = 0
    else:
        beard_style = {
            'light': 'beardLight',
            'medium': 'beardMedium',
            'majestic': 'beardMajestic',
        }[beard_stage]
        query['facialHair'] = beard_style
        query['facialHairProbability'] = 100

    if facial_hair_color:
        query['facialHairColor'] = facial_hair_color
    elif hair_color:
        query['facialHairColor'] = hair_color

    return f"https://api.dicebear.com/9.x/{selected_style}/{image_format}?{urlencode(query)}"


def _fallback_avatar(seed: str) -> ContentFile:
    seed = (seed or 'user').strip()
    initial = (seed[0] if seed else 'U').upper()

    color_int = abs(hash(seed)) % 0xFFFFFF
    bg_hex = f'#{color_int:06x}'

    size = 512
    image = Image.new('RGB', (size, size), bg_hex)
    draw = ImageDraw.Draw(image)

    try:
        font = ImageFont.truetype('DejaVuSans-Bold.ttf', 220)
    except Exception:
        font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), initial, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    x = (size - text_w) // 2
    y = (size - text_h) // 2 - 10
    draw.text((x, y), initial, fill='white', font=font)

    output = BytesIO()
    image.save(output, format='PNG')
    output.seek(0)
    return ContentFile(output.read(), name=f'avatar_random_{seed}.png')


def build_random_avatar_content(
    seed: str,
    style: str = 'avataaars',
    hair_color: str = '',
    gender_vibe: str = 'neutral',
    skin_tone_level: str = '4',
    hair_length: str = 'short',
    glasses: bool = False,
    facial_hair_level: int = 25,
    facial_hair_color: str = '',
    eyes: str = 'default',
    mouth: str = 'smile',
    clothing: str = 'hoodie',
    accessories: str = 'none',
    clothes_color: str = '',
    accessories_color: str = '',
) -> ContentFile:
    seed = (seed or '').strip()
    if not seed:
        raise ValueError('Avatar seed is required.')

    (
        style,
        hair_color,
        gender_vibe,
        skin_tone_level,
        hair_length,
        glasses,
        facial_hair_level,
        facial_hair_color,
        eyes,
        mouth,
        clothing,
        accessories,
        clothes_color,
        accessories_color,
    ) = normalize_avatar_options(
        style,
        hair_color,
        gender_vibe,
        skin_tone_level,
        hair_length,
        glasses,
        facial_hair_level,
        facial_hair_color,
        eyes,
        mouth,
        clothing,
        accessories,
        clothes_color,
        accessories_color,
    )

    url = build_dicebear_avatar_url(
        seed=seed,
        style=style,
        hair_color=hair_color,
        gender_vibe=gender_vibe,
        skin_tone_level=skin_tone_level,
        hair_length=hair_length,
        glasses=glasses,
        facial_hair_level=facial_hair_level,
        facial_hair_color=facial_hair_color,
        eyes=eyes,
        mouth=mouth,
        clothing=clothing,
        accessories=accessories,
        clothes_color=clothes_color,
        accessories_color=accessories_color,
        size=512,
        image_format='png',
    )

    try:
        response = requests.get(url, timeout=8)
        response.raise_for_status()
        return ContentFile(response.content, name=f'avatar_random_{seed}.png')
    except Exception:
        return _fallback_avatar(seed)
