# Phase 10: Super Admin & RBAC Role Management System

This task document outlines the implementation of the Super Admin (Role 0) role, environment-driven credentials in `.env`, exclusive role assignment endpoints, default user registration rules, and instant Redis permission cache invalidation.

---

## 1. Objectives
- Introduce a top-tier **Super Admin** role (Role ID: 0) with full master system privileges across all databases, tools, and user telemetry.
- Configure Super Admin credentials (`SUPER_ADMIN_EMAIL`, `SUPER_ADMIN_PASSWORD`, `SUPER_ADMIN_ID`) in `.env` and `backend/config.py`.
- Enforce default **Standard User** (Role ID: 3) assignment for all new registrations.
- Provide Super Admin exclusive user management endpoints (`GET /admin/users`, `PUT /admin/users/{user_id}/role`).
- Enable instant permission updates by invalidating Redis caches upon role assignment.

---

## 2. Technical Tasks

### 2.1 Environment Configuration & Database Seed ([.env](file:///c:/git-hub/EchoStack/.env) & [postgres/init.sql](file:///c:/git-hub/EchoStack/postgres/init.sql))
- [ ] Add Super Admin credentials to `.env` (`SUPER_ADMIN_EMAIL`, `SUPER_ADMIN_PASSWORD`, `SUPER_ADMIN_ID`).
- [ ] Add `super_admin` role (Role ID: 0) with `"is_super_admin": true` and `"can_manage_users": true` in `init.sql`.
- [ ] Update `users` table schema to set `role_id DEFAULT 3` (Standard user).
- [ ] Seed default Super Admin user account in `postgres/init.sql` matching environment defaults.

### 2.2 Backend Super Admin Security & Endpoints ([backend/config.py](file:///c:/git-hub/EchoStack/backend/config.py), [backend/auth.py](file:///c:/git-hub/EchoStack/backend/auth.py) & [backend/main.py](file:///c:/git-hub/EchoStack/backend/main.py))
- [ ] Bind Super Admin environment settings in `backend/config.py`.
- [ ] Implement startup seed check/verifier ensuring Super Admin account exists in PostgreSQL on boot.
- [ ] Implement `require_super_admin` security dependency in `backend/auth.py`.
- [ ] Create `GET /admin/users` endpoint returning registered user list and assigned roles.
- [ ] Create `PUT /admin/users/{user_id}/role` endpoint restricted to Super Admin.
- [ ] Implement immediate Redis cache invalidation (`user_permissions:<user_id>`) upon role update.
- [ ] Create `GET /auth/super-admin-token` dev endpoint for testing.

### 2.3 Frontend & Documentation Updates ([frontend/src/App.jsx](file:///c:/git-hub/EchoStack/frontend/src/App.jsx) & [reference/roles.md](file:///c:/git-hub/EchoStack/reference/roles.md))
- [ ] Render Super Admin status and user management capabilities in the UI Security & Telemetry panel.
- [ ] Document Super Admin permissions, environment variables, and role assignment rules in plain English in `reference/roles.md`.

---

## 3. Verification Criteria
- [ ] Super Admin credentials are fully configurable via `.env` (`SUPER_ADMIN_EMAIL`, `SUPER_ADMIN_PASSWORD`, `SUPER_ADMIN_ID`).
- [ ] New users default to Standard Role (3) upon creation.
- [ ] Only requests carrying a valid Super Admin JWT (Role 0) can call `PUT /admin/users/{user_id}/role`.
- [ ] Role changes immediately update PostgreSQL and purge Redis cache so new permissions apply instantly.

