# WhatsApp document uploads

Deploy the backend before the frontend that enables 96 MB document uploads.
The backend release must include both the Daphne startup configuration in
`ANK/ANK/asgi.py` and the streaming media relay dependency in `requirements.txt`.
No database migration is required.

The frontend document limit is 96 * 1024 * 1024 bytes, or 100,663,296 bytes,
following the app's existing MB convention. A live Meta upload accepted that
exact size. Files above it never make a browser upload request. Images, audio
and video keep their existing smaller limits.

The backend retains its 100 * 1024 * 1024-byte validation limit. Meta accepted
a 100,000,000-byte file but rejected a 104,857,600-byte file with HTTP 413.
These tests do not establish the exact upstream byte cutoff. The frontend's
96 MB cap leaves headroom below the failed size. A Meta size rejection returns
a validation error without retrying or interrupting other API requests.

`WHATSAPP_MEDIA_MAX_CONCURRENT_UPLOADS` defaults to 1 per container. File locks
coordinate threads and processes sharing its temporary directory. Additional
uploads receive HTTP 429 with `Retry-After: 10`; the user can retry the file.
This limits active relays to Meta, not incoming traffic at the load balancer.
The limit applies independently to each container. Increase it only after
measuring memory and API latency under concurrent uploads.

Daphne 4.2.1 allows Twisted to parse multipart forms before Django. The ASGI
startup workaround disables that duplicate parser so Django's upload handlers
can use temporary files. Recheck the workaround when upgrading Daphne or
Twisted. Daphne still queues the incoming body for ASGI delivery, so this is
not a constant-memory browser-to-server pipeline.

Local full-HTTP tests with the repository's Daphne/Twisted stack measured about
1,460 MiB peak server RSS for a 104,857,600-byte upload before the workaround,
and about 236 MiB afterward. The final 100,000,000-byte transfer peaked around
229 MiB. These measurements do not prove the cause of the hosted outage or
establish capacity for the deployed environment.

Live Meta tests used generated PDFs through the updated local Django/Daphne
endpoint. Uploads at 27,262,976, 52,428,800, 100,000,000 and 100,663,296 bytes
returned media IDs. The final 96 MB upload took about 15 seconds and peaked at
about 231 MiB server RSS. Only test media was deleted afterward. No WhatsApp messages were sent.
The deployed AWS load balancer and production frontend were not part of these
tests.

Regression checks:

```sh
# From ANK-backend/ANK, using the project virtual environment:
DATABASE_URL='' ../venv/bin/python manage.py test MessageTemplates --noinput

# From ank_test:
node --test tests/whatsapp-media-upload.test.mjs
npm run build
```

After deployment, verify one document above 25 MB and one at the frontend's
96 MB limit. Check API health, events and templates during the upload and after a
failed upload. Monitor container memory, task restarts, relay duration and
429/502 responses before increasing upload concurrency.
