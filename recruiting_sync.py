"""
recruiting_sync.py
==================
Reads your Gmail for recruiting emails, summarizes them with FREE Google Gemini AI,
and saves a data.json file that your dashboard reads.

COMPLETELY FREE:
- Gmail API: Free
- GitHub Pages: Free
- Google Gemini API: Free (1,500 requests/day, no credit card needed)
"""

import os
import json
import base64
import re
import urllib.request
import urllib.parse
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
            raise Exception("❌ GMAIL_TOKEN expired. Re-run locally to refresh.")
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

# ── GEMINI AI (FREE) ──────────────────────────────────────────────────────────

def classify_with_gemini(email, api_key):
    """Use free Google Gemini API to classify and summarize email."""

    prompt = f"""You are helping a high school football kicker (Class of 2028) named Isaac Lambert organize his college recruiting emails.

Analyze this email and return a JSON object with these exact fields:
- school: (string) The college/university name, or "Unknown" if unclear
- coach: (string) The coach or staff member's name, or "Recruiting Staff" if unclear
- summary: (string) A 2-3 sentence summary of what this email is about and what action if any is needed
- tags: (array of strings) Include any relevant tags from this list ONLY: ["d1", "d2", "d3", "offer", "visit", "camp", "scholarship"]
- isRecruiting: (boolean) true if this is a genuine college football recruiting email, false if spam or unrelated

EMAIL SUBJECT: {email['subject']}
FROM: {email['sender']}
DATE: {email['date']}

EMAIL BODY:
{email['body'] or email['snippet']}

Return ONLY a valid JSON object, no other text, no markdown."""

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 400}
    }).encode('utf-8')

    req = urllib.request.Request(url, data=payload, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=15) as resp:
        result = json.loads(resp.read())

    text = result['candidates'][0]['content']['parts'][0]['text'].strip()
    text = re.sub(r'```json?\n?', '', text).rstrip('`').strip()
    return json.loads(text)


# ── FALLBACK: Rule-based (if no Gemini key) ───────────────────────────────────

OFFER_KW = ['scholarship offer','full scholarship','we are offering','pleased to offer','extend an offer']
VISIT_KW = ['official visit','unofficial visit','campus visit','visit us','invite you to visit']
CAMP_KW  = ['camp','combine','showcase','clinic','prospect day']
SCHOL_KW = ['scholarship','full ride','athletic scholarship']
D1_KW    = ['sec ','big ten','big 12','acc ','pac-12','division i','fbs','fcs']
D2_KW    = ['division ii','division 2','super region']
D3_KW    = ['division iii','division 3','nescac']

def classify_rules(email):
    text = ((email['subject'] or '') + ' ' + (email['body'] or '') + ' ' + (email['snippet'] or '')).lower()
    tags = []
    if any(k in text for k in OFFER_KW): tags.append('offer')
    if any(k in text for k in SCHOL_KW): tags.append('scholarship')
    if any(k in text for k in VISIT_KW): tags.append('visit')
    if any(k in text for k in CAMP_KW):  tags.append('camp')
    if any(k in text for k in D1_KW):   tags.append('d1')
    elif any(k in text for k in D2_KW): tags.append('d2')
    elif any(k in text for k in D3_KW): tags.append('d3')

    school_match = re.search(r'(university of [\w ]+|[\w ]+ university|[\w ]+ college|[\w ]+ state)', text, re.I)
    school = school_match.group(0).strip().title() if school_match else email['senderName']

    domain = re.search(r'@([\w]+)\.edu', email['sender'])
    if not school_match and domain:
        school = domain.group(1).replace('-',' ').title()

    coach_match = re.search(r'coach\s+([A-Z][a-z]+ [A-Z][a-z]+)', email['body'] or '', re.I)
    coach = 'Coach ' + coach_match.group(1) if coach_match else email['senderName']

    return {
        'school': school or 'Unknown School',
        'coach': coach or 'Recruiting Staff',
        'summary': (email['snippet'] or '')[:300],
        'tags': tags,
        'isRecruiting': True
    }


def classify_email(email, gemini_key):
    if gemini_key:
        try:
            return classify_with_gemini(email, gemini_key)
        except Exception as e:
            print(f"    ⚠️ Gemini failed, using rules: {e}")
    return classify_rules(email)


# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    print("🏈 Isaac Lambert Recruiting Sync")
    print("=" * 50)

    gemini_key = os.environ.get('GEMINI_API_KEY')
    if gemini_key:
        print("✨ Using FREE Google Gemini AI for summaries")
    else:
        print("📋 Using rule-based detection (add GEMINI_API_KEY for AI summaries)")

    # Load existing
    existing_ids = set()
    existing_emails = []
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE) as f:
            old_data = json.load(f)
            existing_emails = old_data.get('emails', [])
            existing_ids = {e['id'] for e in existing_emails}
        print(f"📂 {len(existing_emails)} existing emails loaded")

    # Connect Gmail
    print("🔑 Connecting to Gmail...")
    service = get_gmail_service()

    print("🔍 Searching for recruiting emails...")
    results = service.users().messages().list(
        userId='me', q=GMAIL_SEARCH_QUERY, maxResults=MAX_EMAILS
    ).execute()

    messages = results.get('messages', [])
    new_messages = [m for m in messages if m['id'] not in existing_ids]
    print(f"📧 {len(messages)} found, {len(new_messages)} new")

    if new_messages:
        new_emails = []
        for i, msg in enumerate(new_messages):
            print(f"  [{i+1}/{len(new_messages)}] Processing...")
            try:
                email = parse_email(service, msg['id'])
                result = classify_email(email, gemini_key)

                if not result.get('isRecruiting', True):
                    print(f"    ⏭ Skipping spam: {email['subject'][:40]}")
                    continue

                new_emails.append({
                    'id': email['id'],
                    'school': result.get('school', 'Unknown'),
                    'coach': result.get('coach', 'Recruiting Staff'),
                    'subject': email['subject'],
                    'summary': result.get('summary', email['snippet']),
                    'body': email['body'],
                    'date': email['date'],
                    'tags': result.get('tags', []),
                    'unread': True,
                })
                print(f"    ✅ {result.get('school','?')} — {email['subject'][:45]}")
            except Exception as e:
                print(f"    ❌ Error: {e}")

        existing_emails = new_emails + existing_emails
    else:
        print("✅ No new emails to process")

    with open(OUTPUT_FILE, 'w') as f:
        json.dump({'lastSynced': datetime.now(timezone.utc).isoformat(), 'emails': existing_emails}, f, indent=2)

    print(f"\n✅ Saved {len(existing_emails)} emails to {OUTPUT_FILE}")

if __name__ == '__main__':
    main()
