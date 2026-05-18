# Design Document — Leave Management System

**Author:** [Your Name]
**Date:** 2026-05-18

## 1. API Design

I noticed that most of the provided scaffold already followed REST principles, and normally we would do REST for everything. So, I converted the status update actions that didn't follow REST into a proper RESTful sub-resource (`PUT /leave-requests/{id}/status`). This is much cleaner and more predictable than having multiple RPC-style endpoints like `/approve`, `/reject`, or `/cancel`.

Here are the main endpoints I worked on:

- `POST /leave-requests`
  - Body: `LeaveRequestCreate` (type, start/end dates, reason)
  - Returns: Created leave request (status 201)
- `PUT /leave-requests/{id}/status`
  - Body: `LeaveRequestStatusUpdate` (status: approved, rejected, cancelled)
  - Returns: Updated request
  - *Note*: I built a custom Redis lock decorator here to prevent concurrent modifications safely.
- `GET /leave-requests`
  - Query params: employee_id, status, type, dates, pagination
  - Returns: Paginated list of requests.
- `GET /employees/{id}/leave-balances`
  - Returns: List of balances for the given year.

## 2. Data Model

The database uses SQLAlchemy with three main tables:
- `Employee`: Basic details and a self-referencing foreign key for managers.
- `LeaveRequest`: Tracks the actual request constraints. Uses enums for type and status.
- `LeaveBalance`: Tracks yearly allocations. I used `Float` for `total_days` and `used_days` to future-proof the design, even though for this asignment we don't support half-day leaves just yet.

## 3. Edge Cases Identified

I tried to cover as many edge cases as possible directly in the service layer:
- **Overlapping leaves:** Checked if a user already has a pending/approved leave in the requested date range so they can't double-book.
- **Self-approval:** A manager cannot approve their own leave. The `approver_id` must match `leave.employee.manager_id`.
- **Holidays & Weekends:** I integrated the `holidays` Python package to dynamically skip Malaysian public holidays and weekends so users aren't charged for off-days.
- **Idempotency:** If an aprove or cancel request is sent twice by accident, it fails fast on the second try by checking if the status was already changed.

## 4. Tradeoffs and Decisions

- **Redis Locking vs Database Locking:** Instead of locking rows in SQLite (which can be clunky with concurrent threads), I built a custom `@lock_request` FastAPI decorator. It uses Redis to lock the specific HTTP route and method. This prevents race conditions if two managers try to process the same request at the exact same time.
- **Sync over Async:** I stuck to standard sync SQLAlchemy sessions since the boilerplate was already set up that way. Async DB drivers would be better for high load, but unnecesary for this scale.
- **Half-day leaves:** I decided to skip implementing half-day leaves for now to keep the date logic simple. However, the database columns are already floats so adding an AM/PM flag later will be a very easy migration.

## 5. What I Would Do With More Time

If I had another week on this, I'd definitely add full support for half-day leaves (adding an AM/PM column to the request table and updating the overlap query). I'd also swap out the defualt `X-Current-User` header for a proper JWT authentication middleware. Finally, I'd migrate the database to PostgreSQL since SQLite doesn't handle concurrent writes very well in a real production environment.

## 6. Running the Project

### Install
```bash
make install
```
or
```bash
docker compose up -d 
```

### Run
```bash
make run
```
or
```bash
docker compose up -d
```

### Test
```bash
make test
```
or
```bash
./test.sh
```


### Infrastructure & Docker Decisions

To make the concurrency lock actually work in a real-world scalable environment, I updated the provided `docker-compose.yml` to include a `redis` container. 

**Tradeoff:** I could have used Python's built-in `asyncio.Lock` or standard threading locks in memory, which would require zero infrastructure changes. However, if Kakitangan scales this API horizontally across multiple Docker containers or Kubernetes pods, in-memory locks completely fail. 

By taking the time to wire up Redis via Docker, the locking mechanism is now truly distributed. No matter how many API instances are spun up behind a load balancer, they all share the same Redis instance, guaranteeing that two managers hitting different API containers still cannot double-approve the same leave request.