"""
check_placement.py  -  runs the test checklist against a RUNNING Placement API
=================================================================================
You do NOT need to understand every line of this file. It does by machine what
the checklist in the project guide asks you to do by hand in /docs: send a request,
and compare the status code (and sometimes the reply) with what we expect.

HOW TO USE IT
    1. Stop the server, delete students.json, companies.json, jobs.json and
       applications.json (the script needs a CLEAN start), then start the server again:
            uvicorn main:app --reload
    2. In a second terminal (once):   pip install requests
    3. Run:                           python check_placement.py
       To test a server on another port:  python check_placement.py http://127.0.0.1:8010
    4. Every line says PASS or FAIL. To run it again, repeat from step 1.

The restart test cannot be automated here. Do it by hand at the end:
stop the server, start it again, and check GET /students and GET /applications.
"""

import sys

import requests

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
SIM_TODAY = "2026-11-20"

# Header shortcuts for testing different roles
OFF = {"X-Role": "officer"}
REC1 = {"X-Role": "recruiter", "X-Company-Id": "1"}
REC2 = {"X-Role": "recruiter", "X-Company-Id": "2"}
STU1 = {"X-Role": "student", "X-Student-Id": "1"}
STU2 = {"X-Role": "student", "X-Student-Id": "2"}
STU3 = {"X-Role": "student", "X-Student-Id": "3"}
STU4 = {"X-Role": "student", "X-Student-Id": "4"}
STU6 = {"X-Role": "student", "X-Student-Id": "6"}
STU7 = {"X-Role": "student", "X-Student-Id": "7"}

passed = 0
failed = 0


def check(name, response, expected_status, test=None):
    """Compare the status code, and (if `test` is given) the reply body."""
    global passed, failed
    ok = response.status_code == expected_status
    if ok and test is not None:
        try:
            ok = test(response.json())
        except Exception:
            ok = False
    if ok:
        passed += 1
        print(f"PASS  {name}")
    else:
        failed += 1
        print(f"FAIL  {name}   (got {response.status_code}, expected {expected_status})   {response.text[:120]}")


def get(path, headers=None):
    return requests.get(BASE + path, headers=headers)


def post(path, body=None, headers=None):
    return requests.post(BASE + path, json=body, headers=headers)


def patch(path, body=None, headers=None):
    return requests.patch(BASE + path, json=body, headers=headers)


def delete(path, headers=None):
    return requests.delete(BASE + path, headers=headers)


# ---------------------------------------------------------------- clean start?
try:
    start_students = get("/students", OFF).json()
    start_companies = get("/companies").json()
    start_jobs = get("/jobs").json()
    start_apps = get("/applications", OFF).json()
except requests.exceptions.ConnectionError:
    print(f"Cannot reach the server at {BASE}. Is it running?")
    sys.exit(1)

if len(start_students) != 5 or len(start_companies) != 3 or len(start_jobs) != 4 or len(start_apps) != 0:
    print("The data is not a clean start. Stop the server, delete students.json,")
    print("companies.json, jobs.json and applications.json, start the server again, then re-run.")
    sys.exit(1)

# Dummy valid student used for header / permission checks
DUMMY_STUDENT = {
    "roll_no": "2026TEST",
    "name": "Test Student",
    "email": "test@example.com",
    "branch": "CSE",
    "cgpa": 8.0,
}

print("\n--- 1. Health and browsing (no role needed) ---")
check("GET /health", get("/health"), 200, lambda d: d.get("status") == "ok")
check("GET /companies lists 3 starter companies", get("/companies"), 200, lambda d: len(d) == 3)
check("GET /jobs lists 4 starter jobs", get("/jobs"), 200, lambda d: len(d) == 4)
check("GET /jobs/1 shows calculated openings (3 remaining, 0 filled)", get("/jobs/1"), 200,
      lambda d: d.get("remaining_openings") == 3 and d.get("filled_openings") == 0)

