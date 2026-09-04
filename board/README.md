# board

Next.js 15 App Router, TypeScript strict, Tailwind.

- `/` — corridor status, settlement tiles, last-checked and evidence age always visible.
- `/build` — phase progress, read from `progress.json` through the API.

`claim-*` CSS classes render each claim type differently, so a `scenario` can never be
drawn in the same style as an `observation`.

Lead times on the board are Phase 0 scaffolding until Phase 5 replaces them with routed
arrival times. This is stated on the page itself.
