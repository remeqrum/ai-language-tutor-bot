# AI Language Tutor Bot

Personal Telegram bot for learning any foreign language (from A2 to C1). The bot acts as a strict tutor, helping to expand vocabulary, practice sentence construction, and correct grammar in real time. Languages are configured via environment variables!

## Key Features
- **Vocabulary Boost:** The bot pulls 3 random words from the user's personal database and asks to form one complex sentence with them in the target language.
- **Sentence Builder:** The bot generates a complex phrase in your native language and asks to translate it into the target language without hints, strictly evaluating word order and grammar.
- **Free Chat (Word Addition Mode):** Any sent word is translated, added to the user's database along with an example of a complex sentence, and then the bot asks to translate a similar phrase for reinforcement.
- **Multi-user Isolation:** The bot supports an unlimited number of students. Each word in the database is tied to a unique `telegram_id` of the person adding it. Other users' words do not mix during training.

## Project Architecture
The project is built on a 100% free technology stack:
1. **Python 3** + `python-telegram-bot` (Logic and messenger connection).
2. **Google Gemini API** (AI engine, with a "strict tutor" system prompt).
3. **Supabase (PostgreSQL)** (Cloud database for persistent word storage).
4. **Flask** (Background dummy web server inside the script to keep active status in the cloud).
5. **Render.com** (Free server hosting "Free Web Service").
6. **Cron-job.org** ("Pinger" that pings the Render server via HTTP every 14 minutes to prevent it from sleeping).

## Database Structure (Supabase SQL)
For the bot to work, a `words` table is required with the following columns:
```sql
CREATE TABLE words (
  id uuid default uuid_generate_v4() primary key,
  telegram_id bigint not null,
  word text not null,
  translation text not null,
  level integer default 0,
  last_reviewed timestamp with time zone default now(),
  created_at timestamp with time zone default now()
);
```

## Local Setup
For development and local launch, create a `.env` file in the project root with the following keys:
```env
TELEGRAM_TOKEN=your_bot_token_from_BotFather
GEMINI_API_KEY=your_key_from_Google_AI_Studio
SUPABASE_URL=your_link_like_https://xxxx.supabase.co
SUPABASE_KEY=your_long_supabase_jwt_token
NATIVE_LANGUAGE=Russian
TARGET_LANGUAGE=Slovak
```

Install dependencies and run:
```bash
pip install -r requirements.txt
python src/main.py
```

## Deployment (Make the Bot Independent 24/7)
To make the bot run around the clock even when your computer is off, we use a combo of two free services: **Render.com** (for hosting the code) and **Cron-job.org** (to prevent the free server from "sleeping" due to inactivity).

**Step 1. Deploy on Render.com**
1. Register at [Render.com](https://render.com) (can log in via GitHub).
2. Create a new **Web Service** and connect your GitHub repository.
3. In the service settings, specify:
   - **Environment:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python src/main.py`
4. Go to the **Environment** tab and add all variables from your `.env` file (tokens, keys, and languages).
5. Click **Deploy**. In a couple of minutes, the bot will launch! Copy the link to your service (e.g., `https://your-bot-name.onrender.com`).

**Step 2. Protection Against "Sleeping" with Cron-job.org**
Free Render servers sleep if no requests come in for 15 minutes (that's why a dummy Flask web server is built into the code).
1. Register at [Cron-job.org](https://cron-job.org).
2. Create a new job (Create Cronjob).
3. In the URL field, paste the copied link to your Render service (just the main page `https://...`).
4. Set the schedule: **Every 14 minutes**.
5. Save. Now the cron-job will ping your bot every 14 minutes, and it will work completely autonomously and free 24/7!
