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
    config_path = os.path.join(config_dir, f"{env_name}_model.json")
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)

def get_access_token():
    credential = ClientSecretCredential(
        tenant_id=os.environ["AZURE_TENANT_ID"],
        client_id=os.environ["AZURE_CLIENT_ID"],
        client_secret=os.environ["AZURE_CLIENT_SECRET"]
    )
    return credential.get_token("https://analysis.windows.net/powerbi/api/.default").token, credential

def rewrite_tmdl_connections(repo_path, config):
    env = config["environment"].upper().split("_")[0]  # DEV / TEST / PROD
    mapping = config.get("db_mapping", {}).get(env)
    if not mapping:
        print(f"[TMDL Patch] No mapping found for {env}")
        return

    ws_id = mapping["workspace_id"]
    db_id = mapping["database_id"]

    sm_root = os.path.join(repo_path, "3) Semantic Models")
    for root, _, files in os.walk(sm_root):
        for fname in files:
            if fname.endswith(".tmdl"):
                fpath = os.path.join(root, fname)
                with open(fpath, "r", encoding="utf-8") as f:
                    content = f.read()
                new_content = re.sub(
                    r"https://onelake\.dfs\.fabric\.microsoft\.com/[a-f0-9\-]+/[a-f0-9\-]+",
                    f"https://onelake.dfs.fabric.microsoft.com/{ws_id}/{db_id}",
                    content
                )
                if new_content != content:
                    with open(fpath, "w", encoding="utf-8") as f:
                        f.write(new_content)
                    print(f"[TMDL Patch] Updated connection in {fpath}")

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

    # Only copy items explicitly listed in JSON
    for db in filters.get("SQLDatabase", []):
        copy_item(os.path.join(root, "1) Database", f"{db}.SQLDatabase"),
                  os.path.join(temp_dir, "1) Database", f"{db}.SQLDatabase"),
                  f"Database {db}")

    for udf in filters.get("UserDataFunction", []):
        copy_item(os.path.join(root, "2) ETL", f"{udf}.UserDataFunction"),
                  os.path.join(temp_dir, "2) ETL", f"{udf}.UserDataFunction"),
                  f"UDF {udf}")

    for sm in filters.get("SemanticModel", []):
        copy_item(os.path.join(root, "3) Semantic Models", f"{sm}.SemanticModel"),
                  os.path.join(temp_dir, "3) Semantic Models", f"{sm}.SemanticModel"),
                  f"Semantic Model {sm}")

    for onto in filters.get("Ontology", []):
        copy_item(os.path.join(root, "4) Ontology", f"{onto}.Ontology"),
                  os.path.join(temp_dir, "4) Ontology", f"{onto}.Ontology"),
                  f"Ontology {onto}")

    return temp_dir

def main():
    if len(sys.argv) < 2:
        print("Usage: python model.py <environment>")
        sys.exit(1)

    env = sys.argv[1]
    config = load_env_config(env)
    workspace_id = config["workspace_id"]

    token, credential = get_access_token()

    # Build filtered repo containing only whitelisted items
    repo_path = build_filtered_repo(config)
    rewrite_tmdl_connections(repo_path, config)

    workspace = FabricWorkspace(
        workspace_id=workspace_id,
        repository_directory=repo_path,  # filtered repo only
        item_type_in_scope=config.get("item_type_in_scope", []),
        item_name_filter=config.get("item_name_filter", {}),
        environment=config["environment"],
        token_credential=credential
    )

    print(f"Deploying Model workspace → {workspace_id}")
    publish_all_items(workspace)

if __name__ == "__main__":
    main()
