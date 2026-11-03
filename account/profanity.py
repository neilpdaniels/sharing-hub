from functools import lru_cache
import re

import requests


LOCAL_BLOCKED_WORDS = {
    'asshole',
    'bastard',
    'bitch',
    'bullshit',
    'crap',
    'dick',
    'fuck',
    'piss',
    'shit',
    'slut',
    'twat',
    'wanker',
}

# LDNOOBW English list. We use it as an online supplement and keep a local
# fallback so registration still works if the fetch fails.
LDNOOBW_EN_URL = (
    'https://raw.githubusercontent.com/'
    'LDNOOBW/List-of-Dirty-Naughty-Obscene-and-Otherwise-Bad-Words/master/en'
)


@lru_cache(maxsize=1)
def load_blocked_words():
    blocked_words = set(LOCAL_BLOCKED_WORDS)
    try:
        response = requests.get(LDNOOBW_EN_URL, timeout=3)
        response.raise_for_status()
        for line in response.text.splitlines():
            word = line.strip().lower()
            if word and not word.startswith('#'):
                blocked_words.add(word)
    except Exception:
        pass
    return blocked_words


def contains_blocked_word(value):
    """Return True when text contains a configured obscene/prohibited term.

    Used as a light first-line safeguard for usernames and member messages. It
    does not replace reporting or human moderation, which is essential for
    context-dependent hate, threats, scams and obfuscated language.
    """
    value = (value or '').strip().lower()
    if not value:
        return False

    blocked_words = load_blocked_words()
    tokens = [part for part in re.split(r'[^a-z0-9]+', value) if part]
    compact_value = re.sub(r'[^a-z0-9]+', '', value)
    if not compact_value:
        return False
    # Match whole words in prose to avoid false positives such as a prohibited
    # fragment appearing inside an innocent place or product name. Compact
    # matching still catches a deliberately punctuated standalone term.
    return any(word in tokens or compact_value == word for word in blocked_words)


def username_contains_blocked_word(username):
    value = (username or '').strip().lower()
    if not value:
        return False
    blocked_words = load_blocked_words()
    tokens = [part for part in re.split(r'[^a-z0-9]+', value) if part]
    compact_value = re.sub(r'[^a-z0-9]+', '', value)
    return any(
        word in tokens or (len(word) >= 4 and (word in value or word in compact_value))
        for word in blocked_words
    )
