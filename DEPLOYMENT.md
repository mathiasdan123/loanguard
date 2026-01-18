# LoanGuard Deployment Guide

This guide walks you through deploying LoanGuard to production with all features enabled.

## Quick Links

| Service | Purpose | Free Tier |
|---------|---------|-----------|
| [Railway](https://railway.app) | Hosting + PostgreSQL | $5 credit/month |
| [Clerk](https://clerk.com) | Authentication | 10k users free |
| [SendGrid](https://sendgrid.com) | Email notifications | 100 emails/day |
| [Anthropic](https://console.anthropic.com) | AI document analysis | Pay per use |

---

## Step 1: Set Up PostgreSQL Database

### Option A: Railway (Recommended - Easiest)

1. Go to [railway.app](https://railway.app) and sign in with GitHub
2. Click **"New Project"** → **"Provision PostgreSQL"**
3. Click on the PostgreSQL service → **"Variables"** tab
4. Copy the `DATABASE_URL` value

### Option B: Supabase (Free)

1. Go to [supabase.com](https://supabase.com) and create a project
2. Go to **Settings** → **Database** → **Connection string**
3. Copy the URI (use the "Transaction" pooler for serverless)

---

## Step 2: Set Up Clerk Authentication

1. Go to [clerk.com](https://clerk.com) and create an account
2. Create a new application
3. Choose authentication methods (Email, Google, etc.)
4. Go to **API Keys** and copy:
   - `CLERK_PUBLISHABLE_KEY` (starts with `pk_`)
   - `CLERK_SECRET_KEY` (starts with `sk_`)

5. For JWT verification, go to **JWT Templates**:
   - Click **"New template"** → Choose **"Blank"**
   - Name it "loanguard"
   - Copy the **Public Key** (PEM format)
   - Save this as `CLERK_JWT_KEY`

---

## Step 3: Set Up SendGrid Email

1. Go to [sendgrid.com](https://sendgrid.com) and create an account
2. Complete sender verification (verify your email domain)
3. Go to **Settings** → **API Keys** → **Create API Key**
4. Give it "Full Access" and copy the key (starts with `SG.`)
5. Save as `SENDGRID_API_KEY`

---

## Step 4: Get Anthropic API Key

1. Go to [console.anthropic.com](https://console.anthropic.com)
2. Create an account and add billing
3. Go to **API Keys** → **Create Key**
4. Copy and save as `ANTHROPIC_API_KEY`

---

## Step 5: Deploy to Railway

### 5a. Push code to GitHub

```bash
cd loan-compliance-agent
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/YOUR_USERNAME/loanguard.git
git push -u origin main
```

### 5b. Deploy on Railway

1. Go to [railway.app](https://railway.app)
2. Click **"New Project"** → **"Deploy from GitHub repo"**
3. Select your repository
4. Railway will auto-detect the Dockerfile

### 5c. Add Environment Variables

In Railway, click on your service → **Variables** → **Add Variable**:

```
DATABASE_URL=<your postgresql url>
ANTHROPIC_API_KEY=sk-ant-...
CLERK_PUBLISHABLE_KEY=pk_test_...
CLERK_SECRET_KEY=sk_test_...
CLERK_JWT_KEY=-----BEGIN PUBLIC KEY-----...
SENDGRID_API_KEY=SG...
FROM_EMAIL=alerts@yourdomain.com
FRONTEND_URL=https://your-app.railway.app
ALLOWED_ORIGINS=https://your-app.railway.app
```

### 5d. Add PostgreSQL (if you haven't)

1. In your Railway project, click **"+ New"** → **"Database"** → **"PostgreSQL"**
2. Railway will automatically set `DATABASE_URL` for your app

### 5e. Deploy

Railway will automatically deploy when you push to GitHub. 

Your API will be available at: `https://your-app.up.railway.app`

---

## Step 6: Deploy Frontend

### Option A: Serve from API (Simple)

The API can serve the frontend. Just access your Railway URL.

### Option B: Vercel (Recommended for production)

1. Go to [vercel.com](https://vercel.com)
2. Import your GitHub repo
3. Set the root directory to `web/`
4. Add environment variable:
   ```
   VITE_CLERK_PUBLISHABLE_KEY=pk_test_...
   VITE_API_URL=https://your-api.railway.app
   ```

---

## Step 7: Configure Clerk Redirect URLs

1. Go to Clerk Dashboard → **Paths**
2. Add your production URLs:
   - Sign-in URL: `https://your-app.com/sign-in`
   - Sign-up URL: `https://your-app.com/sign-up`
   - After sign-in URL: `https://your-app.com/`

---

## Local Development

### With Docker (Recommended)

```bash
# Copy environment file
cp .env.example .env
# Edit .env with your values

# Start everything
docker-compose up

# API at http://localhost:8000
# Docs at http://localhost:8000/docs
```

### Without Docker

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export DATABASE_URL="postgresql://localhost:5432/loanguard"
# ... other variables

# Run database migrations
python -c "from src.database import init_db; init_db()"

# Start server
uvicorn src.api_v2:app --reload
```

---

## Testing the Deployment

1. **Check API health:**
   ```bash
   curl https://your-app.railway.app/api/health
   ```

2. **View API docs:**
   Open `https://your-app.railway.app/docs` in browser

3. **Create a demo loan:**
   Sign in and click "Create Demo Loan"

4. **Test email:**
   Check your inbox for the welcome email

---

## Troubleshooting

### "Database connection failed"
- Check `DATABASE_URL` format: `postgresql://user:pass@host:port/dbname`
- Ensure the database exists
- Check if Railway/Supabase allows external connections

### "Authentication failed"
- Verify `CLERK_PUBLISHABLE_KEY` matches your Clerk app
- Check `CLERK_JWT_KEY` is the full PEM key including headers
- Ensure Clerk app URLs are configured correctly

### "Emails not sending"
- Verify sender email is verified in SendGrid
- Check SendGrid API key has send permissions
- Look at SendGrid Activity Feed for errors

### "Document analysis not working"
- Verify `ANTHROPIC_API_KEY` is valid
- Check you have credits in your Anthropic account
- API will fall back to mock data if key is missing

---

## Cost Estimate

For a small deployment (< 100 users):

| Service | Monthly Cost |
|---------|--------------|
| Railway (API + DB) | ~$5-10 |
| Clerk | Free |
| SendGrid | Free |
| Anthropic | ~$5-20 (usage based) |
| **Total** | **~$10-30/month** |

---

## Next Steps

After deployment:

1. **Custom domain**: Add your domain in Railway/Vercel settings
2. **SSL**: Automatically provided by Railway/Vercel
3. **Monitoring**: Consider adding [Sentry](https://sentry.io) for error tracking
4. **Analytics**: Add [PostHog](https://posthog.com) or [Mixpanel](https://mixpanel.com)

---

## Support

- Railway docs: https://docs.railway.app
- Clerk docs: https://clerk.com/docs
- SendGrid docs: https://docs.sendgrid.com
- FastAPI docs: https://fastapi.tiangolo.com
