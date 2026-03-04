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
    """Extract plain text body from an email message."""
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            disposition = str(part.get('Content-Disposition', ''))
            if ctype == 'text/plain' and 'attachment' not in disposition:
                payload = part.get_payload(decode=True)
                if payload:
                    return payload.decode(part.get_content_charset() or 'utf-8', errors='replace')
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            return payload.decode(msg.get_content_charset() or 'utf-8', errors='replace')
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

    try:
        conn = imaplib.IMAP4_SSL(host)
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
            conn.logout()
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

            # Split into paragraphs for granular tagging
            paragraphs = [p.strip() for p in body.split('\n\n') if len(p.strip()) > 80]

            for para in paragraphs[:20]:
                items.append({
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
                })

        conn.logout()
        log.info('CFR Daily Brief: extracted %d paragraphs', len(items))

    except Exception as exc:
        log.error('Email ingestion failed: %s', exc)

    return items
