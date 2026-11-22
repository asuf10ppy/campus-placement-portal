"""
Campus Placement Portal API
Made by: Py-oneers
                    Tanush Juturu       BC2026118
                    Aditya S Uranakar   BC2026008
                    SRINIVAS            
                    Darisipudi Kasuhik  BC2026032
                    DHRUVA
                    PUSHKAR
Course: Python Project 2026

WHAT THIS PROGRAM IS
    A worked course project showing how university campus placements work.
    It has:
      * four kinds of data (MODELS): students, companies, jobs, applications
      * three ROLES:                 officer, recruiter, and student
      * business RULES:              CGPA cutoffs, branches, deadlines,
                                     max 5 active applications, acceptance cascade
      * data that SURVIVES a restart: four JSON files, no database

HOW THE ROLES WORK (a simple stand-in for login)
    Every protected request carries a HEADER named X-Role:
        officer    (placement cell officer - manages everything)
        recruiter  (company recruiter - posts jobs, makes offers for own company)
        student    (university student - applies for jobs, accepts/declines offers)
    A recruiter also sends X-Company-Id (integer).
    A student also sends X-Student-Id (integer).

THE RULES OF THIS PLACEMENT PORTAL
    * A student must meet the job's minimum CGPA and branch requirements.
    * A student cannot apply to a closed job or after the job's deadline.
    * A student may hold at most 5 active applications at the same time.
    * A student cannot apply twice to the same job.
    * Transitioning to 'offered' requires remaining openings > 0 and unplaced student.
    * When a student 'accepts' an offer, they become placed (placed=True) and
      all their other active applications are automatically withdrawn.
    * Cannot delete a job with applications, or a company with jobs.
"""

import copy
from datetime import date
import json
import os
from typing import Annotated, Literal, get_args

from fastapi import FastAPI, Header, HTTPException, Query, Response
from pydantic import BaseModel, Field, StringConstraints, field_validator

app = FastAPI(
    title="Campus Placement Portal API",
    description="Placement portal: students, jobs and applications",
    version="4.6",
)

# =====================================================================
# SECTION 1 - SETTINGS
# =====================================================================
MAX_ACTIVE_APPLICATIONS = 5

Branch = Literal["CSE", "ECE", "ME", "CE", "EE"]
VALID_BRANCHES: list[Branch] = list(get_args(Branch))

JobStatus = Literal["open", "closed"]

ApplicationStatus = Literal[
    "applied", "shortlisted", "offered", "accepted", "rejected", "withdrawn", "declined"
]
ALL_APPLICATION_STATUSES: list[ApplicationStatus] = list(get_args(ApplicationStatus))
ACTIVE_STATUSES: list[ApplicationStatus] = ["applied", "shortlisted", "offered"]

ALLOWED_MOVES: dict[str, list[str]] = {
    "applied": ["shortlisted", "rejected", "withdrawn"],
    "shortlisted": ["offered", "rejected", "withdrawn"],
    "offered": ["accepted", "declined"],
    "rejected": [],
    "withdrawn": [],
    "declined": [],
    "accepted": [],
}

EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
DATE_PATTERN = r"^\d{4}-\d{2}-\d{2}$"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STUDENTS_FILE = os.path.join(BASE_DIR, "students.json")
COMPANIES_FILE = os.path.join(BASE_DIR, "companies.json")
JOBS_FILE = os.path.join(BASE_DIR, "jobs.json")
APPLICATIONS_FILE = os.path.join(BASE_DIR, "applications.json")


# =====================================================================
# SECTION 2 - STORAGE (file handling)
# =====================================================================

STARTER_STUDENTS = [
    {"id": 1, "roll_no": "2026CSE001", "name": "Aarav Sharma", "email": "aarav@example.com", "branch": "CSE", "cgpa": 9.1, "placed": False},
    {"id": 2, "roll_no": "2026ECE002", "name": "Diya Patel", "email": "diya@example.com", "branch": "ECE", "cgpa": 8.4, "placed": False},
    {"id": 3, "roll_no": "2026ME003", "name": "Rohan Verma", "email": "rohan@example.com", "branch": "ME", "cgpa": 7.2, "placed": False},
    {"id": 4, "roll_no": "2026CE004", "name": "Ananya Iyer", "email": "ananya@example.com", "branch": "CE", "cgpa": 6.2, "placed": False},
    {"id": 5, "roll_no": "2026EE005", "name": "Kabir Singh", "email": "kabir@example.com", "branch": "EE", "cgpa": 7.9, "placed": False},
]

