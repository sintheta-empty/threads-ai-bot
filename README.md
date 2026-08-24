# Threads AI Bot

An automated Meta Threads AI Bot powered by **Google Gemini API** — posts gaming quotes, anime wisdom, Valorant content, and AI-generated images. Runs 100% free via **GitHub Actions** every 6 hours.

---

## Features

| Feature | Description |
|---|---|
| Gaming Quotes | Philosophy from Elden Ring, Witcher, God of War, Dark Souls & more |
| Anime Wisdom | Deep thoughts from AoT, Vinland Saga, JJK, Berserk & more |
| Valorant Content | Agent meta tips, patch humor, lore snippets, VCT hype |
| AI Image Posts | Auto-generated concept art via Pollinations.ai with Gemini captions |
| Quote Posts | Periodically quotes & reacts to your own previous posts |
| Auto Replies | Reads comments on your posts and replies with Gemini-crafted responses |
| Spam Guard | Gemini detects and skips spam/bot comments automatically |
| State Persistence | Tracks processed comments in JSON, committed back to repo after each run |

---

## Project Structure

```
threads-ai-bot/
├── app/
│   ├── __init__.py          # Package init
│   ├── brain.py             # Gemini AI content generator
│   ├── threads_client.py    # Meta Threads API client
│   └── state.py             # JSON state management
├── main.py                  # Orchestrator
├── requirements.txt
├── .env.example             # Template for local secrets
├── processed_ids.json       # Auto-generated state file (gitignored locally)
└── .github/
    └── workflows/
        └── threads_bot.yml  # GitHub Actions CI/CD
```

---

## Setup Guide

### Step 1 — Fork / Clone This Repo

```bash
git clone https://github.com/YOUR_USERNAME/threads-ai-bot.git
cd threads-ai-bot
```

### Step 2 — Get Your API Keys

#### Google Gemini API Key
1. Go to [Google AI Studio](https://aistudio.google.com/app/apikey)
2. Click **Create API Key**
3. Copy the key

#### Meta Threads Access Token
1. Go to [Meta Developer Portal](https://developers.facebook.com/)
2. Create an app → Add **Threads API** product
3. Under **Threads API → Generate Token**, generate a **Long-lived User Access Token**
4. Copy the long-lived token (valid for 60 days — refresh before expiry)

#### Your Threads User ID (Optional)
```bash
curl "https://graph.threads.net/v1.0/me?fields=id,username&access_token=YOUR_TOKEN"
```
Copy the numeric `id` from the response.

---

### Step 3 — Local Development Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Copy and fill in your secrets
cp .env.example .env
# Edit .env with your actual keys
nano .env

# Run the bot locally
python main.py
```

Your `.env` file should look like:
```env
GEMINI_API_KEY=AIza...
THREADS_ACCESS_TOKEN=THAAgh2...
THREADS_USER_ID=1234567890
STATE_FILE=processed_ids.json
```

> **Never commit your `.env` file!** Add it to `.gitignore`.

---

### Step 4 — GitHub Actions Setup (Free Automation)

1. Push the project to your GitHub repository
2. Go to **Settings → Secrets and Variables → Actions**
3. Click **New repository secret** and add:

| Secret Name | Value |
|---|---|
| `GEMINI_API_KEY` | Your Gemini API key |
| `THREADS_ACCESS_TOKEN` | Your Threads long-lived access token |
| `THREADS_USER_ID` | Your numeric Threads user ID (optional) |

4. Go to **Actions** tab → enable workflows if prompted
5. The bot will now run **automatically every 6 hours**

#### Manual Trigger
Go to **Actions → Threads AI Bot → Run workflow** and click **Run workflow**.

---

### Step 5 — Customize the Schedule

Edit `.github/workflows/threads_bot.yml` — change the cron expression:

```yaml
schedule:
  # Every 6 hours (default)
  - cron: "0 0,6,12,18 * * *"

  # Every 4 hours
  # - cron: "0 */4 * * *"

  # Every 12 hours
  # - cron: "0 0,12 * * *"
```

---

## Configuration Reference

### Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GEMINI_API_KEY` | Yes | Google Gemini API key |
| `THREADS_ACCESS_TOKEN` | Yes | Meta Threads long-lived access token |
| `THREADS_USER_ID` | No | Numeric Threads user ID (auto-fetched if blank) |
| `STATE_FILE` | No | Path to state JSON file (default: `processed_ids.json`) |

### Post Mode Weights

By default, the bot picks randomly from all 4 modes. To customize weights, edit the `modes` list in `main.py`:

```python
# To make gaming 2x more likely:
mode = random.choices(
    ["gaming", "anime", "valorant", "image"],
    weights=[2, 1, 1, 1]
)[0]
```

---

## How Image Posts Work

The bot uses **Pollinations.ai** — a free, no-auth-required AI image generation service.

1. Gemini generates a detailed image prompt and a caption
2. The image URL is constructed as:
   `https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=1024`
3. This public URL is passed directly to the Threads API as the `image_url`
4. No file hosting or S3 buckets needed!

---

## Refreshing Your Threads Token

Threads access tokens expire after **60 days**. To refresh:

```bash
curl -X POST "https://graph.threads.net/refresh_access_token" \
  -d "grant_type=th_refresh_token" \
  -d "access_token=YOUR_CURRENT_TOKEN"
```

Update the `THREADS_ACCESS_TOKEN` secret in GitHub after refreshing.

---

## Troubleshooting

| Issue | Fix |
|---|---|
| `Missing required environment variables` | Check your `.env` file or GitHub Secrets |
| `Container creation failed: 400` | Token may be expired or missing Threads permissions |
| `Gemini API failed after multiple retries` | Check your Gemini API key and quota |
| `No threads found to process replies for` | Your account has no recent posts yet — run the bot first |
| Bot posts duplicate content | The `processed_ids.json` state file tracks this; ensure it is committed to your repo |

---

## License

MIT — feel free to fork, customize, and make it your own.

---

*Built with Google Gemini API + Meta Threads API + GitHub Actions*
