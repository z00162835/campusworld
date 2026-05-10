# Frontend Agent Guide

Follow root `AGENTS.md` first. This file covers Vue frontend work.

## Source Of Truth

- Frontend contract: `../docs/frontend/SPEC/SPEC.md`
- Testing contract: `../docs/testing/SPEC/SPEC.md`
- Runtime code: `src/`

## Architecture Rules

- Use Vue 3 Composition API with `<script setup>` and TypeScript strict mode.
- API calls go through `src/api/`; do not call `axios` directly from views/components.
- Shared state lives in Pinia stores under `src/stores/`.
- Reusable workflows belong in `src/composables/`.
- Use Element Plus and existing component/style patterns before adding new UI primitives.

## Auth And Session Rules

- Access token is in-memory only via `auth` store.
- Refresh token is backend httpOnly cookie only; never put it in Pinia, `localStorage`, or `sessionStorage`.
- `/auth/login`, `/auth/register`, `/auth/refresh`, `/auth/logout` 401 responses must not trigger refresh retry.
- Login failures show generic text, except network failure.
- Logout must go through `useLogout()`, clear user-scoped stores, and `router.replace('/login')` immediately.
- Reset sensitive store state on logout. Preserve only explicit non-sensitive user preferences.

## Verification

- Type check: `npm run type-check`.
- Tests: `npm run test -- --run`.
- For auth/session changes, include focused store/interceptor/router tests when practical.
- For visible UI changes, run the app and inspect the relevant route.

## Practical Notes

- Keep button text and compact UI labels from overflowing.
- Prefer `router-link`/router navigation over raw anchors for internal SPA routes.
- Do not add marketing-style landing pages unless explicitly requested.