STARTER_COMPANIES = [
    {"id": 1, "name": "TechCorp", "sector": "Software"},
    {"id": 2, "name": "ElectroWave", "sector": "Electronics"},
    {"id": 3, "name": "AutoMotors", "sector": "Automobile"},
]

STARTER_JOBS = [
    {
        "id": 1,
        "company_id": 1,
        "title": "Software Development Engineer",
        "package": 1800000,
        "min_cgpa": 8.0,
        "allowed_branches": ["CSE", "ECE"],
        "openings": 3,
        "deadline": "2026-12-31",
        "status": "open",
    },
    {
        "id": 2,
        "company_id": 1,
        "title": "Data Scientist",
        "package": 2200000,
        "min_cgpa": 8.5,
        "allowed_branches": ["CSE"],
        "openings": 1,
        "deadline": "2027-01-15",
        "status": "open",
    },
    {
        "id": 3,
        "company_id": 2,
        "title": "Hardware Systems Engineer",
        "package": 1200000,
        "min_cgpa": 7.0,
        "allowed_branches": ["ECE", "EE"],
        "openings": 2,
        "deadline": "2027-02-28",
        "status": "open",
    },
    {
        "id": 4,
        "company_id": 3,
        "title": "Mechanical Design Specialist",
        "package": 900000,
        "min_cgpa": 6.0,
        "allowed_branches": ["ME", "CE"],
        "openings": 4,
        "deadline": "2027-03-31",
        "status": "open",
    },
]

STARTER_APPLICATIONS = []

APPLICATION_REQUIRED_KEYS = {"id", "job_id", "student_id", "status", "applied_on", "package_offered"}


def save_data(path, data):
    """Write a whole list of dictionaries atomically via a temporary file."""
    tmp_path = f"{path}.tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=2, ensure_ascii=False)
            file.flush()
            os.fsync(file.fileno())
        os.replace(tmp_path, path)
    except Exception:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise


def _validate_records_shape(loaded, starter_data):
    """Ensure loaded JSON is a list of dictionaries with expected keys."""
    if not isinstance(loaded, list):
        raise ValueError(f"Expected a JSON list, got {type(loaded).__name__}")
    required_keys = set(starter_data[0].keys()) if starter_data else APPLICATION_REQUIRED_KEYS
    for item in loaded:
        if not isinstance(item, dict):
            raise ValueError(f"Expected JSON objects inside list, got {type(item).__name__}")
        if not required_keys.issubset(item.keys()):
            missing = sorted(required_keys - set(item.keys()))
            raise ValueError(f"Missing required keys: {missing}")


def _backup_corrupt_file(path):
    """Move a damaged or malformed data file to <path>.corrupt before rebuilding."""
    corrupt_path = f"{path}.corrupt"
    try:
        os.replace(path, corrupt_path)
    except OSError:
        pass
    return corrupt_path


def load_data(path, starter_data):
    """Read a JSON file, or back up & rebuild from starter data if missing, empty, or damaged."""
    if not os.path.exists(path):
        save_data(path, starter_data)
        return copy.deepcopy(starter_data)
    try:
        with open(path, "r", encoding="utf-8") as file:
            text = file.read().strip()
        if not text:
            corrupt_path = _backup_corrupt_file(path)
            print(f"Warning: {path} was empty (saved backup to {corrupt_path}). Rebuilding with starter data.")
            save_data(path, starter_data)
            return copy.deepcopy(starter_data)
        loaded = json.loads(text)
        _validate_records_shape(loaded, starter_data)
        return loaded
    except Exception as error:
        corrupt_path = _backup_corrupt_file(path)
        print(f"Warning: {path} was damaged ({error}; saved backup to {corrupt_path}). Rebuilding with starter data.")
        save_data(path, starter_data)
        return copy.deepcopy(starter_data)


students = load_data(STUDENTS_FILE, STARTER_STUDENTS)
companies = load_data(COMPANIES_FILE, STARTER_COMPANIES)
jobs = load_data(JOBS_FILE, STARTER_JOBS)
applications = load_data(APPLICATIONS_FILE, STARTER_APPLICATIONS)


