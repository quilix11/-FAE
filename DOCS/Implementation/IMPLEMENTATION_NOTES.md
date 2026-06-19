# IMPLEMENTATION NOTES

## Phase 2: Explicit Operator vs Admin Authentication

### Backend Changes

1.  **Repository Layer**: Added `get_by_operator_code` method to `UserRepository` and implemented it in `SQLAlchemyUserRepository`. This avoids the risky single-query "OR" approach and correctly handles operator code authentication independently.
2.  **Login Handler (`src/application/commands/login_handler.py`)**: Modified `execute` to accept a `login_type` parameter (defaulting to `"username"`). It now conditionally calls either `get_by_operator_code(username)` or `get_by_username(username)` based on `login_type`.
3.  **API Router (`src/presentation/api/router.py`)**: Updated the `/auth/login` endpoint to accept an additional `login_type: str = Form("username")`. This gracefully supports explicitly defining the authentication type while preserving the use of `OAuth2PasswordRequestForm` properties for standard compatibility where appropriate.

### Frontend Changes

1.  **Login Component (`frontend/login/app.js`)**: Updated the base `login(username, password, loginType)` function to append the `login_type` to the form payload.
2.  **Admin Login (`goToAdmin`)**: Now explicitly calls `login(user, pass, "username")`.
3.  **Operator Login (`goToOperator`)**: Now explicitly calls `login(user, pass, "operator_code")`.

### Testing

-   Refactored `test_handlers.py` to restore mock-related and entity-related imports previously omitted.
-   Added test cases (`test_login_handler_success_admin`, `test_login_handler_success_operator`, `test_login_handler_invalid_password`, `test_login_handler_user_not_found`) to explicitly test that `LoginHandler` triggers the correct underlying database method (`get_by_username` vs `get_by_operator_code`) and correctly handles invalid cases. All changes have successfully passed the unit tests.
