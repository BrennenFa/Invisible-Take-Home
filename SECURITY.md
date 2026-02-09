# Security Considerations

This document outlines the security measures implemented in the Banking REST API and recommendations for production deployment.


### JWT Token Authentication
- **Algorithm**: HS256 (HMAC-SHA256)
- **Expiration**: 30 minutes (configurable)
- **Storage**: Tokens should be stored securely by clients (not in localStorage for web apps)
- **Validation**: Every protected endpoint validates token signature and expiration

### Password Security
- **Hashing**: bcrypt with automatic salting
- **Requirements**:
  - Minimum 8 characters
  - At least one uppercase letter
  - At least one lowercase letter
  - At least one digit
- **Never stored in plaintext**

### Rate Limiting
Rate limiting was implemented using SlowAPI to prevent brute force and DDoS attacks. API requests can only be called by a client a limited number of times within a given time window. When the limit is exceeded, a `429 Too Many Requests` response is returned.

### Authorization & Ownership Checks
All endpoints verify that the authenticated user owns the resource they're trying to access:
- Users can only view/modify their own accounts
- Users can only initiate transfers from accounts they own
- Users can only view transactions for their own accounts
- Users can only manage cards linked to their own accounts
- Transfers TO other users' accounts are permitted (required for payments)

### Account & Card Status Validation
Operations are blocked based on resource status:
- **Frozen accounts**: Cannot send transfers, make withdrawals, or process card payments
- **Closed accounts**: All operations blocked
- **Frozen cards**: Card payments rejected
- **Cancelled cards**: Card payments permanently rejected

### Sensitive Data Storage
I attempted to make data storage secure and compliant with current regulations. A few examples are below:
- **Account Numbers**: Encrypted using AES (Fernet) before storage
- **Card Numbers**: Generated securely, masked in API responses (`****-****-****-1234`)
- **CVV**: Never stored - generated deterministically using HMAC-SHA256 when needed

### Soft Deletes
Bank account data is important to retain, as compliance regulations require banks to hold onto their records for several years. Thus, I ensured user accounts are soft-deleted (marked as deleted, not removed). Additionally, email data is anonymized on deletion to comply with data protection requirements.


### Idempotency Protection
All financial operations require an `Idempotency-Key` header. This helps the system manage whether processes are still occurring or need to run again, preventing duplicate transactions from network retries. When a process runs, it has a corresponding idempotency key. All idempotency keys are stored and checked before processing. If a key matches, the cached response is returned without re-executing the operation.


### Concurrent Transaction Handling
Transfers involve updating two account balances atomically. Without proper concurrency control, race conditions could lead to double-spending, deadlock errors, or inconsistent balances.

For example, if a user with a $100 balance is making two simultaneous $75 transfers, the following could occur:

```
Time    Request 1                    Request 2
────────────────────────────────────────────────────────
T1      Read balance: $100           Read balance: $100
T2      Check: $100 >= $75 ✓         Check: $100 >= $75 ✓
T3      Deduct: $100 - $75 = $25     Deduct: $100 - $75 = $25
T4      Write balance: $25           Write balance: $25
────────────────────────────────────────────────────────
Result: $150 transferred from $100 account (DOUBLE SPEND!)
```

Both requests read the same initial balance before either writes, allowing both to pass validation. To fix this, I implemented row-level locking in all API calls.


### Transfer Deadlock Prevention
Much like the issue above, transfers could lead to deadlocks. If two people transfer money to each other simultaneously, row-level locks could block on the rows they both need. To fix this, lock IDs are sorted, ensuring that both transactions acquire locks in the same order. This eliminates the possibility of deadlock.


### Atomic Commits
All writes are, where possible, committed in a single `db.commit()`. Any failure triggers a full rollback. This ensures data consistency and helps eliminate partial state from failed operations.

### Idempotency Conflict Handling
When a duplicate request arrives while the original is still processing, the system polls for the original's result (up to 5 seconds) and returns the cached response. This ensures that duplicate requests don't return an error when the initial process is simply still running.

### Balance Validation
Balance checks occur **after** acquiring row-level locks, not before. This is critical because:
- Reading balance without a lock could return stale data
- Another transaction could modify the balance between read and write
- Validating within the lock window guarantees accuracy


### Pydantic Schema Validation
All inputs are validated before processing. This helps eliminate injection attacks, malformed data, and invalid business logic:

| Field | Validation |
|-------|------------|
| Email | RFC 5322 compliant format |
| Password | Length, complexity requirements |
| Amount | Positive, max 2 decimal places, within limits |
| Account Type | Enum (CHECKING, SAVINGS) |
| Card Type | Enum (DEBIT, CREDIT) |
| PIN | Exactly 4 digits, numeric only |
| UUID | Valid UUID format |
| Routing Number | Exactly 9 digits |
| Account Number | 6-17 digits |

### Amount Limits
| Operation | Maximum |
|-----------|---------|
| Transfer | $1,000,000 |
| Deposit | $100,000 |
| Withdrawal | $50,000 |
| Card Payment | $10,000 |
| Card Spending Limit | $50,000 |


### SQLite Configuration
WAL (Write-Ahead Logging) mode is implemented for better concurrency and crash recovery. This ensures that writes are produced in an adjacent file, allowing reads to occur simultaneously without blocking. This helps prevent timeout lock failures under concurrent load.


### Error Handling
Error responses are designed to prevent information leakage: Error responses return user-friendly messages without exposing internal details (e.g., "Transfer failed" instead of raw exception strings). Full error details including stack traces are logged server-side for debugging.