"""
recruiting_sync.py
==================
Reads your Gmail for recruiting emails and saves a data.json file.
100% FREE - no AI API needed. Uses smart keyword detection instead.
"""

import os
import json
import base64
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# ── CONFIG ───────────────────────────────────────────────────────────────────

GMAIL_SEARCH_QUERY = (
    'subject:(recruiting OR kicker OR football OR "scholarship offer" OR "official visit" '
    'OR "camp invitation" OR "interested in" OR "recruiting questionnaire") '
    '-from:me'
)

MAX_EMAILS = 100
OUTPUT_FILE = "data.json"
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

# ── GMAIL AUTH ────────────────────────────────────────────────────────────────

def get_gmail_service():
    creds = None

    gmail_token = os.environ.get('GMAIL_TOKEN')
    if gmail_token:
        print("🔑 Using GMAIL_TOKEN from GitHub secret...")
        token_data = json.loads(gmail_token)
        creds = Credentials.from_authorized_user_info(token_data, SCOPES)
    elif os.path.exists('token.json'):
        print("🔑 Using local token.json...")
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)

    if creds and creds.expired and creds.refresh_token:
        print("🔄 Refreshing token...")
        creds.refresh(Request())
        if not os.environ.get('GMAIL_TOKEN'):
            with open('token.json', 'w') as f:
                f.write(creds.to_json())

    if not creds or not creds.valid:
        if os.environ.get('GMAIL_TOKEN'):
            raise Exception("❌ GMAIL_TOKEN secret is invalid or expired. Re-run locally to refresh.")
        print("🌐 Opening browser for Gmail authorization...")
        flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
        creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as f:
            f.write(creds.to_json())
        print("✅ token.json saved!")

    return build('gmail', 'v1', credentials=creds)

# ── EMAIL PARSING ─────────────────────────────────────────────────────────────

def get_email_body(payload):
    if payload.get('mimeType') == 'text/plain':
        data = payload.get('body', {}).get('data', '')
        if data:
            return base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
    if payload.get('mimeType', '').startswith('multipart'):
        for part in payload.get('parts', []):
            body = get_email_body(part)
            if body:
                return body
    return ''

def parse_email(service, msg_id):
    msg = service.users().messages().get(userId='me', id=msg_id, format='full').execute()
    headers = {h['name']: h['value'] for h in msg['payload'].get('headers', [])}

    subject = headers.get('Subject', '(No Subject)')
    sender = headers.get('From', '')
    date_str = headers.get('Date', '')

    try:
        date = parsedate_to_datetime(date_str)
        date_iso = date.strftime('%Y-%m-%d')
    except:
        date_iso = datetime.now().strftime('%Y-%m-%d')

    sender_name = re.match(r'^([^<]+)', sender)
    sender_name = sender_name.group(1).strip() if sender_name else sender

    body = get_email_body(msg['payload'])
    body_truncated = body[:3000] if len(body) > 3000 else body

    return {
        'id': msg_id,
        'subject': subject,
        'sender': sender,
        'senderName': sender_name,
        'date': date_iso,
        'body': body_truncated,
        'snippet': msg.get('snippet', ''),
    }

# ── FREE RULE-BASED CLASSIFICATION ───────────────────────────────────────────

# Known D1, D2, D3 keywords to help tag division
D1_KEYWORDS = [
    'sec ', 'big ten', 'big 12', 'acc ', 'pac-12', 'pac 12', 'american athletic',
    'mountain west', 'sun belt', 'conference usa', 'mac ', 'mid-american',
    'division i', 'division 1', 'fbs', 'fcs'
]
D2_KEYWORDS = ['division ii', 'division 2', 'division two', 'super region', 'gsac', 'nsic', 'gliac']
D3_KEYWORDS = ['division iii', 'division 3', 'division three', 'd3', 'nescac', 'odac', 'centennial']

OFFER_KEYWORDS = ['scholarship offer', 'offer of admission', 'full scholarship', 'we are offering',
                  'pleased to offer', 'official offer', 'extend an offer', 'offer you a scholarship']
VISIT_KEYWORDS = ['official visit', 'unofficial visit', 'campus visit', 'visit us', 'invite you to visit',
                  'come visit', 'visit our campus', 'visit weekend']
CAMP_KEYWORDS = ['camp', 'combine', 'showcase', 'clinic', 'kicking camp', 'prospect day']
SCHOLARSHIP_KEYWORDS = ['scholarship', 'full ride', 'financial aid', 'athletic scholarship', 'tuition']

SCHOOL_PATTERNS = [
    r'university of [\w\s]+',
    r'[\w\s]+ university',
    r'[\w\s]+ college',
    r'[\w\s]+ state university',
    r'[\w\s]+ state college',
]

NOT_RECRUITING = ['unsubscribe', 'newsletter', 'promo', 'sale', 'deal', 'offer expires',
                  'click here to unsubscribe', 'marketing', 'advertisement']


def extract_school(sender, body, subject):
    """Try to extract school name from sender domain or body text."""
    # Try to find school name in body
    text = (body + ' ' + subject).lower()
    for pattern in SCHOOL_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            name = match.group(0).strip().title()
            if len(name) > 5:
                return name

    # Try sender name (e.g. "Coach Smith <coach@umich.edu>")
    sender_name = re.match(r'^([^<@]+)', sender)
    if sender_name:
        name = sender_name.group(1).strip()
        if name and len(name) > 3:
            return name

    # Try email domain (umich.edu -> University of Michigan style)
    domain_match = re.search(r'@([\w.]+\.edu)', sender)
    if domain_match:
        domain = domain_match.group(1).replace('.edu', '').replace('.', ' ').title()
        return domain

    return 'Unknown School'


