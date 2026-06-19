# FAE Phase 4: Independent External Audit - Strict Guidelines

**To:** Development & QA Teams (Architects, Coders, Testers)
**From:** Independent External Auditor
**Date:** 2026-06-18
**Status:** Audit Complete (with critical interventions required)

## 1. Executive Summary

This codebase is presented as following Hexagonal Architecture and Domain-Driven Design (DDD). However, the implementation revealed **sloppiness, architectural violations, and poor configuration management**. While the code technically functioned and passed its tests, "working" is not the same as "correct." 

I have stepped in and directly modified your code to fix these glaring flaws. Do not revert them. Read the following strict guidelines and ensure you never repeat these mistakes.

## 2. Critical Violations Found & Fixed

### 2.1 Hexagonal Architecture Violation (Cross-Layer Contamination)
**What you did wrong:** Your Application Layer (`LoginHandler`) imported `HTTPException` and `status` directly from `fastapi` and raised HTTP exceptions.
**Why it is unacceptable:** The Application Layer must remain completely agnostic to the Presentation Layer (HTTP/FastAPI). Leaking web framework exceptions into your domain commands entirely defeats the purpose of Hexagonal Architecture.
**What I fixed:** 
- I removed all FastAPI imports from `LoginHandler`.
- I created a new `AuthenticationError` inheriting from `DomainError` in `src/domain/exceptions.py`.
- I updated `src/presentation/api/exceptions.py` to catch `AuthenticationError` and return a `401 Unauthorized` JSONResponse with the `WWW-Authenticate` header.

### 2.2 Domain Purity & Meaningful Naming
**What you did wrong:** The `LoginHandler` accepted a parameter named `username: str`. However, when `login_type="operator_code"` was used, this `username` parameter actually contained the operator code.
**Why it is unacceptable:** You let the OAuth2 specification (which requires the field to be named `username`) pollute your application's domain logic. `username` has a specific semantic meaning in your system (a string for tech admins). An operator code is a completely different identifier.
**What I fixed:** I renamed the `LoginHandler.execute` parameter from `username` to `identifier`. The API Router now extracts the `username` from the OAuth2 form data and passes it to the handler as the `identifier`.

### 2.3 Static Analysis & Configuration Hygiene
**What you did wrong:** 
- You left 24 Ruff errors in the test suite (`conftest.py` line length violations, `test_handlers.py` trailing whitespace, `S106` hardcoded passwords, `PLR2004` magic values).
- You haphazardly slapped `# noqa: S106` on random lines instead of configuring your tools correctly.
**Why it is unacceptable:** Tests are code. Sloppy tests lead to sloppy production code. Static analysis tools exist to be configured properly, not ignored piecemeal or bypassed because you are lazy.
**What I fixed:** 
- I added a `[tool.ruff.lint.per-file-ignores]` section in `pyproject.toml` to globally ignore `S106` and `PLR2004` *only* inside the `src/tests/*` directory. 
- I removed your useless `noqa` comments.
- I fixed all line length violations and trailing whitespaces. `ruff check src` and `mypy src --strict` now pass perfectly.

## 3. STRICTLY FORBIDDEN PRACTICES (Never Do These Again)

1. **STRICTLY FORBIDDEN:** Importing ANY web framework (FastAPI, Starlette) component into `domain` or `application` directories.
2. **STRICTLY FORBIDDEN:** Naming variables incorrectly to appease an external API format (e.g. calling an Operator Code a "username" inside a Command Handler).
3. **STRICTLY FORBIDDEN:** Disabling linters inline (`# noqa`) for project-wide test patterns. If a rule doesn't apply to tests (like hardcoded passwords for mock users), configure it in `pyproject.toml` using `per-file-ignores`.
4. **STRICTLY FORBIDDEN:** Committing code with trailing whitespace or line length > 120 chars.

If these guidelines are not followed in the next phase, the build will be forcibly failed.
