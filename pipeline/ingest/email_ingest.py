"""
IMAP email parser for CFR Daily News Brief.
Configure: forward CFR newsletter to a dedicated inbox and set credentials
in pipeline-config.yaml (or environment variables CSE_EMAIL_USER / CSE_EMAIL_PASS).
"""

import email
import imaplib
import logging
import os
from datetime import datetime, timezone, timedelta
from email.header import decode_header
from pathlib import Path

import yaml

from ingest.relevance import filter_relevant

log = logging.getLogger(__name__)

CONFIG_FILE = Path(__file__).parent.parent.parent / 'pipeline-config.yaml'


def load_email_config() -> dict:
    if CONFIG_FILE.exists():
        cfg = yaml.safe_load(CONFIG_FILE.read_text(encoding='utf-8'))
        return cfg.get('email', {})
    return {}


def decode_mime_header(value: str) -> str:
    parts = decode_header(value)
    result = []
    for part, enc in parts:
        if isinstance(part, bytes):
            result.append(part.decode(enc or 'utf-8', errors='replace'))
        else:
            result.append(part)
    return ''.join(result)


def extract_text_from_message(msg: email.message.Message) -> str:
    """Extract plain text body from an email message.

    Falls back to stripping HTML tags from text/html parts if no text/plain
    part is present (common for modern newsletter formats).
    """
    import re as _re
    _TAG_RE = _re.compile(r'<[^>]+>')

    plain: str = ''
    html: str = ''

    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            disposition = str(part.get('Content-Disposition', ''))
            if 'attachment' in disposition:
                continue
            payload = part.get_payload(decode=True)
            if not payload:
                continue
            charset = part.get_content_charset() or 'utf-8'
            decoded = payload.decode(charset, errors='replace')
            if ctype == 'text/plain' and not plain:
                plain = decoded
            elif ctype == 'text/html' and not html:
                html = decoded
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or 'utf-8'
            decoded = payload.decode(charset, errors='replace')
            ctype = msg.get_content_type()
            if ctype == 'text/html':
                html = decoded
            else:
                plain = decoded

    if plain:
        return plain
    if html:
        # Strip tags and collapse whitespace as a last-resort fallback
        text = _TAG_RE.sub(' ', html)
        return ' '.join(text.split())
    return ''


def ingest_email(target_date: datetime, config: dict | None = None) -> list[dict]:
    """
    Connect to IMAP inbox, find CFR Daily Brief for target_date.
    Returns list of RawItem dicts.

    Requires:
        pipeline-config.yaml with email.imap_host, imap_user, imap_pass, folder
        OR environment variables: CSE_EMAIL_USER, CSE_EMAIL_PASS
    """
    cfg = load_email_config()

    host = cfg.get('imap_host', 'imap.gmail.com')
    port = int(cfg.get('imap_port', 993))
    user = os.environ.get('CSE_EMAIL_USER') or cfg.get('imap_user', '')
    password = os.environ.get('CSE_EMAIL_PASS') or cfg.get('imap_pass', '')
    folder = cfg.get('folder', 'CFR-Daily')

    if not user or not password:
        log.warning(
            'Email credentials not configured. '
            'Set CSE_EMAIL_USER and CSE_EMAIL_PASS environment variables '
            'or configure pipeline-config.yaml email section.'
        )
        return []

    items: list[dict] = []
    conn: imaplib.IMAP4_SSL | None = None

    try:
        conn = imaplib.IMAP4_SSL(host, port)
        conn.login(user, password)
        conn.select(folder)

        # Search for emails from CFR on or near target_date
        date_str = target_date.strftime('%d-%b-%Y')
        status, ids = conn.search(None, f'(ON {date_str})')

        if status != 'OK' or not ids[0]:
            # Try previous day (brief may arrive late)
            prev = target_date - timedelta(days=1)
            prev_str = prev.strftime('%d-%b-%Y')
            status, ids = conn.search(None, f'(ON {prev_str})')

        if not ids[0]:
            log.info('No CFR Daily Brief found for %s', target_date.date())
            return []

        for msg_id in ids[0].split():
            status, data = conn.fetch(msg_id, '(RFC822)')
            if status != 'OK':
                continue

            raw = data[0][1]
            msg = email.message_from_bytes(raw)

            subject = decode_mime_header(msg.get('Subject', ''))
            body = extract_text_from_message(msg)

            if not body:
                continue

            # Normalise Windows CRLF line endings before paragraph splitting
            body = body.replace('\r\n', '\n')

            # Split into paragraphs for granular tagging
            paragraphs = [p.strip() for p in body.split('\n\n') if len(p.strip()) > 80]

            # Build candidate items then apply relevance filter to drop
            # headers, footers, unsubscribe notices, and off-topic blurbs
            candidates = [
                {
                    'source_id': 'cfr_daily',
                    'source_name': 'CFR Daily News Brief',
                    'tier': 2,
                    'domains': ['d4'],  # Primary: Diplomatic
                    'title': subject,
                    'text': para,
                    'full_content': para,
                    'url': '',
                    'timestamp': target_date.isoformat(),
                    'verification_status': 'reported',
                    'method': 'email',
                }
                for para in paragraphs[:20]
            ]
            relevant = filter_relevant(candidates)
            items.extend(relevant)

        log.info('CFR Daily Brief: extracted %d paragraphs', len(items))

    except Exception as exc:
        log.error('Email ingestion failed: %s', exc)

    finally:
        if conn is not None:
            try:
                conn.logout()
            except Exception:
                pass

    return items
