"""
recruiting_sync.py
==================
Reads your Gmail for recruiting emails, summarizes them with Claude AI,
and saves a data.json file that your dashboard website reads.
Works both locally AND automatically via GitHub Actions.
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
import anthropic

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

    # Check if running in GitHub Actions (token stored as secret)
    gmail_token = os.environ.get('GMAIL_TOKEN')
    if gmail_token:
        print("🔑 Using GMAIL_TOKEN from GitHub secret...")
        token_data = json.loads(gmail_token)
        creds = Credentials.from_authorized_user_info(token_data, SCOPES)

    # Otherwise use local token.json file
    elif os.path.exists('token.json'):
        print("🔑 Using local token.json...")
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)

    # Refresh if expired
    if creds and creds.expired and creds.refresh_token:
        print("🔄 Refreshing token...")
        creds.refresh(Request())
        if not os.environ.get('GMAIL_TOKEN'):
            with open('token.json', 'w') as f:
                f.write(creds.to_json())

    # If no creds at all, run local OAuth flow
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

# ── AI CLASSIFICATION ─────────────────────────────────────────────────────────

def classify_email(client, email):
    prompt = f"""You are helping a high school football kicker (Class of 2028) organize their college recruiting emails.

Analyze this email and return a JSON object with these exact fields:
- school: (string) The college/university name, or "Unknown" if unclear
- coach: (string) The coach or staff member's name, or "Recruiting Staff" if unclear
- summary: (string) A 2-3 sentence summary of what this email is about and what action (if any) is needed
- tags: (array of strings) Include any relevant tags from this list ONLY: ["d1", "d2", "d3", "offer", "visit", "camp", "scholarship"]
- isRecruiting: (boolean) true if this is genuinely a college football recruiting email, false if spam/unrelated

EMAIL SUBJECT: {email['subject']}
FROM: {email['sender']}
DATE: {email['date']}

EMAIL BODY:
{email['body'] or email['snippet']}

Return ONLY a valid JSON object, no other text."""

    try:
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}]
        )
        response_text = message.content[0].text.strip()
        if response_text.startswith('```'):
            response_text = re.sub(r'```json?\n?', '', response_text).rstrip('`').strip()
        return json.loads(response_text)
    except Exception as e:
        print(f"  AI error for '{email['subject']}': {e}")
        return {
            'school': 'Unknown',
            'coach': 'Recruiting Staff',
            'summary': email['snippet'],
            'tags': [],
            'isRecruiting': True
        }

# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    print("🏈 Recruiting Email Sync Starting...")
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
        api_key = os.environ.get('ANTHROPIC_API_KEY')
        if not api_key:
            raise ValueError("❌ Set your ANTHROPIC_API_KEY environment variable!")
        claude = anthropic.Anthropic(api_key=api_key)

        new_emails = []
        for i, msg in enumerate(new_messages):
            print(f"  [{i+1}/{len(new_messages)}] Processing...")
            try:
                email = parse_email(service, msg['id'])
                classification = classify_email(claude, email)

                if not classification.get('isRecruiting', True):
                    print(f"    ⏭ Skipping (not recruiting): {email['subject']}")
                    continue

                merged = {
                    'id': email['id'],
                    'school': classification.get('school', 'Unknown'),
                    'coach': classification.get('coach', 'Recruiting Staff'),
                    'subject': email['subject'],
                    'summary': classification.get('summary', email['snippet']),
                    'body': email['body'],
                    'date': email['date'],
                    'tags': classification.get('tags', []),
                    'unread': True,
                }
                new_emails.append(merged)
                print(f"    ✅ {classification.get('school', '?')} — {email['subject'][:50]}")
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
