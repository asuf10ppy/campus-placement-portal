# Campus Placement Portal API

**Made by:** Team Py-oneers  
**Course:** Python Project 2026  

| Name | Roll No |
| --- | --- |
| Tanush Juturu | BC2026118 |
| Aditya S Uranakar | BC2026008 |
| Srinivas | BC2026114 |
| Darisipudi Krishna Kaushik | BC2026032 |
| Dhruva | |
| Pushkar Peshwe | BC2026079 |

## What This Program Is

A course project showing how university campus placements work. It includes:
- **Four kinds of data (Models):** students, companies, jobs, applications
- **Three roles:** officer, recruiter, and student
- **Business rules:** CGPA cutoffs, branch eligibility, deadlines, max 5 active applications, and acceptance cascade
- **Persistent storage:** four local JSON files (no database)

## Setup & Run

```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

Once running, open **http://127.0.0.1:8000/docs** to try out the endpoints.

On the first run, the app creates `students.json`, `companies.json`, `jobs.json`, and `applications.json` with starter data. To reset to a clean state, stop the server, delete those four files, and start it again.

## How the Roles Work

Protected endpoints use request headers as a simple stand-in for login:

| Role | Required Headers | Access |
| --- | --- | --- |
| Officer | `X-Role: officer` | Placement cell officer — manages everything |
| Recruiter | `X-Role: recruiter`, `X-Company-Id: <id>` | Posts jobs and makes offers for their own company |
| Student | `X-Role: student`, `X-Student-Id: <id>` | Views own profile, applies for jobs, accepts/declines offers |

Public endpoints (`GET /health`, `GET /companies`, `GET /jobs`, `GET /jobs/{id}`) require no headers.

## Rules of the Placement Portal

- A student must meet the job's minimum CGPA and branch requirements.
- A student cannot apply to a closed job or after the job's deadline.
- A student may hold at most 5 active applications (`applied`, `shortlisted`, `offered`) at the same time.
- A student cannot apply twice to the same job.
- Transitioning to `offered` requires remaining openings > 0 and an unplaced student.
- When a student accepts an offer, they become placed (`placed=True`) and all their other active applications are automatically withdrawn. Placed students cannot apply to new jobs.
- Cannot delete a job with applications, or a company with jobs.
- Pass `?today=YYYY-MM-DD` on supported endpoints to test deadlines without changing your system clock.

## Endpoints Overview

- **System:** `GET /health`, `GET /stats`
- **Students:** `POST /students`, `GET /students`, `GET /students/{id}`, `PATCH /students/{id}`
- **Companies:** `POST /companies`, `GET /companies`, `DELETE /companies/{id}`
- **Jobs:** `POST /jobs`, `GET /jobs`, `GET /jobs/{id}`, `PATCH /jobs/{id}`, `DELETE /jobs/{id}`
- **Applications:** `POST /applications`, `GET /applications`, `GET /students/{id}/applications`, `PATCH /applications/{id}/status`

## Testing

Start the server on a clean state, then run the test script in another terminal:

```bash
python check_placement.py
```

## Project Structure

- `main.py` — FastAPI app, Pydantic models, business rules, and JSON persistence
- `check_placement.py` — automated test checklist
- `requirements.txt` — dependencies
