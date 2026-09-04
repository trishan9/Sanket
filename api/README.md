# api

Flask, read-mostly. The board is a consumer; it never drives the watch.

`/api/health` · `/api/status` · `/api/status/<basin_id>` · `/api/corridors` ·
`/api/progress` · `/api/runs` · `/api/trace/<run_id>`

Routes are registered from the `ROUTES` table with named handlers.
