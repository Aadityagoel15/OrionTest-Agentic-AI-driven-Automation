import os
import json
from datetime import datetime
from llm import get_llm_client
from config import Config


class DefectAgent:
    """
    Agent 5: Defect Identification Agent

    ROLE:
    - Analyze FAILED test executions only
    - Identify potential defects vs test issues
    - Produce deterministic, review-ready defect reports

    IMPORTANT:
    - Facts come ONLY from execution results
    - LLM is advisory, never authoritative
    - No defects are created without an actual failed scenario
    """

    def __init__(self):
        Config.ensure_directories()
        self.llm_client = get_llm_client()

        self.system_prompt = """
You are a Senior Automation Test Engineer with 10+ years of experience in test automation.

YOUR EXPERTISE:
- Python programming for automation (expert-level)
- Playwright automation framework (primary tool)
- Test failure analysis and root cause investigation
- Defect identification and triage
- Distinguishing automation script issues from actual product defects

YOUR ROLE AS DEFECT ANALYST:
- Analyze failed test executions from Playwright automation runs
- Identify root causes of test failures
- Distinguish between product defects and test automation issues
- Provide technical, actionable defect reports

CORE RULES:
- Use ONLY the provided failure data from test execution
- Consider Playwright-specific failure patterns (timeouts, element not found, etc.)
- Do NOT invent steps, screens, or flows not present in execution logs
- Distinguish product defects from test script issues (selector problems, timing issues, etc.)
- Keep analysis technical, concise, and focused on automation testing
- Do NOT speculate beyond evidence from execution results
- Consider common Playwright automation pitfalls when analyzing failures

Your output must be structured, actionable, and suitable for both developers and QA teams working with Python/Playwright automation.
"""

    # --------------------------------------------------
    # 🔒 SAFETY NORMALIZER
    # --------------------------------------------------
    def _safe_str(self, value) -> str:
        if value is None:
            return "N/A"
        if isinstance(value, list):
            return "\n".join(map(str, value))
        return str(value)

    # --------------------------------------------------
    def identify_defects(
        self,
        execution_results: dict,
        test_report: dict = None
    ) -> dict:
        """
        Identify defects from execution results.

        Args:
            execution_results: Output from ExecutionAgent
            test_report: Optional reporting agent output

        Returns:
            Defect analysis result dictionary
        """

        detailed_results = execution_results.get("detailed_results", [])
        failures = self._extract_failures(detailed_results)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # ---------------- NO FAILURES ----------------
        if not failures:
            result = self._no_defects_result(timestamp)
            self._persist_defect_artifacts(result, timestamp)
            return result

        # ---------------- ANALYZE FAILURES ----------------
        analyzed = []
        for failure in failures:
            defect = self._analyze_failure(failure)
            if defect:
                analyzed.append(defect)

        unique_defects = self._deduplicate_defects(analyzed)

        result = {
            "timestamp": timestamp,
            "defects_found": len(unique_defects),
            "defects": unique_defects,
            "severity_distribution": self._calculate_severity_distribution(
                unique_defects
            ),
        }

        self._persist_defect_artifacts(result, timestamp)
        return result

    # --------------------------------------------------
    def _no_defects_result(self, timestamp: str) -> dict:
        return {
            "timestamp": timestamp,
            "defects_found": 0,
            "defects": [],
            "severity_distribution": {
                "Critical": 0,
                "High": 0,
                "Medium": 0,
                "Low": 0,
            },
            "message": "No failed scenarios detected. No defects identified.",
        }

    # --------------------------------------------------
    def _extract_failures(self, detailed_results: list) -> list:
        """
        Extract FAILED scenarios only.
        """
        failures = []

        for feature in detailed_results or []:
            feature_name = feature.get("name", "Unknown Feature")

            for scenario in feature.get("elements", []):
                if scenario.get("status", "").lower() != "failed":
                    continue

                failed_steps = [
                    step for step in scenario.get("steps", [])
                    if step.get("result", {})
                    .get("status", "")
                    .lower() == "failed"
                ]

                if not failed_steps:
                    continue

                last_failed = failed_steps[-1]

                failures.append({
                    "feature": feature_name,
                    "scenario": scenario.get("name", "Unknown Scenario"),
                    "failed_step": last_failed.get("name", ""),
                    "error_message": last_failed
                        .get("result", {})
                        .get("error_message", ""),
                    "all_steps": scenario.get("steps", []),
                })

        return failures

    # --------------------------------------------------
    def _analyze_failure(self, failure: dict) -> dict:
        """
        Analyze a single failure using LLM (advisory).
        """

        prompt = f"""
FAILED SCENARIO ANALYSIS

Feature: {failure.get('feature')}
Scenario: {failure.get('scenario')}
Failed Step: {failure.get('failed_step')}
Error Message: {failure.get('error_message')}

TASK:
- Determine if this is a PRODUCT DEFECT or TEST ISSUE
- Assign severity conservatively
- Describe expected vs actual behavior
- Suggest a fix if obvious

Respond ONLY in JSON with:
{{
  "title": "...",
  "severity": "Critical|High|Medium|Low",
  "category": "Functional|UI|Integration|Test Issue",
  "description": "...",
  "expected_behavior": "...",
  "actual_behavior": "...",
  "root_cause_analysis": "...",
  "suggested_fix": "..."
}}
"""

        try:
            response = self.llm_client.generate_structured_response(
                prompt=prompt,
                system_prompt=self.system_prompt
            )

            if not isinstance(response, dict):
                return None

            return {
                "id": f"DEF-{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
                "feature": failure.get("feature"),
                "scenario": failure.get("scenario"),
                "failed_step": failure.get("failed_step"),
                "error_message": failure.get("error_message"),
                "title": response.get("title", "Test Failure"),
                "severity": response.get("severity", "Medium"),
                "category": response.get("category", "Test Issue"),
                "description": response.get("description", ""),
                "expected_behavior": response.get("expected_behavior", ""),
                "actual_behavior": response.get("actual_behavior", ""),
                "root_cause_analysis": response.get("root_cause_analysis", ""),
                "suggested_fix": response.get("suggested_fix", ""),
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            # Hard fallback — never crash pipeline
            return {
                "id": f"DEF-{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
                "feature": failure.get("feature"),
                "scenario": failure.get("scenario"),
                "failed_step": failure.get("failed_step"),
                "title": "Failure Analysis Error",
                "severity": "Medium",
                "category": "Test Issue",
                "description": str(e),
                "timestamp": datetime.now().isoformat(),
            }

    # --------------------------------------------------
    def _deduplicate_defects(self, defects: list) -> list:
        """
        Deduplicate defects by normalized title.
        """
        seen = set()
        unique = []

        for defect in defects:
            key = self._safe_str(defect.get("title")).lower()
            if key not in seen:
                seen.add(key)
                unique.append(defect)

        return unique

    # --------------------------------------------------
    def _calculate_severity_distribution(self, defects: list) -> dict:
        distribution = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0}
        for defect in defects:
            severity = defect.get("severity", "Medium")
            if severity in distribution:
                distribution[severity] += 1
        return distribution

    # --------------------------------------------------
    def _persist_defect_artifacts(self, result: dict, timestamp: str):
        """
        Persist JSON + text defect reports.
        """

        json_path = os.path.join(
            Config.REPORTS_DIR, f"defects_{timestamp}.json"
        )
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)

        result["defects_file_path"] = json_path

        text_report = self._generate_text_report(result)
        txt_path = os.path.join(
            Config.REPORTS_DIR, f"defect_report_{timestamp}.txt"
        )
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(text_report)

        result["defect_report_path"] = txt_path

    # --------------------------------------------------
    def _generate_text_report(self, result: dict) -> str:
        """
        Human-readable defect report.
        """

        lines = [
            "=" * 80,
            "DEFECT REPORT",
            "=" * 80,
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"Total Defects: {result.get('defects_found', 0)}",
            "",
            "SEVERITY DISTRIBUTION",
            "-" * 80,
        ]

        for sev, count in result.get("severity_distribution", {}).items():
            lines.append(f"{sev}: {count}")

        lines.append("")
        lines.append("DEFECT DETAILS")
        lines.append("-" * 80)

        for defect in result.get("defects", []):
            lines.extend([
                "",
                f"ID: {self._safe_str(defect.get('id'))}",
                f"Title: {self._safe_str(defect.get('title'))}",
                f"Severity: {self._safe_str(defect.get('severity'))}",
                f"Category: {self._safe_str(defect.get('category'))}",
                f"Feature: {self._safe_str(defect.get('feature'))}",
                f"Scenario: {self._safe_str(defect.get('scenario'))}",
                "",
                "Description:",
                self._safe_str(defect.get("description")),
                "",
                "Expected Behavior:",
                self._safe_str(defect.get("expected_behavior")),
                "",
                "Actual Behavior:",
                self._safe_str(defect.get("actual_behavior")),
                "",
                "Root Cause:",
                self._safe_str(defect.get("root_cause_analysis")),
                "",
                "Suggested Fix:",
                self._safe_str(defect.get("suggested_fix")),
                "",
                "-" * 80,
            ])

        return "\n".join(lines)
