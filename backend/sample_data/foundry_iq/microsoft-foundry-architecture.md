# Microsoft Foundry Architecture Overview

## Purpose

This document describes the internal architecture of the Microsoft Foundry platform
as deployed in our organization. It covers component layout, service dependencies,
data flow, and integration points with existing Microsoft 365 and Azure infrastructure.

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Microsoft Foundry Platform                    │
│                                                                       │
│  ┌─────────────┐   ┌─────────────────┐   ┌────────────────────────┐ │
│  │  Foundry IQ  │   │  Work IQ (Teams, │   │  Fabric IQ (Power BI,  │ │
│  │  (Knowledge) │   │  Email, Calendar)│   │  Data Factory, Lakehouse│ │
│  └──────┬───────┘   └────────┬────────┘   └──────────┬─────────────┘ │
│         │                    │                        │               │
│         └────────────────────┼────────────────────────┘               │
│                              │                                        │
│                    ┌─────────▼──────────┐                            │
│                    │  Unified Agent API  │                            │
│                    │  (Copilot SDK)      │                            │
│                    └────────────────────┘                            │
└─────────────────────────────────────────────────────────────────────┘
```

## Component Details

### Foundry IQ (Enterprise Knowledge Layer)

- **Technology**: Azure AI Search (semantic ranking enabled)
- **Index name**: `foundry-iq-prod`
- **Knowledge sources**:
  - Internal SharePoint sites (HR, IT, Engineering)
  - Confluence wiki exports (synced nightly)
  - Runbook repository (GitHub → Azure Blob → indexed)
  - Incident postmortems (ServiceNow attachments)
- **MCP endpoint**: Exposed via `@azure/mcp` with `azureaisearch` namespace
- **Authentication**: Managed Identity (no API key rotation needed)

### Work IQ (Collaboration Layer)

- **Technology**: Microsoft Graph API
- **Sources**: Teams, Outlook, SharePoint, OneDrive, Viva Engage
- **MCP server**: `@microsoft/workiq`
- **Permissions required**: `Mail.Read`, `Calendars.Read`, `ChatMessage.Read`

### Fabric IQ (Data & Analytics Layer)

- **Technology**: Microsoft Fabric (OneLake, Data Factory, Power BI)
- **Sources**: Business KPIs, incident metrics, SLA data
- **Access**: Power BI Embedded REST API
- **Status**: Planned for Phase 3 rollout

## Network Topology

All Foundry components are deployed in the `eastus2` region.

| Service              | VNET              | Subnet              | Private Endpoint |
|----------------------|-------------------|---------------------|-----------------|
| Azure AI Search      | vnet-foundry-prod | snet-search-prod    | Yes             |
| Azure OpenAI         | vnet-foundry-prod | snet-openai-prod    | Yes             |
| Azure Blob Storage   | vnet-foundry-prod | snet-storage-prod   | Yes             |
| Azure Key Vault      | vnet-foundry-prod | snet-keyvault-prod  | Yes             |

## Service Dependencies

```
Foundry IQ
  ├── Azure AI Search (semantic search + vector)
  ├── Azure OpenAI (embedding model: text-embedding-3-large)
  ├── Azure Blob Storage (source document store)
  ├── Azure Key Vault (secrets & API keys)
  └── Azure Managed Identity (auth for all services)
```

## Deployment Regions

- **Primary**: East US 2
- **Secondary (DR)**: West US 3 (read-only replica)
- **Failover RTO**: 4 hours
- **Failover RPO**: 1 hour

## Capacity Planning

| Component        | Current SKU    | Max Documents | Notes                          |
|------------------|---------------|---------------|--------------------------------|
| Azure AI Search  | Standard S2   | 1,000,000     | Upgrade to S3 at 800K docs     |
| Azure OpenAI     | PTU-100       | N/A           | Dedicated capacity             |
| Blob Storage     | LRS Standard  | Unlimited     | Lifecycle policy: 90-day tier  |

## Related Documents

- [Rollout Checklist](microsoft-foundry-rollout-checklist.md)
- [Incident Runbook](microsoft-foundry-incident-runbook.md)
- [Known Issues](microsoft-foundry-known-issues.md)