# =====================================================================
# SECTION 3 - MODELS (Pydantic)
# =====================================================================

NonBlankStr20 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=20)]
NonBlankStr100 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


def _validate_iso_date(value: str | None) -> str | None:
    if value is not None:
        date.fromisoformat(value)
    return value


class StudentIn(BaseModel):
    """What the officer sends to register a new student."""
    roll_no: NonBlankStr20 = Field(examples=["2026CSE006"])
    name: NonBlankStr100 = Field(examples=["Priya Nair"])
    email: str = Field(pattern=EMAIL_PATTERN, examples=["priya@example.com"])
    branch: Branch = Field(examples=["CSE"])
    cgpa: float = Field(ge=0.0, le=10.0, examples=[8.5])


class StudentUpdateIn(BaseModel):
    """What the officer may send to modify fields of an existing student."""
    name: NonBlankStr100 | None = None
    email: str | None = Field(default=None, pattern=EMAIL_PATTERN)
    branch: Branch | None = None
    cgpa: float | None = Field(default=None, ge=0.0, le=10.0)


class StudentOut(BaseModel):
    """Student details sent back to callers."""
    id: int
    roll_no: str
    name: str
    email: str
    branch: Branch
    cgpa: float
    placed: bool


class CompanyIn(BaseModel):
    """What the officer sends to add a company."""
    name: NonBlankStr100 = Field(examples=["Google"])
    sector: NonBlankStr100 = Field(examples=["Software"])


class CompanyOut(BaseModel):
    """Company details sent back to callers."""
    id: int
    name: str
    sector: str


class JobIn(BaseModel):
    """What a recruiter or officer sends to post a job opening."""
    company_id: int = Field(gt=0, examples=[1])
    title: NonBlankStr100 = Field(examples=["Software Engineer"])
    package: int = Field(gt=0, examples=[1500000], description="Annual package, in rupees.")
    min_cgpa: float = Field(ge=0.0, le=10.0, examples=[7.5])
    allowed_branches: list[Branch] = Field(min_length=1, examples=[["CSE", "ECE"]])
    openings: int = Field(ge=1, le=100, examples=[3])
    deadline: str = Field(pattern=DATE_PATTERN, examples=["2027-06-30"], description="Last date to apply, as YYYY-MM-DD.")
    status: JobStatus = "open"

    @field_validator("deadline")
    @classmethod
    def check_deadline_date(cls, value: str) -> str:
        return _validate_iso_date(value)

    @field_validator("allowed_branches")
    @classmethod
    def deduplicate_branches(cls, value: list[Branch]) -> list[Branch]:
        return list(dict.fromkeys(value))


class JobUpdateIn(BaseModel):
    """What a recruiter or officer may send to change some fields of a job."""
    title: NonBlankStr100 | None = None
    package: int | None = Field(default=None, gt=0)
    min_cgpa: float | None = Field(default=None, ge=0.0, le=10.0)
    allowed_branches: list[Branch] | None = Field(default=None, min_length=1)
    openings: int | None = Field(default=None, ge=1, le=100)
    deadline: str | None = Field(default=None, pattern=DATE_PATTERN)
    status: JobStatus | None = None

    @field_validator("deadline")
    @classmethod
    def check_deadline_date(cls, value: str | None) -> str | None:
        return _validate_iso_date(value)

    @field_validator("allowed_branches")
    @classmethod
    def deduplicate_branches(cls, value: list[Branch] | None) -> list[Branch] | None:
        return list(dict.fromkeys(value)) if value is not None else None


class JobOut(BaseModel):
    """A job as sent back, including dynamically calculated openings."""
    id: int
    company_id: int
    title: str
    package: int
    min_cgpa: float
    allowed_branches: list[Branch]
    openings: int
    deadline: str
    status: JobStatus
    filled_openings: int
    remaining_openings: int


class ApplicationIn(BaseModel):
    """What a student sends to apply for a job."""
    job_id: int = Field(gt=0, examples=[1])
    student_id: int = Field(gt=0, examples=[1])


class ApplicationStatusUpdateIn(BaseModel):
    """What callers send to move the status of an application."""
    status: ApplicationStatus


class ApplicationOut(BaseModel):
    """Application details returned to callers."""
    id: int
    job_id: int
    student_id: int
    status: ApplicationStatus
    applied_on: str
    package_offered: int | None


