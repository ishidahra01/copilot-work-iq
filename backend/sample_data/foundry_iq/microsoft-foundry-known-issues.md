# Microsoft Foundry — Known Issues

## Purpose

This document tracks active and recently resolved known issues with the
Microsoft Foundry platform. Check this page before opening a new support
ticket or incident.

---

## Active Known Issues

### KI-001 — Foundry IQ returns stale results after source document update

**Status**: Active — Workaround available
**Severity**: SEV4
**Affected versions**: All
**Reported**: 2024-11-15
**Last updated**: 2025-01-20

**Description**:
After a document in SharePoint is updated, the Foundry IQ index may continue
to return the old version for up to 8 hours due to indexer schedule lag.
This does not affect documents added via direct Blob Storage ingestion.

**Root cause**:
The SharePoint connector uses a polling-based change detection mechanism with
a 4-hour window. Combined with the 4-hour indexer schedule, worst-case staleness
is approximately 8 hours.

**Workaround**:
Trigger a manual indexer run from the Azure portal when you need immediate freshness:
```
Azure Portal → AI Search → Indexers → sharepoint-connector → Run
```

**Permanent fix**:
Planned upgrade to SharePoint push-based change notifications in Q2 2025.

---

### KI-002 — Semantic search results degrade when index exceeds 500,000 documents

**Status**: Active — Mitigation in place
**Severity**: SEV3
**Affected versions**: Standard S2 SKU
**Reported**: 2025-01-08
**Last updated**: 2025-02-10

**Description**:
When the Foundry IQ index grows beyond 500,000 documents, semantic ranking
quality degrades noticeably for long-tail queries. Top-5 results accuracy
drops from ~92% to ~78% based on internal benchmarks.

**Root cause**:
Azure AI Search Standard S2 allocates limited memory for semantic ranking
models. Above a certain corpus size, the ranking model cannot hold all
candidate documents in memory, causing approximate ranking.

**Mitigation**:
- Index partitioning has been applied: engineering and HR documents are now
  in separate indexes (`foundry-iq-engineering-prod`, `foundry-iq-hr-prod`)
- The agent queries both indexes and merges results client-side

**Permanent fix**:
Upgrade to Standard S3 SKU planned for Q3 2025 when document count
is projected to exceed 800,000.

---

### KI-003 — `@azure/mcp` server exits unexpectedly on Azure Container Apps

**Status**: Active — Workaround available
**Severity**: SEV3
**Affected versions**: @azure/mcp <= 0.8.2
**Reported**: 2025-02-01
**Last updated**: 2025-02-28

**Description**:
When running the backend on Azure Container Apps, the `@azure/mcp` server
subprocess exits with code 1 after approximately 30 seconds of idle time
due to missing `AZURE_CLIENT_ID` when using user-assigned managed identity.

**Workaround**:
Set the `AZURE_CLIENT_ID` environment variable explicitly in your Container
App environment to the client ID of the user-assigned managed identity:
```bash
az containerapp update \
  --name <app-name> \
  --resource-group <rg> \
  --set-env-vars AZURE_CLIENT_ID=<managed-identity-client-id>
```

**Permanent fix**:
Tracked in @azure/mcp GitHub issue #213. Fix expected in 0.8.3 release.

---

### KI-004 — Work IQ calendar tool returns empty results for recurring meetings

**Status**: Active — Under investigation
**Severity**: SEV4
**Affected versions**: @microsoft/workiq >= 2.1.0
**Reported**: 2025-02-20

**Description**:
The Work IQ MCP `get_calendar_events` tool returns 0 results when querying
for recurring meeting series. Individual (non-recurring) meetings are returned
correctly.

**Workaround**:
None currently. Query for specific date ranges rather than the meeting title.

**Permanent fix**:
Under investigation by the Microsoft Graph team. ETA: unknown.

---

## Recently Resolved Issues

### KI-R001 — Agent fails to start when WORKIQ_ENABLED=true and Node.js < 18

**Status**: Resolved
**Resolved**: 2025-01-15
**Resolution**: Added Node.js version check in startup script. Minimum version
is now enforced to be 18.x. Updated container base image to `node:20-slim`.

---

### KI-R002 — PowerPoint generation fails for reports with > 10 slides

**Status**: Resolved
**Resolved**: 2025-01-22
**Resolution**: Fixed buffer overflow in `pptx_tool.py` when handling large
table datasets. Updated `python-pptx` to 1.0.2.

---

## Reporting a New Issue

If you encounter an issue not listed here:
1. Check the [Incident Runbook](microsoft-foundry-incident-runbook.md) for diagnostic steps
2. Search `#foundry-platform` in Teams for recent discussion
3. Open a ServiceNow ticket with:
   - Component affected (Foundry IQ / Work IQ / Fabric IQ)
   - Error message (exact text)
   - Steps to reproduce
   - Environment (dev / staging / prod)
   - Impact (number of users affected)

---

## Related Documents

- [Architecture Overview](microsoft-foundry-architecture.md)
- [Incident Runbook](microsoft-foundry-incident-runbook.md)
- [Postmortem: IQ-2024-09](microsoft-foundry-postmortem.md)
