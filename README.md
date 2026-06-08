# 🛒 Amazon Seller Tracker — Discord Notifier

Monitors Amazon UK seller storefronts every 60 minutes. When a new ASIN appears, you get a Discord DM with the product title, price, image, and link.

---

## 📁 Files

| File | Purpose |
|------|---------|
| `tracker.py` | Main script — runs the checks and sends Discord DMs |
| `sellers.json` | Your list of sellers to track (edit this freely) |
| `seen_asins.json` | Auto-generated — stores known ASINs so duplicates aren't re-alerted |
| `requirements.txt` | Python dependencies |
| `railway.toml` | Deployment config for Railway.app |
| `.env.example` | Template for your secret credentials |

---

## 🚀 Setup Guide

### Step 1 — Create a Discord Bot

1. Go to [https://discord.com/developers/applications](https://discord.com/developers/applications)
2. Click **New Application** → name it (e.g. "Amazon Tracker")
3. Go to **Bot** → click **Add Bot**
4. Under **Token**, click **Reset Token** → copy and save it (this is your `DISCORD_BOT_TOKEN`)
5. Scroll down and enable **Message Content Intent** → Save
6. Go to **OAuth2 → URL Generator**:
   - Scopes: `bot`
   - Bot Permissions: `Send Messages`
   - Copy the generated URL → paste in browser → add the bot to **any server you're in** (it just needs to exist)

### Step 2 — Get Your Discord User ID

1. Open Discord → Settings → Advanced → Enable **Developer Mode**
2. Right-click your own username anywhere → **Copy User ID**
3. This is your `DISCORD_USER_ID`

### Step 3 — Configure Your Sellers

Edit `sellers.json`. To find a seller's ID on Amazon:
1. Go to their storefront page on Amazon UK
2. The URL will look like: `amazon.co.uk/s?me=A1XXXXXXXXXXXXX`
3. The `me=` value is the seller ID

```json
{
  "sellers": [
    {
      "id": "A1XXXXXXXXXXXXX",
      "name": "Currys PC World"
    },
    {
      "id": "A2YYYYYYYYYYY",
      "name": "Another Seller"
    }
  ]
}
```

**To add a seller:** Add a new `{ "id": "...", "name": "..." }` entry.  
**To remove a seller:** Delete their entry. Their seen ASINs are kept in `seen_asins.json` under their ID (harmless to leave).  
**No restart needed on Railway** — the config reloads at every check cycle.

---

## ☁️ Deploying to Railway (Free Hosting)

Railway gives you 500 free hours/month — enough to run this 24/7.

1. Create a free account at [https://railway.app](https://railway.app)
2. Install the Railway CLI:
   ```bash
   npm install -g @railway/cli
   ```
3. From the `amazon-tracker` folder:
   ```bash
   railway login
   railway init
   railway up
   ```
4. In Railway dashboard → your project → **Variables**, add:
   - `DISCORD_BOT_TOKEN` = your bot token
   - `DISCORD_USER_ID` = your 18-digit user ID

That's it — it will run forever and restart itself if it ever crashes.

---

## 🖥️ Running Locally (for testing)

```bash
pip install -r requirements.txt

# Set env vars (Mac/Linux)
export DISCORD_BOT_TOKEN=your_token_here
export DISCORD_USER_ID=your_user_id_here

python tracker.py
```

On Windows:
```cmd
set DISCORD_BOT_TOKEN=your_token_here
set DISCORD_USER_ID=your_user_id_here
python tracker.py
```

---

## 📬 What the Discord DM Looks Like

```
🆕 New ASIN from Currys PC World
──────────────────────────────────
📦 Title   HP 15.6" Laptop AMD Ryzen 3 256GB Jet Black
🔑 ASIN    B0CXXXXXXXXX
💰 Price   £249.00
🔗 Link    https://www.amazon.co.uk/dp/B0CXXXXXXXXX
```
Plus the product thumbnail image.

---

## ⚠️ Notes

- Amazon can block scrapers. The script uses realistic browser headers and random delays (3–8s between requests) to minimise this risk.
- If you start tracking 50+ sellers and getting blocked, the next step is a proxy service (~£5/month). Ask for help if you reach that point.
- `seen_asins.json` is your "memory" — don't delete it or you'll get re-alerted for all existing products.
