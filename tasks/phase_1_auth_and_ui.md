# Phase 1: Authentication, User Portal & Speech UI Enhancements

This task document details the specifications, backend endpoints, and frontend components required to complete Phase 1 of the EchoStack roadmap.

---

## 1. Objectives
- Implement user registration and login endpoints supporting Full Name, Username, Email, and Password hashing.
- Support login via either Username or Email.
- Build a frontend Login & Registration modal/page.
- Implement live audio text transcript logging in the React UI.

---

## 2. Technical Tasks

### 2.1 Backend User & Authentication API ([backend/api/users.py](file:///c:/git-hub/EchoStack/backend/api/users.py))
- [x] Support `full_name` and `username` schema attributes in the database.
- [x] Implement `POST /api/users/register`:
  - **Inputs:** `full_name`, `username`, `email`, `password`.
  - **Username Rules:** All lowercase, no spaces allowed.
  - **Full Name Rules:** Only letters (and spaces) allowed; no symbols or special characters.
  - **Uniqueness Check:** If either `email` or `username` already exists in the DB, return error `"user already exists"`.
  - **Default Role:** New users created are assigned the `standard` role by default (Superadmin can upgrade users to upper roles).
  - Password hashed using `bcrypt`/`passlib`.
  - Return JWT access token and user profile details.
- [x] Implement `POST /api/users/login`:
  - **Inputs:** Identifier (`username` OR `email`) and `password`.
  - Allow login with either `username` or `email`.
  - Verify password hash and generate JWT access token with user claims.
  - Cache permissions in Redis (`user_permissions:{user_id}`).

### 2.2 Frontend Authentication Portal ([frontend/src/components/AuthModal.jsx](file:///c:/git-hub/EchoStack/frontend/src/components/AuthModal.jsx))
- [x] Build a sleek glassmorphic Auth Modal:
  - Tab toggle between **Login** and **Register**.
  - **Register Form:** Full Name, Username, Email, Password.
  - **Login Form:** Username or Email, Password.
  - Form validation matching backend rules (lowercase & no spaces for username, letters only for full name).
  - Persist JWT token in `localStorage`.
  - Display user avatar, full name/username, and logout button in the top navigation bar.

### 2.3 Live Speech Transcript UI Panel ([frontend/src/App.jsx](file:///c:/git-hub/EchoStack/frontend/src/App.jsx))
- [x] Render live transcript bubbles beneath the Speech Control Orb.
- [x] Display real-time user speech input and AI text output as audio streams.
- [x] Add copy transcript and clear transcript buttons.

---

## 3. Verification Criteria
- [x] User can register a new account with Full Name, Username, Email, and Password.
- [x] Username enforces lowercase and no spaces; Full Name permits only letters.
- [x] Duplicate email or username returns `"user already exists"` error.
- [x] User can log in using either Username or Email with their password.
- [x] New users receive the `standard` role by default; Superadmin can upgrade user roles.
- [x] Frontend displays user identity dynamically based on logged-in user.
- [x] Live Speech-to-Speech session displays text transcript bubbles during voice interaction.
