# Phase 1: Authentication, User Portal & Speech UI Enhancements

This task document details the specifications, backend endpoints, and frontend components required to complete Phase 1 of the EchoStack roadmap.

---

## 1. Objectives
- Implement complete user registration and login endpoints with password hashing.
- Build a frontend Login & Registration modal/page with role selection.
- Implement live audio text transcript logging in the React UI.
- Add dynamic Gemini voice selection (Puck, Charon, Aoede, Fenrir, Kore).

---

## 2. Technical Tasks

### 2.1 Backend Authentication Service ([backend/auth.py](file:///c:/git-hub/EchoStack/backend/auth.py))
- [ ] Add password hashing and verification using `passlib[bcrypt]`.
- [ ] Create `POST /auth/register` endpoint:
  - Input: `email`, `password`, `role_id`.
  - Validate email uniqueness, hash password, create user in `users` table.
  - Return JWT access token and user profile details.
- [ ] Create `POST /auth/login` endpoint:
  - Input: `email`, `password`.
  - Verify password hash, generate JWT access token with user claims.
  - Cache permissions in Redis (`user_permissions:{user_id}`).

### 2.2 Frontend Authentication Portal ([frontend/src/components/AuthModal.jsx](file:///c:/git-hub/EchoStack/frontend/src/components/AuthModal.jsx))
- [ ] Build a sleek glassmorphic Auth Modal:
  - Tab toggle between **Login** and **Register**.
  - Form fields: Email, Password, Role Selector (`Standard`, `Premium`, `Admin`).
  - Persist JWT token in `localStorage`.
  - User avatar and logout button in the top navigation bar.

### 2.3 Live Speech Transcript UI Panel ([frontend/src/App.jsx](file:///c:/git-hub/EchoStack/frontend/src/App.jsx))
- [ ] Render live transcript bubbles beneath the Speech Control Orb.
- [ ] Display real-time user speech input and AI text output as audio streams.
- [ ] Add copy transcript and clear transcript buttons.

### 2.4 Voice & Modality Selector
- [ ] Add backend endpoint / query param for selecting Gemini Live voice.
- [ ] Add voice selection dropdown in UI (*Puck*, *Charon*, *Aoede*, *Fenrir*, *Kore*).

---

## 3. Verification Criteria
- [ ] User can register a new account, log in, and receive a valid JWT token.
- [ ] Frontend displays user identity and role badges dynamically based on logged-in user.
- [ ] Live Speech-to-Speech session displays text transcript bubbles during voice interaction.
