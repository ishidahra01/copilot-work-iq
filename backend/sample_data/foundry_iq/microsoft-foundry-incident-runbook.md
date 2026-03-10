# Microsoft Foundry Incident Runbook

## Purpose

This runbook provides step-by-step procedures for diagnosing and resolving
incidents affecting the Microsoft Foundry platform. It covers Foundry IQ
(knowledge retrieval), Work IQ (collaboration), and shared infrastructure.

---

## Severity Definitions

| Severity | Description                                        | Response SLA |
|----------|----------------------------------------------------|-------------|
| SEV1     | Complete Foundry platform outage                   | 15 minutes  |
| SEV2     | Foundry IQ knowledge retrieval unavailable         | 30 minutes  |
| SEV3     | Degraded search quality or elevated latency        | 2 hours     |
| SEV4     | Non-critical issue or single-user impact           | Next day    |

---

## Runbook 1 — Foundry IQ Not Returning Results

### Symptoms
- Agent responds: "[Foundry IQ] Foundry IQ is not configured"
- Agent responds: "No relevant enterprise knowledge found"
- MCP tool returns empty or error response

### Diagnostic Steps

**Step 1: Verify environment variables**
```bash
echo $AZURE_FOUNDRY_PROJECT_ENDPOINT   # Should be set to Azure AI Search URL
echo $AZURE_SEARCH_INDEX_NAME          # Should be set to index name
echo $FOUNDRY_IQ_SAMPLE_MODE          # Should be "false" for production
```

**Step 2: Check Azure AI Search service health**
- Navigate to Azure Portal → Azure AI Search → your service
- Check **Overview** tab for any service health alerts
- Check **Monitoring → Metrics** for failed requests or high latency

**Step 3: Verify the index exists and has documents**
```bash
curl -H "Authorization: Bearer <token>" \
  "https://<endpoint>.search.windows.net/indexes/<index-name>/stats?api-version=2024-07-01"
```
Expected: `documentCount > 0`

**Step 4: Test MCP connectivity**
```bash
npx -y @azure/mcp@latest server start --namespace azureaisearch
# Then send a test query via JSON-RPC
```

**Step 5: Check indexer status**
- Azure Portal → AI Search → Indexers
- Look for errors or "warning" status
- Click on the indexer → **Execution History** for detailed logs

### Resolution

| Root Cause                    | Action                                                  |
|-------------------------------|----------------------------------------------------------|
| Env var not set               | Set `AZURE_FOUNDRY_PROJECT_ENDPOINT` in app config       |
| Empty index                   | Run indexer manually from Azure portal                   |
| Auth failure (401)            | Re-assign `Search Index Data Reader` role to identity    |
| Index deleted                 | Re-create index per Rollout Checklist Phase 2            |
| MCP package not installed     | Run `npm install -g @azure/mcp`                          |

---

## Runbook 2 — Foundry IQ High Latency

### Symptoms
- Knowledge retrieval takes > 5 seconds
- Requests timing out in the agent (timeout: 30s)
- Azure Monitor shows P95 latency > 2000ms

### Diagnostic Steps

**Step 1: Check Azure AI Search throttling**
- Azure Portal → AI Search → Monitoring → Metrics
- Check `SearchQueriesPerSecond` vs service limits
- Standard S2: 15 QPS per replica

**Step 2: Review query complexity**
- Semantic search is slower than keyword search
- Check if `queryType=semantic` is necessary for all queries

**Step 3: Check index fragmentation**
- Azure Portal → AI Search → Indexes → your index → **Analyze**
- High fragmentation can cause slow queries

### Resolution

| Root Cause          | Action                                                          |
|---------------------|-----------------------------------------------------------------|
| QPS throttling      | Scale out replicas (Azure Portal → AI Search → Scale)           |
| Slow semantic search| Add more replicas; consider S3 tier for high-traffic indexes    |
| Index fragmentation | Trigger an index rebuild via Azure portal or REST API           |
| Cold start          | Warm up index with scheduled queries during off-peak hours      |

---

## Runbook 3 — MCP Server Connection Failures

### Symptoms
- Agent logs: `Foundry IQ MCP server unavailable`
- `FileNotFoundError` when spawning `npx -y @azure/mcp@latest`
- JSON-RPC parse errors

### Diagnostic Steps

**Step 1: Verify npx is available**
```bash
npx --version
node --version   # Should be >= 18.x
```

**Step 2: Try running the MCP server manually**
```bash
npx -y @azure/mcp@latest server start --namespace azureaisearch
# Should show: "Server listening on stdio"
```

**Step 3: Check network access to npm registry**
```bash
npm ping
```

### Resolution

| Root Cause            | Action                                                     |
|-----------------------|------------------------------------------------------------|
| Node.js not installed | Install Node.js >= 18 on the backend container/VM          |
| npm registry blocked  | Configure npm proxy: `npm set proxy http://proxy:8080`     |
| @azure/mcp not found  | Run `npm install -g @azure/mcp` to pre-install             |
| Wrong namespace       | Ensure `--namespace azureaisearch` is passed               |

---

## Escalation Path

1. **On-call engineer** — Check dashboards, run diagnostics above
2. **Foundry platform team** — Ping `#foundry-platform` in Teams
3. **Azure Support** — Open support ticket if root cause is Azure service issue
   - Portal: https://portal.azure.com → Help + Support
   - Include: subscription ID, resource IDs, correlation IDs from Azure Monitor

---

## Related Documents

- [Architecture Overview](microsoft-foundry-architecture.md)
- [Known Issues](microsoft-foundry-known-issues.md)
- [Postmortem: IQ-2024-09](microsoft-foundry-postmortem.md)
