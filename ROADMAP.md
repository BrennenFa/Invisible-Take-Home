# Future Considerations & Roadmap

This document outlines planned enhancements and future considerations for the Banking REST API.

## Improvements

### 1. Redis Cache for Idempotency Keys

**Current State**: Idempotency keys are stored in SQLite (`idempotency_keys` table). However, this means automatic key management has more overhead required, such as a programmed key pruner or similar mechanism. Additionally, SQLite isn't the fastest database for this application.

**Proposed Change**: To fix this, I would move idempotency storage to Redis for improved performance and automatic expiration. This would allow for faster lookups, which is important when validating transactions. Additionally, built-in TTL (time-to-live) means key expiration would be automatic.


### 2. Enhanced Backup System

**Current State**: Currently, there is a backup implementation with SQLite + WAL file copying. However, this is not called automatically.

**Proposed Enhancements**: Due to the importance of bank data, scheduling automated backups would help eliminate much of the risk that comes with storing large datasets, especially with the WAL checkpoint implementation.




### 43 CORS Configuration

**Current State**: No frontend currently exists. As a result, I did not implement CORS, which would limit the web addresses that are able to access the API.

**Proposed Change**: Implement CORS middleware for a more secure API:
- Restrict origins to verified platforms only
- Configure allowed methods (GET, POST, PATCH, DELETE)
- Set appropriate headers for credentials handling
- No wildcard origins in production


### 4. Security Headers

**Current State**: No security headers are currently implemented. The API responses do not include headers that protect against common web vulnerabilities.

**Proposed Change**: Add security headers middleware to include:
```
X-Content-Type-Options: nosniff          # Prevent MIME sniffing
X-Frame-Options: DENY                     # Prevent clickjacking
X-XSS-Protection: 1; mode=block          # Enable XSS filtering
Strict-Transport-Security: max-age=31536000; includeSubDomains  # Force HTTPS
Content-Security-Policy: default-src 'self'  # Restrict content sources
Referrer-Policy: strict-origin-when-cross-origin  # Control referrer info
```


### 6. Two-Factor Authentication (2FA)

**Current State**: Only single-factor authentication (password) is implemented.

**Proposed Change**: Adding 2FA would help improve the security and login system, ensuring only the people intended could access their account and account data.


