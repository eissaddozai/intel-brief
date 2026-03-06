"""
IMAP email parser for CFR Daily News Brief.
Configure: forward CFR newsletter to a dedicated inbox and set credentials
in pipeline-config.yaml (or environment variables CSE_EMAIL_USER / CSE_EMAIL_PASS).
"""

import email
import imaplib
import logging
import os
import re
from datetime import datetime, timezone, timedelta
from email.header import decode_header
from pathlib import Path

import yaml

_HTML_TAG_RE = re.compile(r'<[^>]+>')
# Subject fragments that indicate a CFR Daily News Brief email
_CFR_SUBJECT_MARKERS = ('cfr', 'council on foreign relations', 'daily news brief')
# Minimum paragraph length — discard footers, unsubscribe blurbs, etc.
_MIN_PARA_LENGTH = 80

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
    """
    Extract plain-text body from an email message.
    Prefers text/plain; falls back to HTML with tags stripped.
    """
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
            text = payload.decode(charset, errors='replace')
            if msg.get_content_type() == 'text/html':
                html = text
            else:
                plain = text

    if plain:
        return plain
    if html:
        # Strip HTML tags and collapse whitespace
        return re.sub(r'\s+', ' ', _HTML_TAG_RE.sub(' ', html)).strip()
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
        conn = imaplib.IMAP4_SSL(host)
        conn.login(user, password)
        conn.select(folder)

        # Normalised UTC timestamp for items
        ts = target_date.strftime('%Y-%m-%dT06:00:00+00:00')

        # Search on target_date; fall back to previous day if brief arrived late
        for search_date in (target_date, target_date - timedelta(days=1)):
            date_str = search_date.strftime('%d-%b-%Y')
            status, ids = conn.search(None, f'(ON {date_str})')
            if status == 'OK' and ids[0]:
                break
        else:
            log.info('No emails found for %s or %s',
                     target_date.date(), (target_date - timedelta(days=1)).date())
            return []

        for msg_id in ids[0].split():
            status, data = conn.fetch(msg_id, '(RFC822)')
            if status != 'OK':
                continue

            raw = data[0][1]
            msg = email.message_from_bytes(raw)

            subject = decode_mime_header(msg.get('Subject', ''))

            # Subject-filter: only process emails that look like CFR Daily Brief
            subject_lower = subject.lower()
            if not any(marker in subject_lower for marker in _CFR_SUBJECT_MARKERS):
                log.debug('Skipping non-CFR email: %s', subject[:80])
                continue

            body = extract_text_from_message(msg)
            if not body:
                continue

            # Split into paragraphs; skip short footers / boilerplate
            paragraphs = [p.strip() for p in body.split('\n\n')
                          if len(p.strip()) >= _MIN_PARA_LENGTH]

            for para in paragraphs[:20]:
                items.append({
                    'source_id': 'cfr_daily',
                    'source_name': 'CFR Daily News Brief',
                    'tier': 2,
                    'domains': [],   # triage classifier assigns domains via keywords
                    'title': subject,
                    'text': para,
                    'full_content': para,
                    'url': '',
                    'timestamp': ts,
                    'verification_status': 'reported',
                    'method': 'email',
                })

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
