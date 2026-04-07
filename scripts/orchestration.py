import sys
import os
import json
import tempfile
import shutil
import re
from azure.identity import ClientSecretCredential
from fabric_cicd import FabricWorkspace, publish_all_items

def load_env_config(env_name):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_dir = os.path.join(script_dir, "..", "config")
    config_path = os.path.join(config_dir, f"{env_name}_orchestration.json")
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)

def get_access_token():
    credential = ClientSecretCredential(
        tenant_id=os.environ["AZURE_TENANT_ID"],
        client_id=os.environ["AZURE_CLIENT_ID"],
        client_secret=os.environ["AZURE_CLIENT_SECRET"]
    )
    return credential.get_token("https://analysis.windows.net/powerbi/api/.default").token, credential

def rewrite_all_notebook_paths(repo_path, env_name):
    config = load_env_config(env_name)
    workspace_id = config.get("workspace_id")
    env = config["environment"].upper().split("_")[0]  # DEV / TEST / PROD

    db_map = config.get("db_mapping", {}).get(env, {})
    lh_map = config.get("lakehouse_id_map", {}).get(env, {})
    spark_map = config.get("spark_environment_map", {})

    notebook_root = os.path.join(repo_path, "3) Notebooks")
    if not os.path.exists(notebook_root):
        print("[Notebook Patch] No notebook directory found.")
        return
        
    for root, _, files in os.walk(notebook_root):
        for fname in files:
            file_path = os.path.join(root, fname)
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    original_lines = f.readlines()
            except Exception as e:
                print(f"[Notebook Patch] Skipped {file_path} due to error: {e}")
                continue

            modified_lines = []
            changes_made = False

            for line in original_lines:
                updated = line

                # Replace spark environmentId
                if env in spark_map:
                    new_env_id = spark_map[env]
                    updated = re.sub(
                        r'"environmentId":\s*"[a-f0-9\-]+"',
                        f'"environmentId": "{new_env_id}"',
                        updated
                    )
                    if updated != line:
                        changes_made = True

                # Replace lakehouse GUIDs
                for old_id, logical_name in config.get("lakehouse_id_map", {}).get("DEV", {}).items():
                    if old_id in updated:
                        # Find the new GUID for this logical name in current env
                        new_id = [k for k,v in lh_map.items() if v == logical_name]
                        if new_id:
                            updated = updated.replace(old_id, new_id[0])
                            changes_made = True

                # Replace ABFS workspace IDs
                abfs_pattern = r'abfss://([a-f0-9\-]+)@onelake\.dfs\.fabric\.microsoft\.com/([a-f0-9\-]+)'
                matches = re.findall(abfs_pattern, updated)
                for ws_id, lh_id in matches:
                    if ws_id != workspace_id:
                        updated = updated.replace(ws_id, workspace_id)
                        changes_made = True

                # Replace server_name
                if "server_name" in updated and "server_name" in db_map:
                    updated = re.sub(r"server_name\s*=\s*'.*'",
                                     f"server_name = '{db_map['server_name']}'",
                                     updated)
                    changes_made = True

                # Replace database_name
                if "database_name" in updated and "database_name" in db_map:
                    updated = re.sub(r"database_name\s*=\s*'.*'",
                                     f"database_name = '{db_map['database_name']}'",
                                     updated)
                    changes_made = True

                # Replace ENV
                if "ENV" in updated:
                    updated = re.sub(r'ENV\s*=\s*".*"',
                                     f'ENV = "{env}"',
                                     updated)
                    changes_made = True

                modified_lines.append(updated)

            if changes_made:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.writelines(modified_lines)
                print(f"[Notebook Patch] Updated: {file_path}")


def build_filtered_repo(config):
    root = config["repository_root"]
    temp_dir = tempfile.mkdtemp()
    filters = config.get("item_name_filter", {})

    def copy_item(src, dst, label):
        if not os.path.exists(src):
            print(f"ERROR: {label} not found at {src}")
            sys.exit(1)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if os.path.isdir(src):
            shutil.copytree(src, dst, dirs_exist_ok=True)
        else:
            shutil.copy2(src, dst)
        print(f"[OK] {label} found at {src}")

    for lh in filters.get("Lakehouse", []):
        copy_item(os.path.join(root, "2) Lakehouses", f"{lh}.Lakehouse"),
                  os.path.join(temp_dir, "2) Lakehouses", f"{lh}.Lakehouse"),
                  f"Lakehouse {lh}")

    for nb in filters.get("Notebook", []):
        copy_item(os.path.join(root, "3) Notebooks", f"{nb}.Notebook"),
                  os.path.join(temp_dir, "3) Notebooks", f"{nb}.Notebook"),
                  f"Notebook {nb}")

    for pl in filters.get("DataPipeline", []):
        copy_item(os.path.join(root, "4) Pipelines", f"{pl}.DataPipeline"),
                  os.path.join(temp_dir, "4) Pipelines", f"{pl}.DataPipeline"),
                  f"Pipeline {pl}")

    for env in filters.get("Environment", []):
        copy_item(os.path.join(root, "5) Environment", f"{env}.Environment"),
                  os.path.join(temp_dir, "5) Environment", f"{env}.Environment"),
                  f"Environment {env}")

    return temp_dir

def main():
    if len(sys.argv) < 2:
        print("Usage: python orchestration.py <environment>")
        sys.exit(1)

    env = sys.argv[1]
    config = load_env_config(env)
    workspace_id = config["workspace_id"]

    token, credential = get_access_token()

    repo_path = build_filtered_repo(config)
    rewrite_all_notebook_paths(repo_path, env)

    workspace = FabricWorkspace(
        workspace_id=workspace_id,
        repository_directory=repo_path,
        item_type_in_scope=config.get("item_type_in_scope", []),
        item_name_filter=config.get("item_name_filter", {}),
        environment=config["environment"],
        token_credential=credential
    )

    print(f"Deploying Orchestration workspace → {workspace_id}")
    publish_all_items(workspace)

if __name__ == "__main__":
    main()
