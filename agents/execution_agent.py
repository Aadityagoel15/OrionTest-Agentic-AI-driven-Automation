"""
Agent 3: Execution Agent

ROLE:
- Execute BDD tests using the Behave framework
- Support API & WEB (Playwright)
- Collect raw execution results ONLY
"""

import os
import subprocess
import json
import time
from datetime import datetime
from config import Config, ProjectType, ExecutionMode


class ExecutionAgent:
    """Executes BDD tests deterministically"""

    def __init__(self):
        Config.ensure_directories()
        self.reports_dir = Config.REPORTS_DIR
        self.base_dir = Config.BASE_DIR

    # ------------------------------------------------------------------
    def execute_tests(
        self,
        feature_file: str = None,
        tags: list = None,
        project_type: str = ProjectType.API
    ) -> dict:

        start_time = time.time()

        # --------------------------------------------------
        # CRITICAL: Set execution mode to PROJECT for real test execution
        # This ensures environment.py creates the browser/page context
        # --------------------------------------------------
        Config.set_execution_mode(ExecutionMode.PROJECT)
        # Also set in environment for subprocess
        os.environ["BDD_EXECUTION_MODE"] = ExecutionMode.PROJECT

        # --------------------------------------------------
        # Build Behave command
        # --------------------------------------------------
        cmd = ["behave", "--no-capture", "--no-capture-stderr"]

        # Feature selection
        if feature_file:
            feature_path = (
                feature_file
                if os.path.isabs(feature_file)
                else os.path.join(Config.FEATURES_DIR, feature_file)
            )
            cmd.append(feature_path)
        else:
            cmd.append(Config.FEATURES_DIR)

        # Tags
        if tags:
            tag_expr = " and ".join(f"@{tag}" for tag in tags)
            cmd.extend(["--tags", tag_expr])

        # base_url injection
        base_url = (
            os.getenv("BEHAVE_USERDATA_BASE_URL")
            or os.getenv("BASE_URL")
        )
        if base_url:
            cmd.extend(["-D", f"base_url={base_url}"])

        # WEB guard
        if project_type == ProjectType.WEB:
            cmd.extend(["-D", "ui=true"])

        # Reporting
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        json_report = os.path.join(
            self.reports_dir,
            f"execution_report_{timestamp}.json"
        )

        cmd.extend(["-f", "json.pretty", "-o", json_report])

        # --------------------------------------------------
        # Execute
        # --------------------------------------------------
        try:
            result = subprocess.run(
                cmd,
                cwd=self.base_dir,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env={**os.environ, "PYTHONUTF8": "1"},
                timeout=3600
            )

            duration = round(time.time() - start_time, 2)

            # Parse JSON report if it exists
            detailed_results = []
            summary = {}
            
            if os.path.exists(json_report):
                try:
                    with open(json_report, "r", encoding="utf-8") as f:
                        json_data = json.load(f)
                        detailed_results = json_data if isinstance(json_data, list) else [json_data]
                        
                        # Extract summary from JSON
                        if detailed_results:
                            feature_data = detailed_results[0]
                            elements = feature_data.get("elements", [])
                            
                            scenarios = [e for e in elements if e.get("type") == "scenario"]
                            total_scenarios = len(scenarios)

                            # Count only executed steps (those with a result) to avoid double-counting background definitions
                            total_steps = sum(
                                1
                                for e in scenarios
                                for step in e.get("steps", [])
                                if step.get("result")
                            )
                            
                            passed_scenarios = len([e for e in scenarios if e.get("status") == "passed"])
                            failed_scenarios = len([e for e in scenarios if e.get("status") == "failed"])
                            skipped_scenarios = len([e for e in scenarios if e.get("status") == "skipped"])
                            
                            passed_steps = sum(
                                1 for e in scenarios 
                                for step in e.get("steps", []) 
                                if step.get("result", {}).get("status") == "passed"
                            )
                            failed_steps = sum(
                                1 for e in scenarios 
                                for step in e.get("steps", []) 
                                if step.get("result", {}).get("status") == "failed"
                            )
                            skipped_steps = sum(
                                1 for e in scenarios 
                                for step in e.get("steps", []) 
                                if step.get("result", {}).get("status") == "skipped"
                            )
                            
                            summary = {
                                "total_scenarios": total_scenarios,
                                "passed": passed_scenarios,
                                "failed": failed_scenarios,
                                "skipped": skipped_scenarios,
                                "total_steps": total_steps,
                                "passed_steps": passed_steps,
                                "failed_steps": failed_steps,
                                "skipped_steps": skipped_steps,
                            }
                except Exception as e:
                    # If JSON parsing fails, create basic summary from stdout
                    summary = {
                        "total_scenarios": 0,
                        "passed": 0,
                        "failed": 0,
                        "skipped": 0,
                        "total_steps": 0,
                        "passed_steps": 0,
                        "failed_steps": 0,
                        "skipped_steps": 0,
                    }

            execution_results = {
                "command": " ".join(cmd),
                "working_directory": self.base_dir,
                "status_code": result.returncode,
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "timestamp": timestamp,
                "duration_seconds": duration,
                "project_type": project_type,
                "json_report_path": json_report if os.path.exists(json_report) else None,
                "detailed_results": detailed_results,
                "summary": summary,
            }

            return execution_results

        except subprocess.TimeoutExpired:
            return {
                "command": " ".join(cmd),
                "working_directory": self.base_dir,
                "status_code": -1,
                "success": False,
                "stdout": "",
                "stderr": "Test execution timed out after 3600 seconds",
                "timestamp": timestamp,
                "duration_seconds": 3600,
                "project_type": project_type,
                "json_report_path": None,
                "detailed_results": [],
                "summary": {},
            }
        except Exception as e:
            return {
                "command": " ".join(cmd),
                "working_directory": self.base_dir,
                "status_code": -1,
                "success": False,
                "stdout": "",
                "stderr": str(e),
                "timestamp": timestamp,
                "duration_seconds": round(time.time() - start_time, 2),
                "project_type": project_type,
                "json_report_path": None,
                "detailed_results": [],
                "summary": {},
            }



