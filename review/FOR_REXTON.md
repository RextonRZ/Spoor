# For Rexton (append only)

Decisions only you can make, problems, and the end-of-day summary go here.

## Frontend (block C) — decisions for Rexton (frontend agent, 30 Oct)
- **Colour tokens**: your rexton-ui rule says tokens get your approval before building. You were away, so I chose a
  dark-neutral set (table in `review/requests/002_request.md` §3) and built on it. A theme change is a variable swap in
  `frontend/src/app/globals.css`. Dark only for now (PRD §19.1).
- **Licence note**: `frontend/public/draco/` is the Draco mesh decoder that ships inside the `three` npm package
  (Apache-2.0 code library, not an asset). If you want only MIT/CC0/CC-BY/OFL even for code, I can switch the GLB to
  meshopt compression (MIT) instead.
- **Demo sign-in**: the web app switches between three local demo users (investigator / reviewer / site admin) through
  a cookie; tokens stay server-side in `frontend/.env.local` (git-ignored). A real identity provider is out of scope.
