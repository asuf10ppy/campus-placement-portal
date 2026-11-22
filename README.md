# Campus Placement Portal API

Backend API for managing college placements — students, companies, job postings, and applications — built with Python, FastAPI, and local JSON storage.

**Team Py-oneers** | Python Project 2026

---

## Setup & Run

```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

Once running, open **http://127.0.0.1:8000/docs** to try out the endpoints.

On the first run, the app creates `students.json`, `companies.json`, `jobs.json`, and `applications.json` with starter data. To reset to a clean state, stop the server, delete those four files, and start it again.

---

## Roles & Headers

Protected endpoints use request headers to identify who is calling:

| Role | Required Headers | Access |
|---|---|---|
| Officer | `X-Role: officer` | Full access to everything |
| Recruiter | `X-Role: recruiter`, `X-Company-Id: <id>` | Manage jobs and applications for own company |
| Student | `X-Role: student`, `X-Student-Id: <id>` | View own profile, apply to jobs, respond to offers |

Public endpoints (`GET /health`, `GET /companies`, `GET /jobs`, `GET /jobs/{id}`) require no headers.

---

## Key Rules

- **Eligibility:** Students must meet the job's minimum CGPA and allowed branch list.
- **Deadlines & Status:** No applications to closed jobs, past the deadline, or duplicates for the same job.
- **Active Limit:** Max 5 active applications (`applied`, `shortlisted`, `offered`) per student at a time.
- **Offer Acceptance:** Accepting an offer marks the student as placed and automatically withdraws all their other active applications. Placed students cannot apply to new jobs.
- **Safe Deletes:** Companies with jobs and jobs with applications cannot be deleted.
- **Date Testing:** Pass `?today=YYYY-MM-DD` to test deadline behavior without changing your system clock.

---

## Endpoints Overview

- **System:** `GET /health`, `GET /stats`
- **Students:** `POST /students`, `GET /students`, `GET /students/{id}`, `PATCH /students/{id}`
- **Companies:** `POST /companies`, `GET /companies`, `DELETE /companies/{id}`
- **Jobs:** `POST /jobs`, `GET /jobs`, `GET /jobs/{id}`, `PATCH /jobs/{id}`, `DELETE /jobs/{id}`
- **Applications:** `POST /applications`, `GET /applications`, `GET /students/{id}/applications`, `PATCH /applications/{id}/status`

---

## Testing

Start the server on a clean state, then run the test script in another terminal:

```bash
python check_placement.py
```

---

## Project Structure

- `main.py` — FastAPI app, Pydantic models, business rules, and JSON persistence
- `check_placement.py` — automated test checklist
- `requirements.txt` — dependencies