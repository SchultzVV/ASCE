# Instagram Service 📸

> **Autonomous Social Commerce Engine** – automated content generation and
> publishing on Instagram for e-commerce product curation.

---

## Architecture

```
Main Website
     │
     │ REST (POST /posts · POST /viral-post)
     ▼
┌─────────────────────────────────────────────────────────┐
│                   instagram_service                     │
│                                                         │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │MusicAnalyzer│  │MediaComposer │  │CaptionGenerator│  │
│  └──────┬──────┘  └──────┬───────┘  └───────┬───────┘  │
│         │                │                   │          │
│         └────────────────┼───────────────────┘          │
│                          ▼                              │
│              ┌───────────────────────┐                  │
│              │    PostScheduler      │                  │
│              │    (APScheduler)      │                  │
│              └───────────┬───────────┘                  │
│                          ▼                              │
│              ┌───────────────────────┐                  │
│              │  InstagramPublisher   │                  │
│              │  (Meta Graph API)     │                  │
│              └───────────────────────┘                  │
└─────────────────────────────────────────────────────────┘
         │                 │               │
    Meta Graph         TikTok          MinIO / Redis
       API             Scraper         (media & cache)
```

---

## Features

| Module | Description |
|---|---|
| **MusicAnalyzer** | Scrapes TikTok trending page + Instagram reels audio. Scores tracks by usage, growth and region. |
| **MediaComposer** | Downloads product image → resizes → adds price overlay → produces MP4 reel via ffmpeg. |
| **CaptionGenerator** | Calls OpenAI / DeepSeek / OpenRouter to generate captions with emojis & CTA. |
| **PostScheduler** | APScheduler-backed scheduler with configurable daily posting windows & auto-retry. |
| **InstagramPublisher** | Two-step Meta Graph API flow: create container → publish. Polls video processing status. |

---

## Repository Structure

```
instagram_service/
│
├── app/
│   ├── main.py               ← FastAPI app factory & entry point
│   ├── config.py             ← pydantic-settings configuration
│   │
│   ├── routes/
│   │   ├── posts.py          ← POST /posts
│   │   └── viral.py          ← POST /viral-post
│   │
│   ├── services/
│   │   ├── music_analyzer.py
│   │   ├── media_composer.py
│   │   ├── caption_generator.py
│   │   ├── scheduler.py
│   │   └── instagram_publisher.py
│   │
│   ├── clients/
│   │   ├── meta_api.py       ← Meta Graph API HTTP client
│   │   ├── tiktok_client.py  ← TikTok public data scraper
│   │   └── instagram_client.py
│   │
│   ├── models/
│   │   └── post.py           ← Pydantic data models
│   │
│   └── utils/
│       ├── video_utils.py    ← ffmpeg wrappers
│       └── image_utils.py    ← Pillow helpers
│
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## Quick Start

### 1. Clone & configure

```bash
git clone https://github.com/SchultzVV/ASCE.git
cd ASCE
cp .env.example .env
# Edit .env with your credentials (Meta, OpenAI, MinIO …)
```

### 2. Run with Docker Compose

```bash
docker-compose up --build
```

The API will be available at **http://localhost:8000**.

Interactive docs: **http://localhost:8000/docs**

### 3. Run locally (without Docker)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# ffmpeg must be installed: https://ffmpeg.org/download.html
python -m app.main
```

---

## API Reference

### `POST /posts` – Create post

Creates an Instagram post job for a single product.

**Request**

```json
POST /posts
Content-Type: application/json

{
  "product_id": "123",
  "title": "Nike Running Shoes",
  "price": 49.90,
  "image_url": "https://example.com/images/nike.jpg"
}
```

**Response** `202 Accepted`

```json
{
  "job_id": "a1b2c3d4-...",
  "status": "scheduled",
  "scheduled_time": "2024-06-01T18:00:00",
  "caption": "🔥 Nike Running Shoes por apenas R$ 49,90! ...",
  "music": "Cruel Summer"
}
```

---

### `POST /viral-post` – Viral post

Selects the most viral product from a list, generates content, and schedules it.

**Viral scoring formula**

```
viral_score = discount * 0.40
            + price_attractiveness * 0.25
            + historical_performance * 0.20
            + trend_factor * 0.15
```

**Request**

```json
POST /viral-post
Content-Type: application/json

{
  "products": [
    {
      "id": "1",
      "title": "Headphones Pro",
      "price": 29.99,
      "discount": 50,
      "image_url": "https://example.com/headphones.jpg"
    },
    {
      "id": "2",
      "title": "Running Shoes",
      "price": 89.90,
      "discount": 20,
      "image_url": "https://example.com/shoes.jpg"
    }
  ]
}
```

**Response** `202 Accepted`

```json
{
  "selected_product": "Headphones Pro",
  "viral_score": 0.5875,
  "scheduled_time": "2024-06-01T20:00:00",
  "music": "Flowers",
  "caption": "🎧 Headphones Pro com 50% OFF! ...",
  "job_id": "b2c3d4e5-...",
  "status": "scheduled"
}
```

---

### `GET /posts` – List scheduled jobs

```bash
curl http://localhost:8000/posts
```

### `GET /health` – Health check

```bash
curl http://localhost:8000/health
# {"status":"ok","service":"instagram_service"}
```

---

## Meta API Configuration

1. Go to [Meta for Developers](https://developers.facebook.com/)
2. Create an app with **Instagram Graph API** product
3. Add your **Instagram Business Account** to the app
4. Generate a **long-lived access token** with these permissions:
   - `instagram_basic`
   - `instagram_content_publish`
   - `pages_read_engagement`
5. Copy your **Instagram Business Account ID** and **Page ID**
6. Populate `.env`:

```env
META_APP_ID=<your-app-id>
META_APP_SECRET=<your-app-secret>
ACCESS_TOKEN=<your-long-lived-token>
INSTAGRAM_BUSINESS_ID=<ig-business-account-id>
PAGE_ID=<facebook-page-id>
```

> **Note**: Access tokens expire. Implement token refresh for production use.

---

## LLM Configuration

Set `LLM_PROVIDER` in `.env` to one of:

| Provider | Environment variable | Notes |
|---|---|---|
| `openai` | `OPENAI_API_KEY` | Default – GPT-4o-mini |
| `deepseek` | `DEEPSEEK_API_KEY` | Cost-effective alternative |
| `openrouter` | `OPENROUTER_API_KEY` | OpenAI-compatible proxy |

---

## Scheduler Configuration

Configure posting windows via `POSTING_HOURS` (comma-separated 24-h values):

```env
POSTING_HOURS=9,12,18,20
```

---

## Environment Variables

See [`.env.example`](.env.example) for the full list.

---

## Development

```bash
# Install dev dependencies
pip install -r requirements.txt

# Run with auto-reload
DEBUG=true python -m app.main

# Run tests (if present)
pytest
```

---

## License

MIT