print("\n--- 2. Roles, permissions, and header checks ---")
check("POST /students without X-Role gives 401", post("/students", DUMMY_STUDENT), 401)
check("POST /students with unknown role gives 401", post("/students", DUMMY_STUDENT, {"X-Role": "dean"}), 401)
check("POST /students by student gives 403", post("/students", DUMMY_STUDENT, {"X-Role": "student"}), 403)
check("POST /students by recruiter gives 403", post("/students", DUMMY_STUDENT, {"X-Role": "recruiter"}), 403)
check("POST /jobs by recruiter without X-Company-Id gives 401",
      post("/jobs", {"company_id": 1, "title": "SDE", "package": 1000000, "min_cgpa": 7.0, "allowed_branches": ["CSE"], "openings": 2, "deadline": "2027-01-01"}, {"X-Role": "recruiter"}), 401)
check("POST /jobs by recruiter with invalid X-Company-Id gives 401",
      post("/jobs", {"company_id": 1, "title": "SDE", "package": 1000000, "min_cgpa": 7.0, "allowed_branches": ["CSE"], "openings": 2, "deadline": "2027-01-01"}, {"X-Role": "recruiter", "X-Company-Id": "abc"}), 401)
check("POST /applications by student without X-Student-Id gives 401",
      post(f"/applications?today={SIM_TODAY}", {"job_id": 1, "student_id": 1}, {"X-Role": "student"}), 401)
check("POST /applications by student with invalid X-Student-Id gives 401",
      post(f"/applications?today={SIM_TODAY}", {"job_id": 1, "student_id": 1}, {"X-Role": "student", "X-Student-Id": "-5"}), 401)
check("Recruiter cannot post job for another company (gives 403)",
      post("/jobs", {"company_id": 2, "title": "SDE", "package": 1000000, "min_cgpa": 7.0, "allowed_branches": ["CSE"], "openings": 2, "deadline": "2027-01-01"}, REC1), 403)
check("Student 1 cannot view Student 2 details (gives 403)", get("/students/2", STU1), 403)
check("Student 1 cannot apply for Student 2 (gives 403)",
      post(f"/applications?today={SIM_TODAY}", {"job_id": 1, "student_id": 2}, STU1), 403)

print("\n--- 3. Companies (CRUD and delete rules) ---")
check("POST /companies duplicate name gives 409",
      post("/companies", {"name": "techcorp", "sector": "Software"}, OFF), 409)
check("POST /companies padded duplicate name gives 409",
      post("/companies", {"name": " TechCorp ", "sector": "Software"}, OFF), 409)
check("POST /companies empty name gives 422",
      post("/companies", {"name": "", "sector": "Software"}, OFF), 422)
check("POST /companies valid company gives 201",
      post("/companies", {"name": "InnoSoft", "sector": "Cloud"}, OFF), 201, lambda d: d.get("id") == 4)
check("DELETE /companies/1 with jobs gives 409 (R12 rule broken)", delete("/companies/1", OFF), 409)
check("DELETE /companies/999 not found gives 404", delete("/companies/999", OFF), 404)
check("DELETE /companies/4 without jobs gives 204 (R12 rule obeyed)", delete("/companies/4", OFF), 204)

print("\n--- 4. Students (CRUD, uniqueness, and filters) ---")
check("POST /students duplicate roll number gives 409",
      post("/students", {"roll_no": "2026CSE001", "name": "Dup", "email": "unique@ex.com", "branch": "CSE", "cgpa": 8.0}, OFF), 409)
check("POST /students case-insensitive duplicate roll number gives 409",
      post("/students", {"roll_no": "2026cse001", "name": "Dup", "email": "unique2@ex.com", "branch": "CSE", "cgpa": 8.0}, OFF), 409)
check("POST /students duplicate email (case-insensitive) gives 409",
      post("/students", {"roll_no": "2026NEW001", "name": "Dup", "email": "AARAV@EXAMPLE.COM", "branch": "CSE", "cgpa": 8.0}, OFF), 409)
check("POST /students whitespace-only name gives 422",
      post("/students", {"roll_no": "2026NEW004", "name": "   ", "email": "space@ex.com", "branch": "CSE", "cgpa": 8.0}, OFF), 422)