def extract_coach(sender, body):
    """Try to extract coach name."""
    # Look for "Coach [Name]" or "- [Name]" signature patterns
    coach_match = re.search(r'coach\s+([A-Z][a-z]+\s+[A-Z][a-z]+)', body, re.IGNORECASE)
    if coach_match:
        return 'Coach ' + coach_match.group(1).title()

    signed_match = re.search(r'(?:sincerely|regards|best|go \w+)[,\n\s]+([A-Z][a-z]+ [A-Z][a-z]+)', body, re.IGNORECASE)
    if signed_match:
        return signed_match.group(1).title()

    sender_name = re.match(r'^([^<]+)', sender)
    if sender_name:
        name = sender_name.group(1).strip().strip('"')
        if name and '@' not in name and len(name) > 3:
            return name

    return 'Recruiting Staff'


def classify_email(email):
    """Rule-based classification - completely free."""
    text = ((email['subject'] or '') + ' ' + (email['body'] or '') + ' ' + (email['snippet'] or '')).lower()

    # Check if this is spam/not recruiting
    for kw in NOT_RECRUITING:
        if kw in text:
            return None

    # Must contain at least one recruiting keyword to be included
    recruiting_keywords = ['kicker', 'recruit', 'football', 'scholarship', 'visit', 'offer',
                           'camp', 'program', 'roster', 'signing', 'commit', 'athletic']
    if not any(kw in text for kw in recruiting_keywords):
        return None

    # Detect tags
    tags = []

    if any(kw in text for kw in OFFER_KEYWORDS):
        tags.append('offer')
    if any(kw in text for kw in SCHOLARSHIP_KEYWORDS):
        if 'scholarship' not in [t for t in tags]:
            tags.append('scholarship')
    if any(kw in text for kw in VISIT_KEYWORDS):
        tags.append('visit')
    if any(kw in text for kw in CAMP_KEYWORDS):
        tags.append('camp')

    # Division detection
    if any(kw in text for kw in D1_KEYWORDS):
        tags.append('d1')
    elif any(kw in text for kw in D2_KEYWORDS):
        tags.append('d2')
    elif any(kw in text for kw in D3_KEYWORDS):
        tags.append('d3')

    # Build a simple summary from the snippet + detected tags
    summary_parts = []
    if 'offer' in tags:
        summary_parts.append("📩 Scholarship offer received.")
    if 'visit' in tags:
        summary_parts.append("✈️ Campus visit mentioned.")
    if 'camp' in tags:
        summary_parts.append("⛺ Camp or showcase invitation.")

    # Use first 2 sentences of snippet as summary base
    snippet = email['snippet'] or ''
    sentences = re.split(r'(?<=[.!?])\s+', snippet)
    base_summary = ' '.join(sentences[:2]) if sentences else snippet[:200]

    summary = ' '.join(summary_parts)
    if base_summary:
        summary = (summary + ' ' + base_summary).strip()
    if not summary:
        summary = f"Email from {email['senderName']} regarding football recruiting."

    school = extract_school(email['sender'], email['body'] or '', email['subject'])
    coach = extract_coach(email['sender'], email['body'] or '')

    return {
        'school': school,
        'coach': coach,
        'summary': summary[:400],
        'tags': tags,
    }

# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    print("🏈 Recruiting Email Sync Starting (FREE mode)...")
    print("=" * 50)

    existing_ids = set()
    existing_emails = []
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE) as f:
            old_data = json.load(f)
            existing_emails = old_data.get('emails', [])
            existing_ids = {e['id'] for e in existing_emails}
        print(f"📂 Found {len(existing_emails)} existing emails")

    print("🔑 Connecting to Gmail...")
    service = get_gmail_service()

    print("🔍 Searching Gmail...")
    results = service.users().messages().list(
        userId='me', q=GMAIL_SEARCH_QUERY, maxResults=MAX_EMAILS
    ).execute()

    messages = results.get('messages', [])
    new_messages = [m for m in messages if m['id'] not in existing_ids]
    print(f"📧 Found {len(messages)} total, {len(new_messages)} new to process")

    if not new_messages:
        print("✅ Nothing new!")
    else:
        new_emails = []
        for i, msg in enumerate(new_messages):
            print(f"  [{i+1}/{len(new_messages)}] Processing...")
            try:
                email = parse_email(service, msg['id'])
                classification = classify_email(email)

                if classification is None:
                    print(f"    ⏭ Skipping (not recruiting): {email['subject']}")
                    continue

                merged = {
                    'id': email['id'],
                    'school': classification['school'],
                    'coach': classification['coach'],
                    'subject': email['subject'],
                    'summary': classification['summary'],
                    'body': email['body'],
                    'date': email['date'],
                    'tags': classification['tags'],
                    'unread': True,
                }
                new_emails.append(merged)
                print(f"    ✅ {classification['school']} — {email['subject'][:50]}")
            except Exception as e:
                print(f"    ❌ Error: {e}")

        existing_emails = new_emails + existing_emails

    output = {
        'lastSynced': datetime.now(timezone.utc).isoformat(),
        'emails': existing_emails
    }
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(output, f, indent=2)

    print(f"\n✅ Done! Saved {len(existing_emails)} emails to {OUTPUT_FILE}")

if __name__ == '__main__':
    main()
