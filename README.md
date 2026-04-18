# Job System

A distributed job processing and monitoring application demonstrating asynchronous job queue architecture with real-time updates.

## Overview

Submit jobs through a React UI, process them asynchronously via a worker, and watch status updates in real time over WebSocket. Failed jobs are automatically retried with exponential backoff and eventually moved to a dead letter queue.

## Architecture

```
Frontend (React) ──HTTP──► Backend (FastAPI) ──Redis──► Worker
                 ◄─WebSocket─┘                    └──────────►
```

- **Backend** — FastAPI REST API + WebSocket server on port `8003`
- **Worker** — Pulls jobs from Redis queue and executes them
- **Frontend** — React SPA on port `5173` for submitting and monitoring jobs
- **Redis** — Message broker, job store, and pub/sub channel

## Job Lifecycle

```
QUEUED → RUNNING → SUCCEEDED
                 ↘ FAILED → (retry with backoff) → DEAD
```

Jobs that fail are retried up to `max_retries` times using exponential backoff (`min(30, 2^attempt)` seconds). After exhausting retries they move to a dead letter queue.

## Job Types

| Type | Simulated Duration | Failure Rate |
|---|---|---|
| `email_send` | 1s | 25% |
| `pdf_render` | 2s | 20% |
| `data_sync` | 1.5s | 15% |
| `generic_task` | 0.8s | 10% |

## Prerequisites

- Python 3.8+
- Node.js 16+
- Redis running on `localhost:6379`

## Getting Started

Run each of the following in a separate terminal:

**1. Backend**
```bash
cd backend
pip install -r requirements.txt
python -m uvicorn main:app --reload --port 8003
```

**2. Worker**
```bash
cd worker
pip install -r requirements.txt
python worker.py
```

**3. Frontend**
```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173) in your browser.

## Configuration

| Variable | Default | Description |
|---|---|---|
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection string |

## Project Structure

```
job-system/
├── backend/
│   ├── main.py          # FastAPI app, REST endpoints, WebSocket handler
│   ├── job_queue.py     # Redis queue management, retry logic, pub/sub
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.jsx      # Job submission form and live status table
│   │   └── api.js       # API client and WebSocket URL helpers
│   └── package.json
└── worker/
    ├── worker.py        # Job processor loop with simulated handlers
    └── requirements.txt
```

## Frontend Scripts

```bash
npm run dev      # Start dev server with hot reload
npm run build    # Production build
npm run preview  # Preview production build
npm run lint     # Run ESLint
```
