# Microsoft Foundry Rollout Checklist

## Purpose

This checklist guides teams through the end-to-end process of enabling a new
knowledge source in Foundry IQ. Follow each step in sequence and obtain sign-off
before proceeding to the next phase.

---

## Phase 1 — Pre-Rollout Planning

- [ ] **Identify knowledge source owner** — assign a DRI (Directly Responsible Individual)
- [ ] **Classify data sensitivity** — confirm the content is approved for AI indexing
  - Permitted: Technical runbooks, architecture docs, public-facing SOPs
  - Restricted: PII, financial records, legal documents, HR files
- [ ] **Estimate document volume** — review Azure AI Search capacity (see Architecture doc)
- [ ] **Submit change request** — open a ticket in ServiceNow with:
  - Source type (SharePoint / Confluence / Blob / GitHub)
  - Owner and DRI
  - Estimated document count
  - Target index name

---

## Phase 2 — Azure AI Search Index Setup

- [ ] **Create or verify index** in the Azure portal
  - Index name convention: `foundry-iq-{team}-{env}` (e.g. `foundry-iq-engineering-prod`)
  - Enable semantic ranking (requires Standard S2 or higher)
  - Enable vector search (use `text-embedding-3-large` model)
- [ ] **Configure CORS** if index will be queried from browser-based tools
- [ ] **Set managed identity permissions** — assign `Search Index Data Reader` role
  to the Copilot backend managed identity
- [ ] **Test connectivity** from the backend service:
  ```bash
  curl -H "Authorization: Bearer $(az account get-access-token --resource https://search.azure.com --query accessToken -o tsv)" \
       "https://<search-endpoint>.search.windows.net/indexes/<index-name>/docs/search?api-version=2024-07-01" \
       -d '{"search": "test query", "top": 1}'
  ```

---

## Phase 3 — Data Ingestion

- [ ] **Configure data source connector** in Azure AI Search
  - SharePoint: use the SharePoint Online connector
  - Confluence: export to Azure Blob, use Blob connector
  - GitHub: sync to Blob via GitHub Actions, use Blob connector
- [ ] **Configure skillset** (optional but recommended):
  - Key phrase extraction
  - Entity recognition
  - Custom chunking (recommended: 512 tokens, 10% overlap)
- [ ] **Run initial indexer** — confirm document count matches expectation
- [ ] **Verify semantic ranking** — run 5 sample queries and validate relevance

---

## Phase 4 — Agent Integration

- [ ] **Update environment variable** `AZURE_SEARCH_INDEX_NAME` to include the new index
  (comma-separated if multiple indexes are queried)
- [ ] **Test via Foundry IQ tool** in the staging environment:
  ```
  FOUNDRY_IQ_SAMPLE_MODE=false
  AZURE_FOUNDRY_PROJECT_ENDPOINT=https://<search-endpoint>.search.windows.net
  AZURE_SEARCH_INDEX_NAME=foundry-iq-{team}-{env}
  ```
- [ ] **Validate agent responses** — run the standard demo scenarios (see Demo Scenarios doc)
- [ ] **Confirm MCP connectivity** — verify `@azure/mcp azureaisearch` can reach the index

---

## Phase 5 — Production Enablement

- [ ] **Deploy to production** via standard GitOps pipeline (PR → review → merge → deploy)
- [ ] **Update monitoring dashboards** — add new index to Azure Monitor alerts
- [ ] **Set up indexer schedule** — recommended: every 4 hours for active sources
- [ ] **Document the new source** — update Architecture doc and this checklist
- [ ] **Notify stakeholders** — send announcement to `#foundry-platform` Teams channel

---

## Phase 6 — Post-Rollout Validation

- [ ] **Monitor first 48 hours** — check for indexer errors in Azure portal
- [ ] **Validate query quality** — confirm relevant results for key business queries
- [ ] **Review Azure AI Search metrics** — latency, throttling, QPS
- [ ] **Close the ServiceNow change request**

---

## Troubleshooting Common Rollout Issues

### Issue: Agent returns "No relevant enterprise knowledge found"

**Cause**: Index is empty or query terms don't match indexed content.

**Resolution**:
1. Verify the indexer ran successfully: Azure Portal → AI Search → Indexers
2. Check document count: it should be > 0
3. Run a direct search query via the Azure portal Search Explorer
4. If using semantic ranking, confirm the semantic configuration is set on the index

### Issue: MCP server returns 401 Unauthorized

**Cause**: Managed identity does not have `Search Index Data Reader` role.

**Resolution**:
```bash
az role assignment create \
  --role "Search Index Data Reader" \
  --assignee <managed-identity-object-id> \
  --scope /subscriptions/<sub-id>/resourceGroups/<rg>/providers/Microsoft.Search/searchServices/<service-name>
```

### Issue: Indexer failing with "Transient error"

**Cause**: Source connectivity issue (SharePoint throttling, Blob access denied).

**Resolution**:
1. Check indexer error details in Azure portal
2. Verify managed identity access to the source
3. Reset the indexer and re-run: `POST /indexers/<name>/reset`

---

## Related Documents

- [Architecture Overview](microsoft-foundry-architecture.md)
- [Incident Runbook](microsoft-foundry-incident-runbook.md)
- [Known Issues](microsoft-foundry-known-issues.md)