class BranchStatsOut(BaseModel):
    """Branch-wise breakdown for placement statistics."""
    students: int
    placed: int
    percentage: float


class StatsOut(BaseModel):
    """Comprehensive placement statistics report."""
    total_students: int
    placed_students: int
    placement_percentage: float
    placement_by_branch: dict[str, BranchStatsOut]
    average_package: float
    highest_package: int
    applications_by_status: dict[str, int]
    unplaced_students: list[int]
    top_company_by_offers: str | None


class HealthOut(BaseModel):
    """Simple server status reply."""
    status: str


RoleHeader = Annotated[
    str | None,
    Header(alias="X-Role", description="Caller's role: officer, recruiter, or student."),
]
CompanyIdHeader = Annotated[
    str | None,
    Header(alias="X-Company-Id", description="Recruiter's own company id. Required when X-Role is recruiter."),
]
StudentIdHeader = Annotated[
    str | None,
    Header(alias="X-Student-Id", description="Student's own id. Required when X-Role is student."),
]
TodayOverride = Annotated[
    str | None,
    Query(description="Pretend today is this date (YYYY-MM-DD), so deadlines are easy to test."),
]
BranchFilter = Annotated[Branch | None, Query(description="Keep only this branch.")]


# =====================================================================
# SECTION 4 - HELPER FUNCTIONS
# Small reusable helper functions that keep endpoints clean and simple.
# Each lookup helper raises 404 itself if the item is not found.
# =====================================================================

def check_role(x_role: str | None, allowed_roles: list[str]) -> str:
    """Stop the request unless X-Role is one of the three known roles, and is allowed here."""
    if x_role not in ("student", "recruiter", "officer"):
        raise HTTPException(
            status_code=401,
            detail="Send the header X-Role with the value student, recruiter, or officer",
        )
    if x_role not in allowed_roles:
        raise HTTPException(status_code=403, detail=f"The role '{x_role}' is not allowed to do this")
    return x_role


def parse_positive_int_header(value: str | None, header_name: str) -> int:
    """Read a header as a positive integer, or stop with 401 if it is missing or invalid."""
    if value is None:
        raise HTTPException(status_code=401, detail=f"Missing required header {header_name}")
    try:
        parsed_value = int(value)
    except ValueError:
        raise HTTPException(status_code=401, detail=f"{header_name} must be an integer")
    if parsed_value <= 0:
        raise HTTPException(status_code=401, detail=f"{header_name} must be a positive integer")
    return parsed_value


def get_company_id_header(x_company_id: str | None) -> int:
    """Read and validate the X-Company-Id header sent by a recruiter."""
    return parse_positive_int_header(x_company_id, "X-Company-Id")


def get_student_id_header(x_student_id: str | None) -> int:
    """Read and validate the X-Student-Id header sent by a student."""
    return parse_positive_int_header(x_student_id, "X-Student-Id")


def ensure_recruiter_owns_company(x_company_id: str | None, company_id: int, message: str) -> None:
    """Stop a recruiter whose own company id does not match company_id."""
    if get_company_id_header(x_company_id) != company_id:
        raise HTTPException(status_code=403, detail=message)


def ensure_student_owns_record(x_student_id: str | None, student_id: int, message: str) -> None:
    """Stop a student whose own id does not match student_id."""
    if get_student_id_header(x_student_id) != student_id:
        raise HTTPException(status_code=403, detail=message)


def find_student(student_id: int) -> dict:
    """Find a student by id or stop with 404."""
    for student in students:
        if student["id"] == student_id:
            return student
    raise HTTPException(status_code=404, detail="Student not found")


def find_company(company_id: int) -> dict:
    """Find a company by id or stop with 404."""
    for company in companies:
        if company["id"] == company_id:
            return company
    raise HTTPException(status_code=404, detail="Company not found")


def find_job(job_id: int) -> dict:
    """Find a job by id or stop with 404."""
    for job in jobs:
        if job["id"] == job_id:
            return job
    raise HTTPException(status_code=404, detail="Job not found")


def find_application(application_id: int) -> dict:
    """Find an application by id or stop with 404."""
    for application in applications:
        if application["id"] == application_id:
            return application
    raise HTTPException(status_code=404, detail="Application not found")


def next_id(items: list[dict]) -> int:
    """Return the next integer id: highest existing id + 1 (1 if the list is empty)."""
    return max((item.get("id", 0) for item in items), default=0) + 1