check("POST /students invalid email regex gives 422",
      post("/students", {"roll_no": "2026NEW002", "name": "Bad", "email": "bademailformat", "branch": "CSE", "cgpa": 8.0}, OFF), 422)
check("POST /students CGPA > 10.0 gives 422",
      post("/students", {"roll_no": "2026NEW003", "name": "High", "email": "high@ex.com", "branch": "CSE", "cgpa": 11.0}, OFF), 422)
check("POST /students valid student gives 201",
      post("/students", {"roll_no": "2026CSE006", "name": "Priya Nair", "email": "priya@example.com", "branch": "CSE", "cgpa": 8.8}, OFF), 201,
      lambda d: d.get("id") == 6)
check("GET /students lists 6 students for officer", get("/students", OFF), 200, lambda d: len(d) == 6)
check("GET /students?branch=CSE filters by branch", get("/students?branch=CSE", OFF), 200,
      lambda d: len(d) == 2 and all(s["branch"] == "CSE" for s in d))
check("GET /students?branch=UNKNOWN gives 422", get("/students?branch=UNKNOWN", OFF), 422)
check("GET /students/1 for officer gives 200", get("/students/1", OFF), 200)
check("GET /students/1 for own student gives 200", get("/students/1", STU1), 200)
check("GET /students/999 not found gives 404", get("/students/999", OFF), 404)
check("PATCH /students/1 with taken email gives 409", patch("/students/1", {"email": "diya@example.com"}, OFF), 409)
check("PATCH /students/1 update name gives 200", patch("/students/1", {"name": "Aarav Sharma Senior"}, OFF), 200,
      lambda d: d.get("name") == "Aarav Sharma Senior")

print("\n--- 5. Jobs (posting, filters, deadlines, and openings) ---")
check("POST /jobs non-existent company gives 404",
      post("/jobs", {"company_id": 999, "title": "Ghost", "package": 1000000, "min_cgpa": 7.0, "allowed_branches": ["CSE"], "openings": 2, "deadline": "2027-01-01"}, OFF), 404)
check("POST /jobs package <= 0 gives 422",
      post("/jobs", {"company_id": 1, "title": "Free", "package": 0, "min_cgpa": 7.0, "allowed_branches": ["CSE"], "openings": 2, "deadline": "2027-01-01"}, OFF), 422)
check("POST /jobs openings > 100 gives 422",
      post("/jobs", {"company_id": 1, "title": "Huge", "package": 1000000, "min_cgpa": 7.0, "allowed_branches": ["CSE"], "openings": 150, "deadline": "2027-01-01"}, OFF), 422)
check("POST /jobs by recruiter for own company gives 201",
      post("/jobs", {"company_id": 1, "title": "Frontend Eng", "package": 1500000, "min_cgpa": 7.5, "allowed_branches": ["CSE", "ECE"], "openings": 2, "deadline": "2027-05-01"}, REC1), 201,
      lambda d: d.get("id") == 5)
check("GET /jobs ?open_only=true hides expired jobs when simulated date passes deadline",
      get("/jobs?open_only=true&today=2027-01-01"), 200, lambda d: 1 not in [j["id"] for j in d])
check("GET /jobs ?today= bad format gives 422", get("/jobs?today=31-12-2026"), 422)
check("GET /jobs/999 not found gives 404", get("/jobs/999"), 404)
check("PATCH /jobs/1 by recruiter from another company gives 403", patch("/jobs/1", {"title": "Hack"}, REC2), 403)
check("PATCH /jobs/1 with empty allowed_branches gives 422", patch("/jobs/1", {"allowed_branches": []}, OFF), 422)
check("PATCH /jobs/5 manual status change to 'closed' gives 200", patch("/jobs/5", {"status": "closed"}, OFF), 200,
      lambda d: d.get("status") == "closed")
check("DELETE /jobs/999 not found gives 404", delete("/jobs/999", OFF), 404)
check("DELETE /jobs/5 without applications gives 204", delete("/jobs/5", OFF), 204)

