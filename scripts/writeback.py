import sys
import re
import os
import json
import tempfile
import shutil
from azure.identity import ClientSecretCredential
from fabric_cicd import FabricWorkspace, publish_all_items

def load_env_config(env_name):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_dir = os.path.join(script_dir, "..", "config")
    config_path = os.path.join(config_dir, f"{env_name}_writeback.json")
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)

def get_access_token():
    credential = ClientSecretCredential(
        tenant_id=os.environ["AZURE_TENANT_ID"],
        client_id=os.environ["AZURE_CLIENT_ID"],
        client_secret=os.environ["AZURE_CLIENT_SECRET"]
    )
    return credential.get_token("https://analysis.windows.net/powerbi/api/.default").token, credential

def rewrite_report_connections(repo_path, config):
    env = config["environment"].upper().split("_")[0]  # DEV / TEST / PROD
    mapping = config.get("report_mapping", {}).get(env)
    if not mapping:
        print(f"[Report Patch] No mapping found for {env}")
        return

    conn_name = mapping["connection_name"]
    sm_id = mapping["semantic_model_id"]

    reports_root = os.path.join(repo_path, "1) Reports")
    for root, _, files in os.walk(reports_root):
        for fname in files:
            if fname == "definition.pbir":
                fpath = os.path.join(root, fname)
                with open(fpath, "r", encoding="utf-8") as f:
                    content = json.load(f)

                # Update connection string
                conn_str = content["datasetReference"]["byConnection"]["connectionString"]
                # Replace workspace name
                conn_str = re.sub(r"Data Source=powerbi://api\.powerbi\.com/v1\.0/myorg/[^;]+",
                                  f"Data Source=powerbi://api.powerbi.com/v1.0/myorg/{conn_name}",
                                  conn_str)
                # Replace semantic model id
                conn_str = re.sub(r"semanticmodelid=[a-f0-9\-]+",
                                  f"semanticmodelid={sm_id}",
                                  conn_str)

                content["datasetReference"]["byConnection"]["connectionString"] = conn_str

                with open(fpath, "w", encoding="utf-8") as f:
                    json.dump(content, f, indent=2)

                print(f"[Report Patch] Updated connection in {fpath}")

def build_filtered_repo(config):
    root = config["repository_root"]
    temp_dir = tempfile.mkdtemp()
    filters = config.get("item_name_filter", {})

    def copy_item(src, dst, label):
        if not os.path.exists(src):
            print(f"[WARN] {label} not found at {src}")
            return
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if os.path.isdir(src):
            shutil.copytree(src, dst, dirs_exist_ok=True)
        else:
            shutil.copy2(src, dst)
        print(f"[OK] Copied {label}")

    # Only copy reports listed in JSON
    for rpt in filters.get("Report", []):
        copy_item(os.path.join(root, "1) Reports", f"{rpt}.Report"),
                  os.path.join(temp_dir, "1) Reports", f"{rpt}.Report"),
                  f"Report {rpt}")

    return temp_dir

def main():
    if len(sys.argv) < 2:
        print("Usage: python writeback.py <environment>")
        sys.exit(1)

    env = sys.argv[1]
    config = load_env_config(env)
    workspace_id = config["workspace_id"]

    token, credential = get_access_token()

    # Build filtered repo containing only whitelisted reports
    repo_path = build_filtered_repo(config)
    rewrite_report_connections(repo_path, config)

    workspace = FabricWorkspace(
        workspace_id=workspace_id,
        repository_directory=repo_path,
        item_type_in_scope=config.get("item_type_in_scope", []),
        item_name_filter=config.get("item_name_filter", {}),
        environment=config["environment"],
        token_credential=credential
    )

    print(f"Deploying Writeback workspace → {workspace_id}")
    publish_all_items(workspace)

if __name__ == "__main__":
    main()