def count_active_applications(student_id: int) -> int:
    """Count how many active applications this student holds right now."""
    return sum(
        1
        for application in applications
        if application["student_id"] == student_id and application["status"] in ACTIVE_STATUSES
    )


def count_filled_openings(job_id: int) -> int:
    """Count how many openings are filled (status offered or accepted)."""
    return sum(
        1
        for application in applications
        if application["job_id"] == job_id and application["status"] in ("offered", "accepted")
    )


def today_from_param(today: str | None) -> date:
    """Return the ?today= date if given, else the real date; a bad format gives 422."""
    if today is None:
        return date.today()
    try:
        return date.fromisoformat(today)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid date format for ?today=. Expected YYYY-MM-DD")


def check_student_eligibility(student: dict, job: dict) -> None:
    """Verify that a student satisfies both the CGPA and branch requirements of a job."""
    if student["cgpa"] < job["min_cgpa"]:
        raise HTTPException(
            status_code=409,
            detail=f"Student CGPA ({student['cgpa']}) is below minimum required ({job['min_cgpa']})",
        )
    if student["branch"] not in job["allowed_branches"]:
        raise HTTPException(
            status_code=409,
            detail=f"Student branch '{student['branch']}' is not eligible for this job",
        )


def build_job_out(job: dict) -> dict:
    """Return a job dictionary with computed filled and remaining openings attached."""
    filled = count_filled_openings(job["id"])
    return {**job, "filled_openings": filled, "remaining_openings": job["openings"] - filled}


# =====================================================================
# SECTION 5 - ENDPOINTS (18)
# Every endpoint follows 5 clear steps:
#   1. check the role
#   2. check that everything exists (404)
#   3. check the business rules (403/409/400)
#   4. update data and save
#   5. reply with status code and data
# =====================================================================

# ---------- 1. Health check (no role needed) ----------
@app.get("/health", response_model=HealthOut, tags=["system"], summary="Is the server alive?")
def health():
    return {"status": "ok"}


# ---------- 2. Students ----------
@app.post("/students", status_code=201, response_model=StudentOut, tags=["students"], summary="Register a student (officer)")
def add_student(body: StudentIn, x_role: RoleHeader = None):
    check_role(x_role, ["officer"])
    for existing_student in students:
        if existing_student["roll_no"].lower() == body.roll_no.lower():
            raise HTTPException(status_code=409, detail="A student with this roll number already exists")
        if existing_student["email"].lower() == body.email.lower():
            raise HTTPException(status_code=409, detail="A student with this email already exists")

    new_student = {
        "id": next_id(students),
        "roll_no": body.roll_no,
        "name": body.name,
        "email": body.email,
        "branch": body.branch,
        "cgpa": body.cgpa,
        "placed": False,
    }
    students.append(new_student)
    save_data(STUDENTS_FILE, students)
    return new_student


@app.get("/students", response_model=list[StudentOut], tags=["students"], summary="List students (officer)")
def list_students(
    branch: BranchFilter = None,
    placed: Annotated[bool | None, Query(description="Keep only placed (true) or unplaced (false) students.")] = None,
    x_role: RoleHeader = None,
):
    check_role(x_role, ["officer"])
    return [
        student
        for student in students
        if (branch is None or student["branch"] == branch)
        and (placed is None or student["placed"] == placed)
    ]


@app.get("/students/{student_id}", response_model=StudentOut, tags=["students"], summary="Get one student (officer or own student)")
def get_student(student_id: int, x_role: RoleHeader = None, x_student_id: StudentIdHeader = None):
    role = check_role(x_role, ["officer", "student"])
    if role == "student":
        ensure_student_owns_record(x_student_id, student_id, "Students can only view their own record")
    return find_student(student_id)


@app.patch("/students/{student_id}", response_model=StudentOut, tags=["students"], summary="Change student fields (officer)")
def update_student(student_id: int, body: StudentUpdateIn, x_role: RoleHeader = None):
    check_role(x_role, ["officer"])
    student = find_student(student_id)

    if body.email is not None:
        for other_student in students:
            if other_student["id"] != student_id and other_student["email"].lower() == body.email.lower():
                raise HTTPException(status_code=409, detail="A student with this email already exists")

    student.update(body.model_dump(exclude_none=True))
    save_data(STUDENTS_FILE, students)
    return student


