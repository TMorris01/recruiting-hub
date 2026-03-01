"""
recruiting_sync.py — Isaac Lambert Recruiting Hub
==================================================
Reads Gmail, detects school names, division levels, and email types.
Uses free Google Gemini AI if GEMINI_API_KEY is set, otherwise uses
smart rule-based detection. 100% free either way.
"""

import os
import json
import base64
import re
import urllib.request
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

# ── KNOWN SCHOOLS DATABASE ────────────────────────────────────────────────────
# Maps common name variations / domains → (Official Name, Division)

SCHOOL_DB = {
    # ── BIG TEN D1 ──
    "michigan": ("University of Michigan", "d1"),
    "umich": ("University of Michigan", "d1"),
    "wolverines": ("University of Michigan", "d1"),
    "michigan state": ("Michigan State University", "d1"),
    "msu": ("Michigan State University", "d1"),
    "spartans": ("Michigan State University", "d1"),
    "ohio state": ("Ohio State University", "d1"),
    "osu": ("Ohio State University", "d1"),
    "buckeyes": ("Ohio State University", "d1"),
    "penn state": ("Penn State University", "d1"),
    "nittany lions": ("Penn State University", "d1"),
    "notre dame": ("Notre Dame University", "d1"),
    "fighting irish": ("Notre Dame University", "d1"),
    "wisconsin": ("University of Wisconsin", "d1"),
    "badgers": ("University of Wisconsin", "d1"),
    "iowa": ("University of Iowa", "d1"),
    "hawkeyes": ("University of Iowa", "d1"),
    "minnesota": ("University of Minnesota", "d1"),
    "gophers": ("University of Minnesota", "d1"),
    "nebraska": ("University of Nebraska", "d1"),
    "cornhuskers": ("University of Nebraska", "d1"),
    "illinois": ("University of Illinois", "d1"),
    "fighting illini": ("University of Illinois", "d1"),
    "indiana": ("Indiana University", "d1"),
    "hoosiers": ("Indiana University", "d1"),
    "purdue": ("Purdue University", "d1"),
    "boilermakers": ("Purdue University", "d1"),
    "rutgers": ("Rutgers University", "d1"),
    "northwestern": ("Northwestern University", "d1"),
    "maryland": ("University of Maryland", "d1"),
    "ucla": ("UCLA", "d1"),
    "usc": ("USC", "d1"),
    "oregon": ("University of Oregon", "d1"),
    "ducks": ("University of Oregon", "d1"),
    "washington": ("University of Washington", "d1"),
    "huskies": ("University of Washington", "d1"),
    # ── SEC D1 ──
    "alabama": ("University of Alabama", "d1"),
    "crimson tide": ("University of Alabama", "d1"),
    "georgia": ("University of Georgia", "d1"),
    "bulldogs": ("University of Georgia", "d1"),
    "lsu": ("Louisiana State University", "d1"),
    "tigers": ("LSU", "d1"),
    "auburn": ("Auburn University", "d1"),
    "florida": ("University of Florida", "d1"),
    "gators": ("University of Florida", "d1"),
    "tennessee": ("University of Tennessee", "d1"),
    "vols": ("University of Tennessee", "d1"),
    "arkansas": ("University of Arkansas", "d1"),
    "razorbacks": ("University of Arkansas", "d1"),
    "ole miss": ("University of Mississippi", "d1"),
    "rebels": ("University of Mississippi", "d1"),
    "mississippi state": ("Mississippi State University", "d1"),
    "texas a&m": ("Texas A&M University", "d1"),
    "aggies": ("Texas A&M University", "d1"),
    "vanderbilt": ("Vanderbilt University", "d1"),
    "commodores": ("Vanderbilt University", "d1"),
    "south carolina": ("University of South Carolina", "d1"),
    "gamecocks": ("University of South Carolina", "d1"),
    "kentucky": ("University of Kentucky", "d1"),
    "wildcats": ("University of Kentucky", "d1"),
    "missouri": ("University of Missouri", "d1"),
    "texas": ("University of Texas", "d1"),
    "longhorns": ("University of Texas", "d1"),
    "oklahoma": ("University of Oklahoma", "d1"),
    "sooners": ("University of Oklahoma", "d1"),
    # ── ACC D1 ──
    "clemson": ("Clemson University", "d1"),
    "florida state": ("Florida State University", "d1"),
    "fsu": ("Florida State University", "d1"),
    "miami": ("University of Miami", "d1"),
    "hurricanes": ("University of Miami", "d1"),
    "nc state": ("NC State University", "d1"),
    "north carolina": ("University of North Carolina", "d1"),
    "tar heels": ("University of North Carolina", "d1"),
    "virginia tech": ("Virginia Tech", "d1"),
    "hokies": ("Virginia Tech", "d1"),
    "virginia": ("University of Virginia", "d1"),
    "duke": ("Duke University", "d1"),
    "blue devils": ("Duke University", "d1"),
    "pitt": ("University of Pittsburgh", "d1"),
    "pittsburgh": ("University of Pittsburgh", "d1"),
    "wake forest": ("Wake Forest University", "d1"),
    "boston college": ("Boston College", "d1"),
    "louisville": ("University of Louisville", "d1"),
    "cardinals": ("University of Louisville", "d1"),
    "syracuse": ("Syracuse University", "d1"),
    "georgia tech": ("Georgia Tech", "d1"),
    # ── BIG 12 D1 ──
    "baylor": ("Baylor University", "d1"),
    "bears": ("Baylor University", "d1"),
    "tcu": ("TCU", "d1"),
    "horned frogs": ("TCU", "d1"),
    "kansas state": ("Kansas State University", "d1"),
    "kansas": ("University of Kansas", "d1"),
    "iowa state": ("Iowa State University", "d1"),
    "cyclones": ("Iowa State University", "d1"),
    "west virginia": ("West Virginia University", "d1"),
    "mountaineers": ("West Virginia University", "d1"),
    "cincinnati": ("University of Cincinnati", "d1"),
    "bearcats": ("University of Cincinnati", "d1"),
    "ucf": ("UCF", "d1"),
    "houston": ("University of Houston", "d1"),
    "byu": ("BYU", "d1"),
    "utah": ("University of Utah", "d1"),
    "utes": ("University of Utah", "d1"),
    "colorado": ("University of Colorado", "d1"),
    "buffaloes": ("University of Colorado", "d1"),
    "arizona state": ("Arizona State University", "d1"),
    "sun devils": ("Arizona State University", "d1"),
    "arizona": ("University of Arizona", "d1"),
    # ── MAC / Mid-American D1 ──
    "northern michigan": ("Northern Michigan University", "d2"),
    "central michigan": ("Central Michigan University", "d1"),
    "eastern michigan": ("Eastern Michigan University", "d1"),
    "western michigan": ("Western Michigan University", "d1"),
    "michigan tech": ("Michigan Tech", "d2"),
    "toledo": ("University of Toledo", "d1"),
    "ball state": ("Ball State University", "d1"),
    "bowling green": ("Bowling Green State University", "d1"),
    "ohio university": ("Ohio University", "d1"),
    "kent state": ("Kent State University", "d1"),
    "akron": ("University of Akron", "d1"),
    "buffalo": ("University at Buffalo", "d1"),
    "miami ohio": ("Miami University Ohio", "d1"),
    "northern illinois": ("Northern Illinois University", "d1"),
    # ── Mountain West / Sun Belt / CUSA D1 ──
    "boise state": ("Boise State University", "d1"),
    "broncos": ("Boise State University", "d1"),
    "fresno state": ("Fresno State University", "d1"),
    "san diego state": ("San Diego State University", "d1"),
    "nevada": ("University of Nevada", "d1"),
    "air force": ("Air Force Academy", "d1"),
    "army": ("Army West Point", "d1"),
    "navy": ("Navy", "d1"),
    "appalachian state": ("Appalachian State University", "d1"),
    "app state": ("Appalachian State University", "d1"),
    "louisiana": ("University of Louisiana", "d1"),
    "ragin cajuns": ("University of Louisiana", "d1"),
    "marshall": ("Marshall University", "d1"),
    "liberty": ("Liberty University", "d1"),
    # ── FCS D1 ──
    "ndsu": ("North Dakota State University", "d1"),
    "north dakota state": ("North Dakota State University", "d1"),
    "south dakota state": ("South Dakota State University", "d1"),
    "sdsu": ("South Dakota State University", "d1"),
    "montana": ("University of Montana", "d1"),
    "eastern washington": ("Eastern Washington University", "d1"),
    "illinois state": ("Illinois State University", "d1"),
    "southern illinois": ("Southern Illinois University", "d1"),
    "northern iowa": ("University of Northern Iowa", "d1"),
    "missouri state": ("Missouri State University", "d1"),
    "south dakota": ("University of South Dakota", "d1"),
    "north dakota": ("University of North Dakota", "d1"),
    "saginaw valley": ("Saginaw Valley State University", "d2"),
    "grand valley": ("Grand Valley State University", "d2"),
    "ferris state": ("Ferris State University", "d2"),
    "hillsdale": ("Hillsdale College", "d2"),
    "lake superior": ("Lake Superior State University", "d3"),
    "finlandia": ("Finlandia University", "d3"),
    "northwood": ("Northwood University", "d2"),
}

