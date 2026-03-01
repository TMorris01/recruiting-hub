"""
recruiting_sync.py
==================
Reads your Gmail for recruiting emails, summarizes them with Claude AI,
and saves a data.json file that your dashboard website reads.

SETUP INSTRUCTIONS (see README.md for full guide):
1. pip install google-auth google-auth-oauthlib google-api-python-client anthropic
2. Get Gmail API credentials (credentials.json) from Google Cloud Console
3. Set your ANTHROPIC_API_KEY as an environment variable
4. Run: python recruiting_sync.py
5. Push data.json to your GitHub repo
"""

import os
import json
import base64
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

# Gmail API
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Claude AI
import anthropic

# ── CONFIG ──────────────────────────────────────────────────────────────────

# Search query to find recruiting emails in your Gmail
GMAIL_SEARCH_QUERY = (
    'subject:(recruiting OR kicker OR football OR "scholarship offer" OR "official visit" '
    'OR "camp invitation" OR "interested in" OR "recruiting questionnaire") '
    '-from:me'
)

MAX_EMAILS = 100           # Max emails to fetch per run
OUTPUT_FILE = "data.json"  # Output file (commit this to GitHub)
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

# ── GMAIL AUTH ───────────────────────────────────────────────────────────────

def get_gmail_service():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return build('gmail', 'v1', credentials=creds)

# ── EMAIL PARSING ─────────────────────────────────────────────────────────────

def get_email_body(payload):
    """Extract plain text body from email payload."""
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
    """Fetch and parse a single email."""
    msg = service.users().messages().get(
        userId='me', id=msg_id, format='full'
    ).execute()

    headers = {h['name']: h['value'] for h in msg['payload'].get('headers', [])}

    subject = headers.get('Subject', '(No Subject)')
    sender = headers.get('From', '')
    date_str = headers.get('Date', '')

    # Parse date
    try:
        date = parsedate_to_datetime(date_str)
        date_iso = date.strftime('%Y-%m-%d')
    except:
        date_iso = datetime.now().strftime('%Y-%m-%d')

    # Extract sender name and school guess
    sender_name = re.match(r'^([^<]+)', sender)
    sender_name = sender_name.group(1).strip() if sender_name else sender

    # Get body
    body = get_email_body(msg['payload'])
    # Truncate to avoid huge AI bills
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
    """Use Claude to classify and summarize a recruiting email."""

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
        # Clean up response
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

# ── MAIN SYNC ─────────────────────────────────────────────────────────────────

def main():
    print("🏈 Recruiting Email Sync Starting...")
    print("=" * 50)

    # Load existing data to avoid re-processing
    existing_ids = set()
    existing_emails = []
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE) as f:
            old_data = json.load(f)
            existing_emails = old_data.get('emails', [])
            existing_ids = {e['id'] for e in existing_emails}
        print(f"📂 Found {len(existing_emails)} existing emails in {OUTPUT_FILE}")

    # Connect to Gmail
    print("🔑 Connecting to Gmail...")
    service = get_gmail_service()

    # Search for recruiting emails
    print(f"🔍 Searching Gmail...")
    results = service.users().messages().list(
        userId='me',
        q=GMAIL_SEARCH_QUERY,
        maxResults=MAX_EMAILS
    ).execute()

    messages = results.get('messages', [])
    new_messages = [m for m in messages if m['id'] not in existing_ids]
    print(f"📧 Found {len(messages)} total, {len(new_messages)} new emails to process")

    if not new_messages:
        print("✅ Nothing new to process!")
    else:
        # Set up Claude
        api_key = os.environ.get('ANTHROPIC_API_KEY')
        if not api_key:
            raise ValueError("❌ Set your ANTHROPIC_API_KEY environment variable!")
        claude = anthropic.Anthropic(api_key=api_key)

        new_emails = []
        for i, msg in enumerate(new_messages):
            print(f"  [{i+1}/{len(new_messages)}] Processing email {msg['id']}...")
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

    # Save output
    output = {
        'lastSynced': datetime.now(timezone.utc).isoformat(),
        'emails': existing_emails
    }

    with open(OUTPUT_FILE, 'w') as f:
        json.dump(output, f, indent=2)

    print(f"\n✅ Done! Saved {len(existing_emails)} emails to {OUTPUT_FILE}")
    print("📤 Now run: git add data.json && git commit -m 'sync emails' && git push")

if __name__ == '__main__':
    main()