# ---------- 3. Companies ----------
@app.post("/companies", status_code=201, response_model=CompanyOut, tags=["companies"], summary="Register a company (officer)")
def add_company(body: CompanyIn, x_role: RoleHeader = None):
    check_role(x_role, ["officer"])
    for existing_company in companies:
        if existing_company["name"].lower() == body.name.lower():
            raise HTTPException(status_code=409, detail="A company with this name already exists")

    new_company = {"id": next_id(companies), "name": body.name, "sector": body.sector}
    companies.append(new_company)
    save_data(COMPANIES_FILE, companies)
    return new_company


@app.get("/companies", response_model=list[CompanyOut], tags=["companies"], summary="List all companies (anyone)")
def list_companies():
    return companies


@app.delete("/companies/{company_id}", status_code=204, tags=["companies"], summary="Delete a company without jobs (officer)")
def delete_company(company_id: int, x_role: RoleHeader = None):
    check_role(x_role, ["officer"])
    company = find_company(company_id)
    if any(job["company_id"] == company["id"] for job in jobs):
        raise HTTPException(status_code=409, detail="Cannot delete a company with existing jobs")

    companies.remove(company)
    save_data(COMPANIES_FILE, companies)
    return Response(status_code=204)


# ---------- 4. Jobs ----------
@app.post("/jobs", status_code=201, response_model=JobOut, tags=["jobs"], summary="Post a job (recruiter or officer)")
def add_job(body: JobIn, x_role: RoleHeader = None, x_company_id: CompanyIdHeader = None):
    role = check_role(x_role, ["officer", "recruiter"])
    if role == "recruiter":
        ensure_recruiter_owns_company(x_company_id, body.company_id, "A recruiter can only post jobs for their own company")
    find_company(body.company_id)

    new_job = {"id": next_id(jobs), **body.model_dump()}
    jobs.append(new_job)
    save_data(JOBS_FILE, jobs)
    return build_job_out(new_job)


@app.get("/jobs", response_model=list[JobOut], tags=["jobs"], summary="List jobs with filters (anyone)")
def list_jobs(
    branch: BranchFilter = None,
    min_package: Annotated[int | None, Query(ge=0, description="Keep only jobs offering at least this package.")] = None,
    open_only: Annotated[bool, Query(description="If true, hide closed jobs and jobs past their deadline.")] = False,
    today: TodayOverride = None,
):
    current_date = today_from_param(today)
    result = []
    for job in jobs:
        if open_only:
            if job["status"] == "closed" or date.fromisoformat(job["deadline"]) < current_date:
                continue
        if branch is not None and branch not in job["allowed_branches"]:
            continue
        if min_package is not None and job["package"] < min_package:
            continue
        result.append(build_job_out(job))
    return result


@app.get("/jobs/{job_id}", response_model=JobOut, tags=["jobs"], summary="Get one job by id (anyone)")
def get_job(job_id: int):
    return build_job_out(find_job(job_id))


@app.patch("/jobs/{job_id}", response_model=JobOut, tags=["jobs"], summary="Update job fields or status (recruiter or officer)")
def update_job(job_id: int, body: JobUpdateIn, x_role: RoleHeader = None, x_company_id: CompanyIdHeader = None):
    role = check_role(x_role, ["officer", "recruiter"])
    job = find_job(job_id)

    if role == "recruiter":
        ensure_recruiter_owns_company(x_company_id, job["company_id"], "A recruiter can only edit jobs for their own company")

    if body.openings is not None:
        filled = count_filled_openings(job["id"])
        if body.openings < filled:
            raise HTTPException(status_code=409, detail=f"Cannot reduce openings below currently filled count ({filled})")

    job.update(body.model_dump(exclude_none=True))
    save_data(JOBS_FILE, jobs)
    return build_job_out(job)


@app.delete("/jobs/{job_id}", status_code=204, tags=["jobs"], summary="Delete a job without applications (officer)")
def delete_job(job_id: int, x_role: RoleHeader = None):
    check_role(x_role, ["officer"])
    job = find_job(job_id)
    if any(application["job_id"] == job["id"] for application in applications):
        raise HTTPException(status_code=409, detail="Cannot delete a job with existing applications")

    jobs.remove(job)
    save_data(JOBS_FILE, jobs)
    return Response(status_code=204)