print("\n--- 6. Applications (Rules R1 to R7) ---")
check("POST /applications non-existent job gives 404", post(f"/applications?today={SIM_TODAY}", {"job_id": 999, "student_id": 1}, STU1), 404)
check("POST /applications non-existent student gives 404", post(f"/applications?today={SIM_TODAY}", {"job_id": 1, "student_id": 999}, {"X-Role": "student", "X-Student-Id": "999"}), 404)

# Create a temporary closed job to verify R1
closed_job = post("/jobs", {"company_id": 1, "title": "Closed", "package": 1000000, "min_cgpa": 6.0, "allowed_branches": ["CSE"], "openings": 1, "deadline": "2027-01-01", "status": "closed"}, OFF).json()
check("POST /applications to closed job gives 409 (R1 rule)",
      post(f"/applications?today={SIM_TODAY}", {"job_id": closed_job["id"], "student_id": 1}, STU1), 409)

check("POST /applications after job deadline gives 409 (R2 rule)",
      post("/applications?today=2027-01-01", {"job_id": 1, "student_id": 1}, STU1), 409)
check("POST /applications with CGPA below minimum gives 409 (R4 rule)",
      post(f"/applications?today={SIM_TODAY}", {"job_id": 1, "student_id": 4}, STU4), 409)
check("POST /applications with disallowed branch gives 409 (R5 rule)",
      post(f"/applications?today={SIM_TODAY}", {"job_id": 1, "student_id": 3}, STU3), 409)
check("POST /applications valid application gives 201",
      post(f"/applications?today={SIM_TODAY}", {"job_id": 1, "student_id": 1}, STU1), 201,
      lambda d: d.get("status") == "applied" and d.get("package_offered") is None)
check("POST /applications duplicate application gives 409 (R6 rule)",
      post(f"/applications?today={SIM_TODAY}", {"job_id": 1, "student_id": 1}, STU1), 409)
check("DELETE /jobs/1 with existing applications gives 409 (R11 rule)", delete("/jobs/1", OFF), 409)

check("GET /students/1/applications for own student gives 200", get("/students/1/applications", STU1), 200, lambda d: len(d) == 1)
check("GET /students/1/applications for other student gives 403", get("/students/1/applications", STU2), 403)
check("GET /applications for recruiter of own company shows Job 1 app", get("/applications", REC1), 200, lambda d: len(d) >= 1)
check("GET /applications for recruiter of company 2 shows 0 apps", get("/applications", REC2), 200, lambda d: len(d) == 0)
check("GET /applications with invalid ?status= gives 422", get("/applications?status=pending", OFF), 422)

# Boundary test for MAX_ACTIVE_APPLICATIONS (R7)
print("Testing active applications limit (5 allowed, 6th rejected)...")
for i in range(1, 4):
    post("/jobs", {"company_id": 2, "title": f"ECE Job {i}", "package": 1100000, "min_cgpa": 7.0, "allowed_branches": ["ECE"], "openings": 2, "deadline": "2027-06-30"}, OFF)
ece_jobs = [j["id"] for j in get("/jobs").json() if "ECE" in j["allowed_branches"] and j["status"] == "open"]
succ = 0
for jid in ece_jobs[:5]:
    if post(f"/applications?today={SIM_TODAY}", {"job_id": jid, "student_id": 2}, STU2).status_code == 201:
        succ = succ + 1

j6 = post("/jobs", {"company_id": 2, "title": "ECE Extra Job 6", "package": 1150000, "min_cgpa": 7.0, "allowed_branches": ["ECE"], "openings": 2, "deadline": "2027-06-30"}, OFF).json()["id"]
r_6th = post(f"/applications?today={SIM_TODAY}", {"job_id": j6, "student_id": 2}, STU2)
check("Active applications limit: 5th works, 6th gives 409 (R7 rule)", r_6th, 409, lambda _: succ == 5)

