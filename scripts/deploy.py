import sys
import os
from orchestration import main as orchestration_main
from report import main as report_main
from model import main as model_main
from writeback import main as writeback_main

def deploy_all(env):
    print(f"Deploying ALL workspaces for {env}")
    orchestration_main()
    report_main()
    model_main()
    writeback_main()

def main():
    if len(sys.argv) < 3:
        print("Usage: python deploy.py <environment> <workspace>")
        sys.exit(1)

    env = sys.argv[1]        # "test" or "prod"
    workspace = sys.argv[2]  # "all", "orchestration", "reporting", "model", "writeback"

    if workspace == "all":
        deploy_all(env)
    elif workspace == "orchestration":
        print(f"Deploying orchestration workspace for {env}")
        orchestration_main()
    elif workspace == "reporting":
        print(f"Deploying reporting workspace for {env}")
        report_main()
    elif workspace == "model":
        print(f"Deploying model workspace for {env}")
        model_main()
    elif workspace == "writeback":
        print(f"Deploying writeback workspace for {env}")
        writeback_main()
    else:
        print(f"Unknown workspace: {workspace}")
        sys.exit(1)

if __name__ == "__main__":
    main()
