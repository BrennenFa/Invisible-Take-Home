# Tools Used:
1. claude code
2. chatgpt/gemini - web


# Example Prompts/Iterations:
1. Basic commands - 
2. Validation of Findings --> Where are id's managed? Are they incremental? Change that to uuid
3. ❯ so im using a sqlite db.... is there anything u can do to help manage concurrency with it?   ---> validation of problems
4. so if i have a .wal.... and its used locally... how should i set it to backup? i currently have 500 pages, but should i have it be intermittent?
5. Scalability & Idempotency Testing Discussion:
   - "I want to test scalability and idempotency.... should these be unit tests, integration tests, or both"
   - "ok.... lets do both then.... should i add it to the already implemented (eg: accounts, auth, etc) or make a new test called like system tests, concurrency tests, latency tests, etc"
   - "ok... can implement a few?"
   - Result: Created dedicated `test_concurrency.py` with parallel transfer tests, race condition handling, and idempotency validation

6. Modular Architecture Iteration:
   - Started with monolithic transfer logic → AI suggested breaking into modular components
   - Implemented idempotency table for transfers + transactions
   - Fixed race conditions identified through concurrent test execution

7. Account Number Implementation:
   - "implementing account numbers and more completed tests"
   - AI helped design account number generation and validation logic

8. Meta Prompt - Documentation:
   - "add to my usage-report.md (dont remove anything) some things for this, especially if there are any cool prompts/iterations i had with u??"
   - AI read existing file, fixed merge conflict, and added session summary

# Challenges solved by AI
1. **Concurrency & Race Conditions**: AI helped identify and fix race conditions in transfer logic when running parallel tests
2. **Idempotency Implementation**: Designed idempotency table structure for ensuring duplicate requests don't cause duplicate transactions
3. **SQLite WAL Configuration**: AI provided guidance on WAL mode backup strategies (checkpoint intervals vs page counts)
4. **Test Organization**: AI recommended separating concurrency/system tests from unit tests for clarity
5. **UUID Migration**: Changed from incremental IDs to UUIDs for better security and distributed system compatibility

# Areas where human intervention was needed
1. os.getenv() --> leaked db location (security review)
2. Merge conflict resolution awareness (human flagged the conflict markers)
3. Final validation of test results and edge cases
4. Decision-making on architectural tradeoffs (e.g., choosing between test organization strategies)
