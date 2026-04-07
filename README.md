# Fabric Deployment — Developer README

## Purpose

This README documents the end-to-end DevOps implementation used to deploy Fabric artifacts (Lakehouses, Pipelines, Notebooks, Semantic Models, Reports, Writeback) from a source-controlled DEV workspace into TEST and PROD. It is written for engineers (detailed usage, CLI, config examples) and managers (high-level flow, governance). All sensitive values are redacted and replaced with placeholders so this repository can be published publicly.

### Redaction Policy

**Applies throughout this repo and examples:** Replace every real identifier, secret, or connection string with the placeholders below. Do not commit real secrets or IDs.

- **Tenant ID** → `{{TENANT_ID}}`
- **Subscription ID** → `{{SUBSCRIPTION_ID}}`
- **Workspace ID** → `{{WORKSPACE_ID_<ENV>}}` (e.g., `{{WORKSPACE_ID_PROD}}`)
- **Client ID** → `{{CLIENT_ID}}`
- **Client Secret** → `{{CLIENT_SECRET}}`
- **SQL connection string** → `{{SQL_CONN_STRING}}`
- **Any GUIDs or resource IDs** → `{{RESOURCE_ID_<NAME>}}`

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Repository Layout](#repository-layout)
3. [High-Level Deployment Flow & Branching](#high-level-deployment-flow--branching)
4. [Config JSON Schema & Sanitized Examples](#config-json-schema--sanitized-examples)
5. [Azure DevOps Pipeline (YAML) — Sanitized Example](#azure-devops-pipeline-yaml--sanitized-example)
6. [Annotated Script Reference](#annotated-script-reference)
7. [Service Principals, Workspace Identities & Governance](#service-principals-workspace-identities--governance)
8. [Post-Deployment Validation](#post-deployment-validation)
9. [Quick Fixes](#quick-fixes)
10. [YAML Snippet](#yaml-snippet)
11. [Repository Directory Structure](#repository-directory-structure)
12. [Pipeline Execution for Different Environments](#pipeline-execution-for-different-environments)
13. [Pipeline Configuration Parameters](#pipeline-configuration-parameters)

---

## Executive Summary

### What This Repo Provides

- A repeatable, auditable deployment process that uses source-controlled artifacts in DEV as the source of truth.
- Scripts to build a filtered repository, patch environment-specific values, and publish artifacts to Fabric workspaces.
- Sanitized example configs and pipeline definitions you can adapt.
- A documented governance model for service principals and workspace identities.

### Key Principles

- **Source of truth:** DEV repo (feature → main → release branches).
- **Validation:** Deploy DEV → TEST for validation; deploy DEV → PROD from source control (do not promote TEST → PROD directly).
- **Least privilege:** Service principals and workspace identities are assigned minimal roles required for deployment.

---

## Repository Layout

```
fabric_deployment/
├─ config/
│  ├─ test_orchestration.json
│  ├─ test_model.json
│  ├─ test_reporting.json
│  ├─ test_writeback.json
├─ pipelines/
│  └─ azure-pipelines.yml
├─ scripts/
│  ├─ deploy.py
│  ├─ orchestration.py
│  ├─ model.py
│  ├─ report.py
│  └─ writeback.py
├─ requirements.txt
└─ README.md  <-- you are here
```

### Notes

- **config/** contains environment JSONs (one per workspace type and environment). All IDs in these files must use placeholders before publishing.
- **pipelines/** contains the Azure DevOps YAML pipeline(s).
- **scripts/** contains the Python deployment scripts. Each script has a CLI entry point and reads a config JSON.

---

## High-Level Deployment Flow & Branching

### Flow (Governance)

- **DEV** (source control, CI) → **TEST** (validation)
- **DEV** (source control, CI) → **PROD** (production)

TEST is a validation sandbox and is not source-controlled in your environment; therefore, do not promote TEST → PROD directly.

### Branching Strategy (Recommended)

```
feature/first_sync → main → release/UAT → release/PROD
```

### Branch Usage

- **feature/\*** — development work, PRs, CI runs.
- **main** — stable code; merges from feature branches after review.
- **release/UAT** — used to deploy to TEST/UAT for validation.
- **release/PROD** — used to deploy to PROD (protected branch, approvals required).

### Pipeline Triggers

- **Feature branch:** CI runs (unit tests, lint).
- **main:** nightly or manual build.
- **release/\*:** gated deployment pipelines with approvals.

---

## Config JSON Schema & Sanitized Examples

### Common Keys

- **workspace_id** — target Fabric workspace ID.
- **environment** — string used by scripts to determine ENV (e.g., DEV_ORCHESTRATION, TEST_MODEL, PROD_REPORTING).
- **db_mapping** — mapping of logical DB names to environment-specific server/database.
- **lakehouse_id_map** — mapping of logical lakehouse names to GUIDs per environment.
- **spark_environment_map** — mapping of environment name to Spark environment ID.
- **item_type_in_scope** — list of artifact types to deploy.
- **item_name_filter** — optional list of artifact names to include.

### Sanitized Example: orchestration.json

```json
{
  "workspace_id": "WORKSPACE_ID_TEST",
  "environment": "TEST_ORCHESTRATION",
  "repository_root": "fabric_workspaces/ORCHESTRATION",
  "item_type_in_scope": ["Lakehouse", "Environment", "Notebook", "DataPipeline"],
  "item_name_filter": {
    "Lakehouse": [],
    "Notebook": ["Sample_Notebook"],
    "DataPipeline": ["Sample_Pipeline"],
    "Environment": [],
    "Dataflow_Gen2": []
  },
  "lakehouse_id_map": {
    "DEV": {
      "LAKEHOUSE_ID_DEV_LANDING": "Landing",
      "LAKEHOUSE_ID_DEV_BRONZE": "Bronze",
      "LAKEHOUSE_ID_DEV_SILVER": "Silver",
      "LAKEHOUSE_ID_DEV_GOLD": "Gold"
    },
    "TEST": {
      "LAKEHOUSE_ID_TEST_LANDING": "Landing",
      "LAKEHOUSE_ID_TEST_BRONZE": "Bronze",
      "LAKEHOUSE_ID_TEST_SILVER": "Silver",
      "LAKEHOUSE_ID_TEST_GOLD": "Gold"
    },
    "PROD": {
      "LAKEHOUSE_ID_PROD_LANDING": "Landing",
      "LAKEHOUSE_ID_PROD_BRONZE": "Bronze",
	  "LAKEHOUSE_ID_TEST_SILVER": "Silver",
      "LAKEHOUSE_ID_TEST_GOLD": "Gold"
    }
  },
  "db_mapping": {
    "DEV": {
      "server_name": "DEV_SERVER_NAME",
      "database_name": "DEV_DATABASE_NAME"
    },
    "TEST": {
      "server_name": "TEST_SERVER_NAME",
      "database_name": "TEST_DATABASE_NAME"
    },
    "PROD": {
      "server_name": "PROD_SERVER_NAME",
      "database_name": "PROD_DATABASE_NAME"
    }
  },
  "spark_environment_map": {
    "DEV": "SPARK_ENV_ID_DEV",
    "TEST": "SPARK_ENV_ID_TEST",
    "PROD": "SPARK_ENV_ID_PROD"
  }
}

```

### Guidance

- Keep one JSON per environment/workspace type.
- Use consistent logical names (Landing, Bronze, Silver, etc.) across envs so scripts can map by logical name.

---

## Azure DevOps Pipeline (YAML) — Sanitized Example

### File: pipelines/azure-pipelines.yml

```yaml
trigger: none
pr: none

parameters:
  - name: environment
    type: string
    default: test
    values:
      - test
      - prod

  - name: workspace
    type: string
    default: orchestration
    values:
      - all
      - orchestration
      - reporting
      - model
      - writeback

steps:
  - task: UsePythonVersion@0
    inputs:
      versionSpec: '3.11'
      architecture: 'x64'
    displayName: 'Use Python 3.11'

  - script: python -m pip install -r $(Build.SourcesDirectory)/fabric_deployment/requirements.txt
    displayName: 'Install Python dependencies'

  - script: |
      echo "Deploying for ${{ parameters.environment }} ${{ parameters.workspace }}"
      python "$(Build.SourcesDirectory)/fabric_deployment/scripts/deploy.py" ${{ parameters.environment }} ${{ parameters.workspace }}
    displayName: 'Dynamic Deploy'
    env:
      AZURE_CLIENT_ID: $(AZURE_CLIENT_ID)
      AZURE_TENANT_ID: $(AZURE_TENANT_ID)
      AZURE_CLIENT_SECRET: $(AZURE_CLIENT_SECRET)

```

### Notes

- **Secrets:** never store secrets in plain YAML. Use pipeline secure variables or Azure Key Vault integration.

---

## Annotated Script Reference

Below are concise, actionable references for each script. Each entry includes purpose, CLI usage, key env vars, config expectations, and important behaviors.

### orchestration.py — Full Walkthrough

**Purpose:** Deploy orchestration artifacts: pipelines, lakehouses, notebooks, environment definitions.

**Usage:**
```bash
python scripts/orchestration.py <environment>
# e.g.
python scripts/orchestration.py test
```

**Inputs:**
- **CLI arg:** `<environment>` — matches `config/<env>_orchestration.json` (e.g., test → config/test_orchestration.json).
- **Environment variables required for authentication:**
  - `AZURE_TENANT_ID={{TENANT_ID}}`
  - `AZURE_CLIENT_ID={{CLIENT_ID}}`
  - `AZURE_CLIENT_SECRET={{CLIENT_SECRET}}`

**Behavior:**
1. Loads config JSON for the environment.
2. Builds a filtered repo (copies only items in item_name_filter and item_type_in_scope).
3. Patches notebooks:
   - Replaces lakehouse GUIDs using lakehouse_id_map.
   - Replaces ABFS workspace IDs with workspace_id.
   - Replaces server_name, database_name, and ENV placeholders.
   - Replaces Spark environment IDs using spark_environment_map.
4. Publishes artifacts using Fabric API (via fabric_cicd or equivalent library).

**Important Checks:**
- Validate environment field in JSON matches CLI arg semantics (scripts often derive env from JSON; prefer CLI-driven env).
- Ensure spark_environment_map contains mapping for the target env.
- Confirm db_mapping contains keys for the environment (DEV/TEST/PROD).

**Common Fixes:**
- If notebooks still reference DEV IDs: check lakehouse_id_map and abfs replacement logic.
- If publish fails: verify service principal permissions and workspace identity membership.

### model.py — Full Walkthrough

**Purpose:** Deploy model artifacts: SQL Databases, UserDataFunctions, Semantic Models.

**Usage:**
```bash
python scripts/model.py <environment>
```

**Inputs:**
- `config/<env>_model.json` (workspace_id, db_mapping, semantic model mappings).

**Behavior:**
1. Reads JSON config and authenticates.
2. Deploys SQL Database objects (if included).
3. Deploys UserDataFunctions and other DB objects.
4. Deploys SemanticModel (TDML or equivalent) and updates its workspace/database IDs in the model file before publishing.

**Important Checks:**
- Ensure semantic model TDML contains placeholders that the script can replace.
- Confirm workspace identity used by the model workspace has access to the SQL DB.

### report.py — Full Walkthrough

**Purpose:** Deploy reports and bind them to semantic models/datasets.

**Usage:**
```bash
python scripts/report.py <environment>
```

**Behavior:**
1. Loads `config/<env>_reporting.json`.
2. Publishes reports to the target workspace.
3. Rebinds datasets to the correct semantic model/dataset IDs (replaces placeholders in report metadata).
4. Validates report load (optionally triggers a dataset refresh).

**Important Checks:**
- Confirm semantic model IDs are present in config and match the model workspace.
- Validate dataset refresh permissions.

### writeback.py — Full Walkthrough

**Purpose:** Deploy writeback artifacts and configure semantic writeback integration.

**Usage:**
```bash
python scripts/writeback.py <environment>
```

**Behavior:**
1. Loads `config/<env>_writeback.json`.
2. Deploys writeback configuration and ensures the writeback dataset is bound to the semantic model.
3. Validates writeback connectivity (SQL DB permissions, workspace identity).

**Important Checks:**
- Ensure writeback DB connection strings are redacted in public examples.
- Validate workspace identity has necessary DB roles.

### deploy.py — Orchestrator Wrapper

**Purpose:** High-level wrapper used by CI pipelines to run the appropriate scripts in sequence.

**Usage:**
```bash
python scripts/deploy.py <environment>
# Example:
python scripts/deploy.py test
```

**Behavior:**
1. Accepts environment arg (e.g., test, prod).
2. Runs orchestration.py, model.py, report.py, writeback.py in the configured order (or a subset based on item_type_in_scope).
3. Logs results and returns non-zero exit code on failure (CI will mark pipeline failed).

**Important Checks:**
- Ensure deploy.py uses the same config naming convention as other scripts.
- Confirm deploy.py respects item_type_in_scope to avoid unnecessary deployments.

---

## Service Principals, Workspace Identities & Governance

### Recommended Identities (Redacted Names)

- **Service principal for CI/CD:** CI-SP-Deployment
  - **Purpose:** used by pipelines to authenticate and publish artifacts.
  - **Permissions:** Contributor on target workspaces or scoped roles as required.

- **Workspace identities (one per workspace):**
  - Orchestration-WS-Identity
  - Model-WS-Identity
  - Reporting-WS-Identity
  - Writeback-WS-Identity

### Role Matrix (Example)

| Identity | Orchestration WS | Model WS | Reporting WS | Writeback WS |
|----------|------------------|----------|--------------|--------------|
| CI-SP-Deployment | Contributor | Contributor | Contributor | Contributor |
| Orchestration-WS-Identity | Owner | Reader | Reader | Reader |
| Model-WS-Identity | Reader | Owner | Reader | Reader |
| Reporting-WS-Identity | Reader | Reader | Owner | Reader |

**Principle:** Assign the minimum role required. Use workspace identities for cross-workspace authentication rather than embedding secrets.

### How to Create & Assign (High Level)

1. Create service principal in Azure AD.
2. Grant it the required role(s) on the Fabric workspaces (use RBAC).
3. Create workspace identities in Fabric (UI or API) and add them to the required workspaces.
4. Add workspace identities to SQL DB roles where needed (for writeback or semantic model access).

---

## Post-Deployment Validation

### Post-Deployment Validation Checklist

- Notebooks attach to the correct Spark environment.
- Lakehouse schema exists and tables are accessible.
- Semantic model dataset binds to the correct SQL DB and workspace.
- Reports load and visuals render.
- Pipelines run successfully (sample run).
- Access checks: workspace identities and service principal roles validated.

---

## Quick Fixes

| Issue | Fix |
|-------|-----|
| Notebook still referencing DEV IDs | Check lakehouse_id_map and abfs replacement logic in orchestration.py. |
| Publish fails with 403 | Verify service principal has Contributor role on workspace. |
| Semantic model binding fails | Ensure TDML placeholders were replaced and workspace identity has DB access. |
| Pipeline not triggering | Check branch filters in azure-pipelines.yml. |

---

## YAML Snippet

### Sanitized YAML Snippet (Pipeline Secrets via Key Vault)

```yaml
variables:
  - group: 'ci-secrets' # variable group that references Key Vault

stages:
  - stage: DeployToProd
    jobs:
      - job: Deploy
        steps:
          - task: AzureKeyVault@2
            inputs:
              azureSubscription: '$(azureServiceConnection)'
              KeyVaultName: '$(keyVaultName)'
              SecretsFilter: 'clientSecret'
```
# fabric_workspaces
## Repository Directory Structure

The `fabric_workspaces` folder is organized by functional domains, making it easy to navigate and maintain different types of artifacts.

```
fabric_workspaces/
├── MODEL/
│   ├── 1) Database
│   ├── 2) ETL
│   ├── 3) Semantic Models
│   ├── 4) Ontology
│   └── README.md
├── ORCHESTRATION/
│   ├── 1) Database
│   ├── 2) Lakehouses
│   ├── 3) Notebooks
│   ├── 4) Pipelines
│   ├── 5) Environment
│   └── README.md
├── REPORTING/
│   ├── 1) Reports
│   └── README.md
├── WRITEBACK/
│   ├── 1) Reports
│   └── README.md
└── README.md
```

### Folder Descriptions

| Folder | Purpose | Contents |
|--------|---------|----------|
| **MODEL** | Data modeling and semantic layer | Database schemas, ETL processes, Semantic Models, Ontology definitions |
| **ORCHESTRATION** | Workflow automation and data processing | Databases, Lakehouses, Notebooks, Pipelines, Spark Environments |
| **REPORTING** | Business intelligence and analytics | Reports, Dashboards, Visualizations |
| **WRITEBACK** | Data writeback configurations | Writeback Reports, SQL target configurations |

### Organizational Benefits

- **Separation of Concerns:** Each workspace handles a specific functional domain
- **Team Collaboration:** Teams can work independently on their respective workspace
- **Scalability:** Easy to add new items within each domain
- **Maintainability:** Clear structure makes documentation and updates straightforward

---

## Pipeline Execution for Different Environments

### Overview

The pipeline dashboard displays all pipeline runs across different environments. This section explains how to monitor and execute pipelines.

### Understanding Pipeline Runs

1. **TEST_DEPLOYMENT** — Validates changes in the TEST environment
   - Triggered by changes to `azure-pipelines.yml`
   - Runs on the `release/UAT` branch

2. **PRODUCTION_DEPLOYMENT** — Deploys to PROD environment
   - Triggered by changes to `azure-pipelines.yml`
   - Runs on the `release/PROD` branch

### Monitoring Pipeline Runs

To monitor pipeline executions:

1. Navigate to the **Pipelines** dashboard
2. Click on **Recent** tab to see latest runs
3. Click on a pipeline name to view detailed logs
4. Check **Status** column for pass/fail indicator
5. Review **Duration** to identify performance issues

### Troubleshooting Failed Pipelines

| Issue | Cause | Solution |
|-------|-------|----------|
| Deploy fails with 403 error | Service principal lacks permissions | Add Contributor role to workspace |
| Notebook references DEV IDs | Configuration not patched | Verify lakehouse_id_map in config JSON |
| Semantic model binding fails | Workspace identity lacks DB access | Add workspace identity to SQL DB roles |
| Pipeline not triggering | Branch not configured | Check trigger conditions in azure-pipelines.yml |

---

## Pipeline Configuration Parameters

### Overview

The pipeline execution interface allows you to configure parameters before running a pipeline. This provides flexibility in choosing deployment environment and target workspace without modifying code.

### Pipeline Version Selection

```
Pipeline version
├── Select pipeline version by branch/tag
│   └── [feature/first_sync ▼]
│       ├── feature/other_branch
│       ├── main
│       ├── release/UAT
│       └── release/PROD
└── Select the pipeline to run by branch, commit, or tag
```

**Purpose:** Choose which branch/tag version of the pipeline to execute
- Use **feature branches** for development and testing
- Use **main** for stable releases
- Use **release/UAT** for test environment validation
- Use **release/PROD** for production deployments

### Parameters Section

#### Environment Parameter

```
environment (radio buttons)
├── ○ test    (selected by default)
└── ○ prod
```

**Purpose:** Select the target deployment environment

| Option | Use Case | Description |
|--------|----------|-------------|
| **test** | Validation & Testing | Deploy to TEST workspace for validation before production |
| **prod** | Production Deployment | Deploy to PRODUCTION workspace (requires approvals) |

**Default:** `test` (safer default to prevent accidental production deployments)

#### Workspace Parameter

```
workspace (dropdown)
├── orchestration (default)
├── model
├── reporting
└── writeback
└── all
```

**Purpose:** Select which workspace domain to deploy to

| Workspace | Contains | Deploy When |
|-----------|----------|-------------|
| **orchestration** | Pipelines, Lakehouses, Notebooks, Environments | Deploying data orchestration artifacts |
| **model** | Semantic Models, ETL, Databases | Deploying data modeling artifacts |
| **reporting** | Reports, Dashboards | Deploying reporting artifacts |
| **writeback** | Writeback configurations, SQL targets | Deploying writeback features |

### How to Execute a Pipeline

1. **Navigate** to the Pipelines dashboard
2. **Click** "New pipeline" or select an existing pipeline
3. **Choose Pipeline version** from the dropdown (branch/tag)
4. **Select Environment:**
   - `test` — for validation and testing
   - `prod` — for production deployment
5. **Select Workspace:**
   - Choose specific workspace or `all` for complete deployment
   - Deploy all artifacts to test environment for comprehensive testing
6. **Review Parameters** before execution
7. **Click "Run"** to start the pipeline
8. **Monitor** the pipeline execution in the Recent runs tab

### Best Practices for Pipeline Parameters

✅ **DO:**
- Start with `test` environment for all new changes
- Use `feature/*` branches for development
- Test in `orchestration` workspace before testing other domains
- Use release branches for production deployments
- Document why each parameter choice was made in commit messages

❌ **DON'T:**
- Skip testing in TEST environment
- Use `prod` environment without proper approvals
- Manually modify parameters in production without documentation
- Deploy from unreviewed feature branches to production
- Change workspace parameter during active production operations

### Parameter Dependency Matrix

```
Pipeline Version  | Environment | Workspace | Use Case
──────────────────┼─────────────┼───────────┼────────────────────────
feature/*         | test        | Any       | Development & Testing
main              | test        | Any       | Staging validation
release/UAT       | test        | Any       | UAT approval testing
release/PROD      | prod        | Any       | Production deployment
```
---

**Last Updated:** 2026-04-07  
**Maintainer:** Viranna Gadgoli  
**Email:** viranna119@gmail.com