print("\n--- 7. Application status moves (Rules R8 to R10) ---")
check("Student cannot set status to 'shortlisted' (gives 403)", patch(f"/applications/1/status?today={SIM_TODAY}", {"status": "shortlisted"}, STU1), 403)
check("Recruiter of company 2 cannot update company 1 app (gives 403)", patch(f"/applications/1/status?today={SIM_TODAY}", {"status": "shortlisted"}, REC2), 403)
check("Status change date earlier than application date gives 400", patch("/applications/1/status?today=2026-11-10", {"status": "shortlisted"}, OFF), 400)
check("Disallowed status transition (applied -> offered) gives 409 (R8 rule)", patch(f"/applications/1/status?today={SIM_TODAY}", {"status": "offered"}, OFF), 409)
check("Shortlisting application gives 200", patch(f"/applications/1/status?today={SIM_TODAY}", {"status": "shortlisted"}, OFF), 200, lambda d: d.get("status") == "shortlisted")
check("Offering job copies package (1800000) and gives 200 (R9 rule)", patch(f"/applications/1/status?today={SIM_TODAY}", {"status": "offered"}, OFF), 200,
      lambda d: d.get("status") == "offered" and d.get("package_offered") == 1800000)

# Job 2 openings exhaustion test (openings = 1)
print("Testing job openings limit (use Job 2 with openings = 1)...")
app6 = post(f"/applications?today={SIM_TODAY}", {"job_id": 2, "student_id": 6}, STU6).json()["id"]
patch(f"/applications/{app6}/status?today={SIM_TODAY}", {"status": "shortlisted"}, OFF)
patch(f"/applications/{app6}/status?today={SIM_TODAY}", {"status": "offered"}, OFF)
rem_j2 = get("/jobs/2").json()["remaining_openings"]

post("/students", {"roll_no": "2026CSE007", "name": "Manish Gupta", "email": "manish@example.com", "branch": "CSE", "cgpa": 9.0}, OFF)
app7 = post(f"/applications?today={SIM_TODAY}", {"job_id": 2, "student_id": 7}, STU7).json()["id"]
patch(f"/applications/{app7}/status?today={SIM_TODAY}", {"status": "shortlisted"}, OFF)
r_offer_blocked = patch(f"/applications/{app7}/status?today={SIM_TODAY}", {"status": "offered"}, OFF)
check("Exhausting openings (rem=0) blocks next offer with 409 (R9 rule)", r_offer_blocked, 409, lambda _: rem_j2 == 0)

# Acceptance cascade test (R10)
print("Testing acceptance cascade and double accept...")
r_acc = patch(f"/applications/1/status?today={SIM_TODAY}", {"status": "accepted"}, STU1)
check("Student accepting offer sets placed=True (R10 rule)", r_acc, 200,
      lambda _: get("/students/1", OFF).json().get("placed") is True)
check("Accepting twice gives 409 (R8 rule, no second cascade)", patch(f"/applications/1/status?today={SIM_TODAY}", {"status": "accepted"}, STU1), 409)
check("Placed student cannot apply to new jobs (gives 409, R3 rule)", post(f"/applications?today={SIM_TODAY}", {"job_id": 3, "student_id": 1}, STU1), 409)

print("\n--- 8. Overall placement statistics report ---")
check("GET /stats by student gives 403", get("/stats", STU1), 403)
check("GET /stats by officer gives 200 with complete report", get("/stats", OFF), 200,
      lambda d: d["total_students"] >= 5 and d["placed_students"] >= 1 and d["average_package"] >= 1800000 and d["top_company_by_offers"] == "TechCorp")

print("\n" + "=" * 60)
print(f"RESULTS: {passed} PASSED, {failed} FAILED")
print("=" * 60)
print("\n[REMINDER] Hand tests to perform manually:")
print("1. RESTART TEST: Stop server, do NOT delete JSON files, restart server, verify data persists.")
print("2. DAMAGED-FILE TEST: Corrupt one JSON file (e.g., write 'corrupt' to students.json),")
print("   restart server, and confirm safe loading warns and rebuilds from starter data.")
print("=" * 60)

if failed > 0:
    sys.exit(1)