# ---------- 5. Applications ----------
@app.post("/applications", status_code=201, response_model=ApplicationOut, tags=["applications"], summary="Apply for a job (student)")
def apply_job(body: ApplicationIn, today: TodayOverride = None, x_role: RoleHeader = None, x_student_id: StudentIdHeader = None):
    check_role(x_role, ["student"])
    ensure_student_owns_record(x_student_id, body.student_id, "Students can only apply on behalf of themselves")

    student = find_student(body.student_id)
    job = find_job(body.job_id)

    # R1. Job must not be closed
    if job["status"] == "closed":
        raise HTTPException(status_code=409, detail="This job is closed for applications")

    # R2. Deadline check
    current_date = today_from_param(today)
    if current_date > date.fromisoformat(job["deadline"]):
        raise HTTPException(status_code=409, detail="The application deadline for this job has passed")

    # R3. Placed students cannot apply
    if student["placed"]:
        raise HTTPException(status_code=409, detail="Student is already placed and cannot apply for new jobs")

    # R4 & R5. Minimum CGPA and branch eligibility
    check_student_eligibility(student, job)

    # R6. No duplicate applications
    if any(app_item["student_id"] == student["id"] and app_item["job_id"] == job["id"] for app_item in applications):
        raise HTTPException(status_code=409, detail="Student has already applied to this job")

    # R7. Maximum active applications limit
    if count_active_applications(student["id"]) >= MAX_ACTIVE_APPLICATIONS:
        raise HTTPException(
            status_code=409,
            detail=f"Maximum active applications limit of {MAX_ACTIVE_APPLICATIONS} reached",
        )

    new_application = {
        "id": next_id(applications),
        "job_id": job["id"],
        "student_id": student["id"],
        "status": "applied",
        "applied_on": current_date.isoformat(),
        "package_offered": None,
    }
    applications.append(new_application)
    save_data(APPLICATIONS_FILE, applications)
    return new_application


@app.get("/students/{student_id}/applications", response_model=list[ApplicationOut], tags=["applications"], summary="List student applications (officer or own student)")
def list_student_applications(student_id: int, x_role: RoleHeader = None, x_student_id: StudentIdHeader = None):
    role = check_role(x_role, ["officer", "student"])
    if role == "student":
        ensure_student_owns_record(x_student_id, student_id, "Students can only view their own applications")
    find_student(student_id)
    return [application for application in applications if application["student_id"] == student_id]


@app.get("/applications", response_model=list[ApplicationOut], tags=["applications"], summary="List applications (officer or recruiter for own jobs)")
def list_applications(
    status: Annotated[ApplicationStatus | None, Query(description="Keep only applications in this status.")] = None,
    x_role: RoleHeader = None,
    x_company_id: CompanyIdHeader = None,
):
    role = check_role(x_role, ["officer", "recruiter"])
    company_job_ids = None
    if role == "recruiter":
        caller_company_id = get_company_id_header(x_company_id)
        company_job_ids = {job["id"] for job in jobs if job["company_id"] == caller_company_id}

    return [
        application
        for application in applications
        if (company_job_ids is None or application["job_id"] in company_job_ids)
        and (status is None or application["status"] == status)
    ]


