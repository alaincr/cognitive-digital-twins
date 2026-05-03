# Thesis Synthesizer — Heartbeat

## Schedule
Daily (evening)

## On each heartbeat

1. **Check integration queue:** Read issues assigned by Integration Director
2. **For each approved finding:**
   - Read the component team's source material
   - Determine which scaffolding section it belongs to
   - Add it with proper attribution and `((block-ref))` links
   - If it creates a tension, add `⚠️ TENSIONE:` block and notify Integration Director
3. **Scaffolding health check (weekly, Fridays):**
   - Does every chapter have at least one supporting source?
   - Are there gaps with no assigned component team working on them?
   - Are tensions accumulating without resolution? Escalate stale ones.
4. **Output:** Updated `[[Scaffolding]]`, log entry in Daily Note tagged `#scaffolding-update`
