The migration moved 40 gigabytes across three regions in four hours.
Operators confirmed the checksums before the cutover. Support tickets
dropped from twelve a week to two after the new runbook shipped.
Rollback ownership and the on-call rotation now live in the runbook.

P95 latency fell from 180ms to 90ms after the cache layer moved in
front of the hot path. ADR-041 documents the change, and the platform
team reviewed it on 2026-08-14.

The runbook says to keep /srv/app/config.yaml untouched and to roll
back by restoring the previous image tag from the registry.