# Conference name → division mapping
CONFERENCE_DIVISION = {
    "sec": "d1", "big ten": "d1", "big 12": "d1", "acc": "d1",
    "pac-12": "d1", "pac 12": "d1", "american athletic": "d1",
    "mountain west": "d1", "sun belt": "d1", "conference usa": "d1",
    "mid-american": "d1", "mac ": "d1", "fbs": "d1", "fcs": "d1",
    "division i": "d1", "division 1": "d1",
    "division ii": "d2", "division 2": "d2", "gsac": "d2",
    "nsic": "d2", "gliac": "d2", "super region": "d2", "great lakes": "d2",
    "division iii": "d3", "division 3": "d3", "nescac": "d3",
    "odac": "d3", "centennial": "d3", "miaa": "d3",
}

# ── GMAIL AUTH ────────────────────────────────────────────────────────────────

def get_gmail_service():
    creds = None
    gmail_token = os.environ.get('GMAIL_TOKEN')
    if gmail_token:
        print("🔑 Using GMAIL_TOKEN from GitHub secret...")
        creds = Credentials.from_authorized_user_info(json.loads(gmail_token), SCOPES)
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
        print("🌐 Opening browser for Gmail login...")
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
        date_iso = parsedate_to_datetime(date_str).strftime('%Y-%m-%d')
    except:
        date_iso = datetime.now().strftime('%Y-%m-%d')
    sender_name = re.match(r'^([^<]+)', sender)
    sender_name = sender_name.group(1).strip().strip('"') if sender_name else sender
    body = get_email_body(msg['payload'])
    return {
        'id': msg_id,
        'subject': subject,
        'sender': sender,
        'senderName': sender_name,
        'date': date_iso,
        'body': body[:4000] if len(body) > 4000 else body,
        'snippet': msg.get('snippet', ''),
    }