@app.patch("/applications/{application_id}/status", response_model=ApplicationOut, tags=["applications"], summary="Transition application status (officer, recruiter, student)")
def update_application_status(
    application_id: int,
    body: ApplicationStatusUpdateIn,
    today: TodayOverride = None,
    x_role: RoleHeader = None,
    x_company_id: CompanyIdHeader = None,
    x_student_id: StudentIdHeader = None,
):
    # Step 1: Role check
    role = check_role(x_role, ["officer", "recruiter", "student"])

    # Step 2: Existence check
    application = find_application(application_id)
    job = find_job(application["job_id"])
    student = find_student(application["student_id"])

    # Step 3: Ownership check
    if role == "recruiter":
        ensure_recruiter_owns_company(x_company_id, job["company_id"], "A recruiter can only manage applications for their own company")
    elif role == "student":
        ensure_student_owns_record(x_student_id, application["student_id"], "Students can only manage their own applications")

    # Step 4: May-this-role-set-this-status check
    target_status = body.status
    if role in ("officer", "recruiter"):
        if target_status not in ("shortlisted", "rejected", "offered"):
            raise HTTPException(status_code=403, detail=f"The role '{role}' cannot set status to '{target_status}'")
    elif role == "student":
        if target_status not in ("withdrawn", "accepted", "declined"):
            raise HTTPException(status_code=403, detail=f"A student cannot set status to '{target_status}'")

    # Step 5: Date check
    current_date = today_from_param(today)
    if today is not None and current_date < date.fromisoformat(application["applied_on"]):
        raise HTTPException(status_code=400, detail="A status change cannot happen before the application date")

    # Step 6: Allowed move check (R8)
    current_status = application["status"]
    if target_status not in ALLOWED_MOVES.get(current_status, []):
        raise HTTPException(
            status_code=409,
            detail=f"Status move from '{current_status}' to '{target_status}' is not allowed",
        )

    # Step 7: Moving to 'offered' (R9)
    if target_status == "offered":
        if student["placed"]:
            raise HTTPException(status_code=409, detail="Student is already placed and cannot receive new offers")
        remaining = job["openings"] - count_filled_openings(job["id"])
        if remaining <= 0:
            raise HTTPException(status_code=409, detail="No remaining openings available for this job")
        application["package_offered"] = job["package"]
        application["status"] = "offered"
        save_data(APPLICATIONS_FILE, applications)
        return application

    # Step 8: Moving to 'accepted' (R10 - acceptance cascade)
    if target_status == "accepted":
        application["status"] = "accepted"
        student["placed"] = True
        for other_application in applications:
            if (
                other_application["student_id"] == student["id"]
                and other_application["id"] != application["id"]
                and other_application["status"] in ACTIVE_STATUSES
            ):
                other_application["status"] = "withdrawn"
        save_data(STUDENTS_FILE, students)
        save_data(APPLICATIONS_FILE, applications)
        return application

    # Step 9: Any other standard transition (shortlisted, rejected, withdrawn, declined)
    application["status"] = target_status
    save_data(APPLICATIONS_FILE, applications)
    return application


# ---------- 6. Placement statistics report ----------
@app.get("/stats", response_model=StatsOut, tags=["reports"], summary="Placement report (officer)")
def get_stats(today: TodayOverride = None, x_role: RoleHeader = None):
    check_role(x_role, ["officer"])
    today_from_param(today)

    total_students = len(students)
    placed_students = sum(1 for student in students if student["placed"])
    unplaced_students = [student["id"] for student in students if not student["placed"]]
    placement_percentage = round((placed_students / total_students) * 100, 1) if total_students > 0 else 0.0

    placement_by_branch = {}
    for branch in VALID_BRANCHES:
        branch_students = [student for student in students if student["branch"] == branch]
        branch_total = len(branch_students)
        branch_placed = sum(1 for student in branch_students if student["placed"])
        branch_percentage = round((branch_placed / branch_total) * 100, 1) if branch_total > 0 else 0.0
        placement_by_branch[branch] = {
            "students": branch_total,
            "placed": branch_placed,
            "percentage": branch_percentage,
        }

    accepted_packages = [
        application["package_offered"]
        for application in applications
        if application["status"] == "accepted" and application.get("package_offered") is not None
    ]
    average_package = round(sum(accepted_packages) / len(accepted_packages), 1) if accepted_packages else 0.0
    highest_package = max(accepted_packages, default=0)

    applications_by_status = {status: 0 for status in ALL_APPLICATION_STATUSES}
    for application in applications:
        if application["status"] in applications_by_status:
            applications_by_status[application["status"]] += 1

    company_offers = {}
    for application in applications:
        if application["status"] in ("offered", "accepted"):
            job = next((j for j in jobs if j["id"] == application["job_id"]), None)
            if job is not None:
                company_offers[job["company_id"]] = company_offers.get(job["company_id"], 0) + 1

    top_company_by_offers = None
    if company_offers:
        top_company_id = max(company_offers, key=company_offers.get)
        company = next((c for c in companies if c["id"] == top_company_id), None)
        if company is not None:
            top_company_by_offers = company["name"]

    return {
        "total_students": total_students,
        "placed_students": placed_students,
        "placement_percentage": placement_percentage,
        "placement_by_branch": placement_by_branch,
        "average_package": average_package,
        "highest_package": highest_package,
        "applications_by_status": applications_by_status,
        "unplaced_students": unplaced_students,
        "top_company_by_offers": top_company_by_offers,
    }

# Thank you
# End of Campus Placement Portal API
