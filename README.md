# Banking REST API

## Tech Stack

- **Framework**: FastAPI (Python 3.12)
- **Database**: SQLite with WAL mode for concurrency
- **Authentication**: JWT (JSON Web Tokens)
- **Validation**: Pydantic v2
- **Testing**: pytest

## Features
- User authentication (signup, login, JWT tokens)
- Multiple account types (Checking, Savings)
- Money transfers with idempotency protection
- Transaction history with filtering
- Card management (Debit/Credit)
- Statement generation (JSON, CSV, PDF)
- Rate limiting and security headers
- Concurrent transaction handling

## Quick Start

### Prerequisites

- Python 3.12+
- pip or conda

### Installation

```bash
# Clone the repository
git clone <repository-url>

# Create virtual environment
python -m venv venv
# Mac/Linux:
source venv/bin/activate  
# Windows: 
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment file and configure
cp .env.example .env
```

### Environment Configuration

After copying `.env.example` to `.env`, update the following values:

| Variable | Description | How to Generate |
|----------|-------------|-----------------|
| `JWT_SECRET` | Secret key for signing JWT tokens | `openssl rand -hex 32` |
| `CVV_SECRET` | Secret for CVV validation | `openssl rand -hex 32` |
| `ACCOUNT_NUMBER_SECRET` | 32-byte key for account number encryption | `python -c "import secrets, base64; print(base64.b64encode(secrets.token_bytes(32)).decode())"` |
| `BANK_ROUTING_NUMBER` | Your bank's routing number | Use your assigned routing number |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | JWT token lifetime | Default: `30` (adjust as needed) |

**Quick Setup (Development):**


```bash
# Run the server
uvicorn app.main:app --reload
```

The API will be available at `http://127.0.0.1:8000`

### Running Tests

```bash
source venv/bin/activate
pytest tests/ -v
```

## API Documentation

Once running, visit:
- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`

## API Endpoints

### Authentication

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auth/signup` | Register a new user |
| POST | `/auth/login` | Login and receive JWT token |
| GET | `/auth/me` | Get current user profile |
| PATCH | `/auth/password` | Change password |
| PATCH | `/auth/email` | Change email |
| DELETE | `/auth/account` | Delete account (soft delete) |

### Accounts

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/accounts` | Create new account |
| GET | `/accounts` | List all user accounts |
| GET | `/accounts/{id}` | Get account details |
| GET | `/accounts/{id}/transactions` | Get account transactions |
| PATCH | `/accounts/{id}/freeze` | Freeze account |
| PATCH | `/accounts/{id}/unfreeze` | Unfreeze account |
| PATCH | `/accounts/{id}/close` | Close account |

### Transfers

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/transfers` | Create transfer (by account ID) |
| POST | `/transfers/account` | Create transfer (by account number) |
| GET | `/transfers` | List all transfers |
| GET | `/transfers/{id}` | Get transfer details |

### Transactions

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/transactions/deposit` | Deposit funds |
| POST | `/transactions/withdrawal` | Withdraw funds |
| POST | `/transactions/card-payment` | Make card payment |
| GET | `/transactions` | List transactions (with filters) |

### Cards

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/cards` | Create new card |
| GET | `/cards` | List all cards |
| GET | `/cards/{id}` | Get card details |
| PATCH | `/cards/{id}/freeze` | Freeze card |
| PATCH | `/cards/{id}/unfreeze` | Unfreeze card |
| DELETE | `/cards/{id}` | Cancel card |

### Statements

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/statements/account/{id}` | Generate statement (JSON/CSV/PDF) |

## Example Usage

This walkthrough demonstrates a complete transfer workflow between two users.

### Step 1: Register User A (Sender)

```bash
curl -X POST http://127.0.0.1:8000/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"email": "alice@example.com", "password": "SecurePass123"}'
```

Response:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer"
}
```

### Step 2: Register User B (Recipient)

```bash
curl -X POST http://127.0.0.1:8000/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"email": "bob@example.com", "password": "SecurePass456"}'
```

### Step 3: User B Creates an Account

User B creates an account and receives their account number (only shown at creation):

```bash
curl -X POST http://127.0.0.1:8000/accounts \
  -H "Authorization: Bearer <user-b-token>" \
  -H "Content-Type: application/json" \
  -d '{"type": "CHECKING"}'
```

Response:
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "user_id": "user-b-uuid",
  "type": "CHECKING",
  "balance": 0.0,
  "status": "ACTIVE",
  "created_at": "2024-01-15T10:00:00Z",
  "routing_number": "123456789",
  "account_number": "9876543210",
  "account_number_masked": "******3210"
}
```

> **Note:** Save the `account_number` and `routing_number` - these are needed to receive transfers.

### Step 4: User A Creates an Account

```bash
curl -X POST http://127.0.0.1:8000/accounts \
  -H "Authorization: Bearer <user-a-token>" \
  -H "Content-Type: application/json" \
  -d '{"type": "CHECKING"}'
```

### Step 5: User A Deposits Funds

```bash
curl -X POST http://127.0.0.1:8000/transactions/deposit \
  -H "Authorization: Bearer <user-a-token>" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: deposit-001" \
  -d '{"account_id": "<user-a-account-uuid>", "amount": 1000.00}'
```

### Step 6: User A Transfers to User B

Using User B's account number and routing number from Step 3:

```bash
curl -X POST http://127.0.0.1:8000/transfers/account \
  -H "Authorization: Bearer <user-a-token>" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: transfer-001" \
  -d '{
    "source_account_id": "<user-a-account-uuid>",
    "destination_account_number": "9876543210",
    "destination_routing_number": "123456789",
    "amount": 250.00,
    "description": "Rent payment"
  }'
```

Response:
```json
{
  "id": "transfer-uuid",
  "source_account_id": "<user-a-account-uuid>",
  "destination_account_id": "<user-b-account-uuid>",
  "amount": 250.00,
  "description": "Rent payment",
  "created_at": "2024-01-15T10:30:00Z",
  "source_transaction_id": "debit-txn-uuid",
  "destination_transaction_id": "credit-txn-uuid"
}
```

## Authentication

All protected endpoints require a JWT token in the Authorization header:

```
Authorization: Bearer <your-token>
```

Tokens expire after 30 minutes (configurable in `.env`).

## Idempotency

Financial operations (transfers, deposits, withdrawals) require an `Idempotency-Key` header to prevent duplicate transactions:

```
Idempotency-Key: <unique-uuid>
```

Replaying the same request with the same key returns the cached response.


## Project Structure

```
Invisible/
├── app/
│   ├── main.py              # FastAPI entry point
│   ├── database.py          # Database configuration
│   ├── models.py            # SQLAlchemy models
│   ├── schemas.py           # Pydantic validation
│   ├── security.py          # Auth utilities
│   └── routes/              # API endpoints
├── tests/
│   ├── unit_tests/          # Business logic tests
│   └── integration_tests/   # API endpoint tests
├── SECURITY.md              # Security documentation
├── AI_USAGE.md              # AI development report
├── ROADMAP.md               # Future considerations
└── requirements.txt
```

## Test Client (Bonus)

A Python test client is included that demonstrates the complete transfer workflow:

```bash
# Make sure the server is running first
uvicorn app.main:app --reload

# In another terminal, run the test client
python test_client.py
```

The client demonstrates:
1. User registration (two users)
2. Account creation
3. Depositing funds
4. Transferring money between users via account number
5. Checking balances
6. Transaction history
7. Statement generation

## Documentation

- [Security Considerations](SECURITY.md)
- [Future Roadmap](ROADMAP.md)
- [AI Usage Report](AI_USAGE.md)