# ── SMART SCHOOL DETECTION ────────────────────────────────────────────────────

def detect_school_and_division(email):
    """Try to identify school name and division from email content."""
    text = ((email['subject'] or '') + ' ' + (email['body'] or '') + ' ' + (email['snippet'] or '')).lower()
    sender = email['sender'].lower()

    # 1. Check against known school database
    for key, (name, div) in SCHOOL_DB.items():
        if key in text or key in sender:
            return name, div

    # 2. Check conference mentions for division
    division = None
    for conf, div in CONFERENCE_DIVISION.items():
        if conf in text:
            division = div
            break

    # 3. Try to extract school name from email domain
    domain_match = re.search(r'@([\w-]+)\.edu', sender)
    if domain_match:
        domain = domain_match.group(1).replace('-', ' ')
        # Check if domain matches any known school key
        for key, (name, div) in SCHOOL_DB.items():
            if domain in key or key in domain:
                return name, div
        # Format domain nicely as school name
        school_name = domain.title() + (' University' if 'university' not in domain else '')
        return school_name, division or 'unknown'

    # 4. Try regex patterns in body text
    patterns = [
        r'(university of [\w\s]+?)(?:\s*(?:football|athletics|recruiting|staff|coaching))',
        r'([\w\s]+ university)(?:\s*(?:football|athletics|recruiting|kicking))',
        r'([\w\s]+ college)(?:\s*(?:football|athletics|recruiting))',
        r'([\w\s]+ state university)',
        r'go (\w+)!',  # team cheer like "Go Green!" "Go Blue!"
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            name = match.group(1).strip().title()
            if 5 < len(name) < 60:
                return name, division or 'unknown'

    # 5. Fall back to sender name
    return email['senderName'] or 'Unknown School', division or 'unknown'


# ── TAG DETECTION ─────────────────────────────────────────────────────────────

OFFER_KW    = ['scholarship offer','full scholarship','we are offering','pleased to offer',
               'extend an offer','official offer','offer you a scholarship','offered a scholarship',
               'offer of admission','we would like to offer','proud to offer']
VISIT_KW    = ['official visit','unofficial visit','campus visit','visit our campus',
               'invite you to visit','come visit','visit weekend','on-campus visit','paid visit']
CAMP_KW     = ['kicking camp','football camp','combine','showcase','prospect camp',
               'camp invitation','skills camp','clinic','prospect day','junior day']
SCHOL_KW    = ['full scholarship','scholarship offer','athletic scholarship','full ride',
               'tuition covered','financial aid package','scholarship to play']
INTEREST_KW = ['interested in','following your film','watched your film','your tape',
               'great interest','keeping an eye','monitor your progress','recruiting you']

def detect_tags(email, division):
    text = ((email['subject'] or '') + ' ' + (email['body'] or '') + ' ' + (email['snippet'] or '')).lower()
    tags = []
    if any(k in text for k in OFFER_KW):    tags.append('offer')
    if any(k in text for k in SCHOL_KW):    tags.append('scholarship')
    if any(k in text for k in VISIT_KW):    tags.append('visit')
    if any(k in text for k in CAMP_KW):     tags.append('camp')
    if division in ('d1', 'd2', 'd3'):
        tags.append(division)
    return tags

def extract_coach(sender, body):
    for pattern in [
        r'coach\s+([A-Z][a-z]+\s+[A-Z][a-z]+)',
        r'(?:sincerely|regards|best wishes|go \w+)[,\s\n]+([A-Z][a-z]+ [A-Z][a-z]+)',
        r'([A-Z][a-z]+ [A-Z][a-z]+)\s*\n.*?(?:coach|coordinator|director)',
    ]:
        m = re.search(pattern, body or '', re.IGNORECASE | re.MULTILINE)
        if m:
            return m.group(1).strip()
    sender_name = re.match(r'^([^<"]+)', sender)
    if sender_name:
        name = sender_name.group(1).strip().strip('"')
        if name and '@' not in name and 2 < len(name) < 40:
            return name
    return 'Recruiting Staff'

def is_recruiting_email(email):
    text = ((email['subject'] or '') + ' ' + (email['snippet'] or '')).lower()
    spam = ['unsubscribe','newsletter','promo','% off','limited time','order confirmation',
            'your receipt','invoice','verify your','reset your password']
    if any(k in text for k in spam): return False
    recruiting = ['recruit','kicker','football','scholarship','visit','camp','offer',
                  'roster','commit','signing','athletic','program','coaching staff']
    return any(k in text for k in recruiting)

# ── GEMINI AI (OPTIONAL FREE UPGRADE) ────────────────────────────────────────

def classify_with_gemini(email, api_key):
    prompt = f"""You are helping high school football kicker Isaac Lambert (Class of 2028, Escanaba MI) organize his college recruiting emails.

Analyze this email carefully and return a JSON object:
- school: Full official college/university name (e.g. "University of Michigan" not "Michigan")
- coach: Coach or staff member name, or "Recruiting Staff"
- summary: 2-3 sentence summary. What did they want? Any action needed?
- tags: Array from ONLY these options: ["d1", "d2", "d3", "offer", "visit", "camp", "scholarship"]
  - Use d1/d2/d3 based on the school's actual division level even if not stated explicitly
  - "offer" = scholarship offer extended
  - "scholarship" = scholarship mentioned even if not a formal offer yet
  - "visit" = campus visit invited or scheduled
  - "camp" = camp, clinic, combine, or showcase invitation
- isRecruiting: true if genuine football recruiting email, false if spam

FROM: {email['sender']}
SUBJECT: {email['subject']}
DATE: {email['date']}
BODY:
{email['body'] or email['snippet']}

Return ONLY valid JSON. No markdown, no extra text."""

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 500}
    }).encode('utf-8')
    req = urllib.request.Request(url, data=payload, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=15) as resp:
        result = json.loads(resp.read())
    text = result['candidates'][0]['content']['parts'][0]['text'].strip()
    text = re.sub(r'```json?\n?', '', text).rstrip('`').strip()
    return json.loads(text)

# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    print("🏈 Isaac Lambert Recruiting Sync")
    print("=" * 50)

    gemini_key = os.environ.get('GEMINI_API_KEY')
    if gemini_key:
        print("✨ Gemini AI active — smart summaries enabled")
    else:
        print("📋 Rule-based mode (add GEMINI_API_KEY secret for AI summaries)")

    existing_ids = set()
    existing_emails = []
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE) as f:
            old_data = json.load(f)
            existing_emails = old_data.get('emails', [])
            existing_ids = {e['id'] for e in existing_emails}
        print(f"📂 {len(existing_emails)} existing emails loaded")

    print("🔑 Connecting to Gmail...")
    service = get_gmail_service()

    print("🔍 Searching Gmail...")
    results = service.users().messages().list(
        userId='me', q=GMAIL_SEARCH_QUERY, maxResults=MAX_EMAILS
    ).execute()

    messages = results.get('messages', [])
    new_messages = [m for m in messages if m['id'] not in existing_ids]
    print(f"📧 {len(messages)} found, {len(new_messages)} new to process")

    if new_messages:
        new_emails = []
        for i, msg in enumerate(new_messages):
            print(f"  [{i+1}/{len(new_messages)}] Processing...")
            try:
                email = parse_email(service, msg['id'])

                if not is_recruiting_email(email):
                    print(f"    ⏭ Skipping (not recruiting): {email['subject'][:50]}")
                    continue

                if gemini_key:
                    try:
                        result = classify_with_gemini(email, gemini_key)
                        school = result.get('school', 'Unknown')
                        coach = result.get('coach', 'Recruiting Staff')
                        summary = result.get('summary', email['snippet'])
                        tags = result.get('tags', [])
                        if not result.get('isRecruiting', True):
                            print(f"    ⏭ AI skipping: {email['subject'][:50]}")
                            continue
                    except Exception as e:
                        print(f"    ⚠️ Gemini failed, using rules: {e}")
                        school, division = detect_school_and_division(email)
                        coach = extract_coach(email['sender'], email['body'])
                        tags = detect_tags(email, division)
                        summary = email['snippet'][:300]
                else:
                    school, division = detect_school_and_division(email)
                    coach = extract_coach(email['sender'], email['body'])
                    tags = detect_tags(email, division)
                    summary = email['snippet'][:300]

                new_emails.append({
                    'id': email['id'],
                    'school': school,
                    'coach': coach,
                    'subject': email['subject'],
                    'summary': summary,
                    'body': email['body'],
                    'date': email['date'],
                    'tags': list(dict.fromkeys(tags)),  # deduplicate
                    'unread': True,
                })
                print(f"    ✅ {school} — {email['subject'][:45]}")
            except Exception as e:
                print(f"    ❌ Error: {e}")

        existing_emails = new_emails + existing_emails
    else:
        print("✅ No new emails!")

    with open(OUTPUT_FILE, 'w') as f:
        json.dump({'lastSynced': datetime.now(timezone.utc).isoformat(), 'emails': existing_emails}, f, indent=2)

    print(f"\n✅ Done! {len(existing_emails)} total emails saved.")

if __name__ == '__main__':
    main()
