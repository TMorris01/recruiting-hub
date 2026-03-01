# 🏈 Recruiting Hub — Setup Guide
### Class of 2028 Football Kicker Email Dashboard

This is a personal recruiting dashboard that:
- Reads your Gmail for recruiting emails
- Uses Claude AI to summarize and tag each email
- Displays everything on a beautiful website
- Works as an iPhone app (add to home screen)
- Hosted FREE on GitHub Pages

---

## What You'll Need
- A GitHub account (free)
- A Gmail account (your recruiting email)
- An Anthropic API key (free trial available at console.anthropic.com)
- Python 3.8+ installed on your computer

---

## Step 1 — Set Up GitHub

1. Go to [github.com](https://github.com) and create an account if you don't have one
2. Click the **+** button → **New Repository**
3. Name it: `recruiting-hub`
4. Set it to **Public**
5. Click **Create Repository**
6. Upload all these files to the repo (drag and drop in the browser)

---

## Step 2 — Enable GitHub Pages

1. In your repo, click **Settings**
2. Scroll to **Pages** in the left sidebar
3. Under "Branch", select **main** and **/ (root)**
4. Click **Save**
5. After ~1 minute, your site will be live at:
   `https://YOUR_GITHUB_USERNAME.github.io/recruiting-hub`

---

## Step 3 — Gmail API Setup

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Create a new project (call it "Recruiting Hub")
3. Go to **APIs & Services** → **Enable APIs**
4. Search for and enable **Gmail API**
5. Go to **APIs & Services** → **Credentials**
6. Click **Create Credentials** → **OAuth 2.0 Client ID**
7. Choose **Desktop App**, name it anything
8. Download the JSON file and rename it to `credentials.json`
9. Put `credentials.json` in the same folder as `recruiting_sync.py`
10. Go to **OAuth consent screen** → Add your email as a test user

---

## Step 4 — Get Your Anthropic API Key

1. Go to [console.anthropic.com](https://console.anthropic.com)
2. Create a free account
3. Go to **API Keys** and create a new key
4. Copy the key (starts with `sk-ant-...`)

---

## Step 5 — Install Python Dependencies

Open Terminal (Mac) or Command Prompt (Windows) and run:

```bash
pip install google-auth google-auth-oauthlib google-api-python-client anthropic
```

---

## Step 6 — Run the Sync Script

Set your API key (do this every time you open a new terminal):

**Mac/Linux:**
```bash
export ANTHROPIC_API_KEY=sk-ant-YOUR_KEY_HERE
```

**Windows:**
```cmd
set ANTHROPIC_API_KEY=sk-ant-YOUR_KEY_HERE
```

Then run the script:
```bash
python recruiting_sync.py
```

The first time it runs, a browser window will open asking you to log in to Gmail and grant permission. This only happens once.

---

## Step 7 — Push to GitHub

After the script runs, upload the new `data.json` to your GitHub repo:

**Option A — Browser (easier):**
1. Open your repo on github.com
2. Click **Add File** → **Upload Files**
3. Drag `data.json` in
4. Click **Commit Changes**

**Option B — Git (faster for regular use):**
```bash
git add data.json
git commit -m "sync recruiting emails"
git push
```

Your website will update within a minute!

---

## Add to iPhone Home Screen

1. Open Safari on your iPhone
2. Go to your GitHub Pages URL
3. Tap the **Share** button (box with arrow)
4. Tap **Add to Home Screen**
5. Name it "Recruiting Hub"
6. Done! It works like a native app

---

## Staying Up to Date

Run the sync script anytime you want to update:
```bash
export ANTHROPIC_API_KEY=sk-ant-YOUR_KEY_HERE
python recruiting_sync.py
```

Then push `data.json` to GitHub. Your site updates automatically.

**Tip:** You can also set up a GitHub Action to automate this — ask Claude how!

---

## Cost Estimate

- GitHub Pages: **Free**
- Gmail API: **Free**
- Anthropic API: Very cheap — processing 100 emails costs roughly **$0.05**

---

## Troubleshooting

**"credentials.json not found"** → Make sure the file is in the same folder as the script

**"ANTHROPIC_API_KEY not set"** → Run the export/set command again

**Website shows demo data** → You haven't pushed `data.json` yet, or it's in the wrong location

**Gmail not finding emails** → Edit the `GMAIL_SEARCH_QUERY` in `recruiting_sync.py` to match your emails better

---

Good luck with your recruiting! 🏈⚡
