# ARCHITECTURE DEBATE & PLAN

## Architect Alpha (Conservative, Robust, Secure)

**Topic**: Should the login endpoint accept a generic `identifier` that checks the database for *either* `username` OR `operator_code`?

### Observation
The proposition to accept a single generic `identifier` field and magically check it against both `username` and `operator_code` is fundamentally flawed from a security and system stability perspective. Implicit fallbacks introduce hidden complexities.

### Risks of a Generic "Identifier"
1. **Namespace Collision**: A `TECH_ADMIN` might have a `username` of "12345", which inadvertently perfectly matches an operator's `operator_code`. While password hashes differ, handling overlaps requires confusing edge cases. What if two users exist—one with `username: "1234"` and another with `operator_code: "1234"`? The system might try to validate the password against the wrong user record.
2. **Security & Obfuscation**: The system should strictly enforce "What you are" and "How you authenticate." Operators and Admins serve drastically different functions (`Role.OPERATOR` vs `Role.TECH_ADMIN`). Intertwining their login entry points into a "try this, then try that" query expands the surface area for timing attacks and credential stuffing.
3. **Database Performance**: Querying `WHERE username = $1 OR operator_code = $1` negates simple single-index lookups (unless specifically indexed, but it's still two separate semantic checks). Doing it sequentially (`get_by_username` -> if null -> `get_by_operator_code`) is two round trips. 

### Alpha's Proposed Solution
I strongly advocate for **Explicit Intention over Implicit Magic**.

**Option A (Strictly Typed Logic - Preferred):**
Maintain standard OAuth2 using `OAuth2PasswordRequestForm` to preserve OpenAPI/Swagger compatibility, but enforce strict format validation on the backend.
- Ensure `username` formats and `operator_code` formats are strictly mutually exclusive via system invariants. For example, `operator_code` must be purely numeric, while `username` must be alphanumeric (but not solely numeric).
- At the domain/application level (`LoginHandler`), conditionally route the check:
  ```python
  if is_valid_operator_code_format(identifier):
      user = await uow.users.get_by_operator_code(identifier)
  else:
      user = await uow.users.get_by_username(identifier)
  ```
This guarantees an `operator_code` will never overlap with a `username` query, maintaining zero ambiguity.

**Option B (Explicit Payload):**
Modify the API request schema to explicitly state the type of credential being used:
`{ "login_type": "username|operator_code", "identifier": "...", "password": "..." }`
This ensures enterprise-grade strictness, though it departs from the standard OAuth2 `username/password` form.

I expect Architect Beta to propose the "easiest" and "most generic" abstraction where we just `OR` the database fields. This is reckless and I preemptively reject it unless strict mutually exclusive format constraints are guaranteed.
