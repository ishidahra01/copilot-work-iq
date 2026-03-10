# Postmortem: Foundry IQ Outage IQ-2024-09

## Incident Summary

| Field             | Value                                                |
|-------------------|------------------------------------------------------|
| **Incident ID**   | IQ-2024-09                                           |
| **Date**          | 2024-09-17                                           |
| **Duration**      | 4 hours 23 minutes (14:12 UTC – 18:35 UTC)           |
| **Severity**      | SEV2                                                 |
| **Impact**        | 100% of Foundry IQ knowledge retrieval unavailable   |
| **Affected users**| All users of the Enterprise Intelligence Agent       |
| **Author**        | Foundry Platform Team                                |
| **Status**        | Closed                                               |

---

## Timeline

| Time (UTC) | Event                                                                      |
|------------|----------------------------------------------------------------------------|
| 14:12      | Alert fired: Azure AI Search service returning 503 for all queries         |
| 14:15      | On-call engineer acknowledged alert                                        |
| 14:22      | Confirmed: Azure AI Search endpoint returning 503 for all index queries    |
| 14:35      | Azure Service Health checked — no official incident posted yet             |
| 14:47      | Azure Support ticket opened (Priority A)                                   |
| 15:10      | Azure posted incident: "Azure AI Search — East US 2 — Degraded performance"|
| 15:30      | Attempted failover to West US 3 replica — blocked (DR index was stale)    |
| 16:00      | Azure reported root cause: storage backend failover in East US 2           |
| 18:35      | Azure AI Search service restored; all queries returning 200                |
| 18:50      | Post-incident validation passed; agents confirmed operational              |

---

## Root Cause

An unplanned storage backend failover event in Azure East US 2 caused the Azure AI Search
service to enter a degraded state. During the failover window, the search service was unable
to serve index queries, returning HTTP 503 errors.

Our disaster recovery replica in West US 3 was not usable because:
1. The nightly sync job had failed silently for 3 days due to an expired Blob SAS token.
2. The DR index was 72 hours stale.
3. The agent configuration did not have a fallback to the DR endpoint.

---

## Impact Analysis

- **Foundry IQ tool**: 100% of queries failed for 4h 23m
- **Agent behavior**: Agent continued to function using only MS Docs and Work IQ tools;
  enterprise knowledge retrieval was unavailable
- **User-facing impact**: Agents could not surface internal runbooks or architecture docs;
  quality of investigation responses was degraded
- **Escalations received**: 14 tickets filed via Helpdesk

---

## Contributing Factors

1. **Silent SAS token expiry**: The DR sync job was failing silently since 2024-09-14.
   No alert was configured for indexer failures on the DR index.

2. **No automatic failover**: The backend was configured with a single endpoint.
   No health-check logic existed to switch to the DR endpoint on errors.

3. **Stale DR index**: Because of (1), the DR index was 72 hours out of date by the
   time of the incident, making it unusable for production traffic.

4. **Azure Service Health delay**: Azure did not post to Service Health for 63 minutes
   after the incident began, delaying our diagnosis.

---

## Action Items

| ID  | Action                                                           | Owner          | Due Date   | Status   |
|-----|------------------------------------------------------------------|----------------|------------|----------|
| A1  | Configure alerts for indexer failures (both primary and DR)      | Foundry Team   | 2024-10-01 | ✅ Done  |
| A2  | Rotate Blob SAS token to Managed Identity (no expiry risk)       | Foundry Team   | 2024-10-01 | ✅ Done  |
| A3  | Implement endpoint health check + automatic DR failover          | Backend Team   | 2024-11-15 | ✅ Done  |
| A4  | Add DR index freshness check to runbook pre-incident checks      | Foundry Team   | 2024-10-15 | ✅ Done  |
| A5  | Configure Azure Service Health alerts to PagerDuty              | SRE Team       | 2024-10-30 | ✅ Done  |
| A6  | Implement fallback message to users when Foundry IQ unavailable  | Backend Team   | 2024-10-15 | ✅ Done  |
| A7  | Test DR failover quarterly (chaos engineering exercise)          | SRE Team       | Recurring  | 🔄 Q1 2025 done |

---

## Lessons Learned

### What went well

- The alert fired within 3 minutes of the incident start.
- The on-call engineer acknowledged quickly and followed the runbook.
- The agent gracefully degraded (MS Docs and Work IQ continued working).
- Post-incident communication to users was clear and timely.

### What could be improved

- SAS token-based auth should never be used for critical sync jobs. Managed Identity is now standard.
- Silent failures in background jobs (indexer runs) need alerting, not just logging.
- DR failover should be automated, not manual.
- Azure Service Health integration should be automated to PagerDuty.

---

## Prevention for Future Incidents

1. **Monitoring**: All indexer jobs now alert on failure (A1 ✅)
2. **Auth**: All sync jobs use Managed Identity (A2 ✅)
3. **Resilience**: Backend implements health-check-based DR failover (A3 ✅)
4. **Chaos testing**: DR failover tested quarterly (A7 ongoing)
5. **Runbook**: This postmortem's timeline is incorporated into the Incident Runbook

---

## Related Documents

- [Incident Runbook](microsoft-foundry-incident-runbook.md)
- [Architecture Overview](microsoft-foundry-architecture.md)
- [Known Issues](microsoft-foundry-known-issues.md)
