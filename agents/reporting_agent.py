import os
import json
from datetime import datetime
from llm import get_llm_client
from config import Config


class ReportingAgent:
    """
    Agent 4: Reporting Agent

    ROLE:
    - Generate deterministic execution reports
    - Summarize execution facts
    - Optionally generate AI insights (non-authoritative)

    IMPORTANT:
    - Facts always come from execution results
    - AI insights must NEVER override factual metrics
    """

    def __init__(self):
        Config.ensure_directories()
        self.llm_client = get_llm_client()

        self.system_prompt = """
You are a Senior Automation Test Engineer with 10+ years of experience in test automation.

YOUR EXPERTISE:
- Python programming for automation (expert-level)
- Playwright automation framework (primary tool)
- Test execution analysis and reporting
- Identifying patterns in test results
- Creating actionable test reports for stakeholders

YOUR ROLE AS TEST REPORTING SPECIALIST:
- Analyze test execution results from Playwright automation runs
- Generate comprehensive, professional test reports
- Provide insights on test execution patterns
- Help identify areas for improvement in automation scripts

CORE RULES:
- NEVER change or reinterpret factual results from test execution
- Clearly distinguish facts (actual results) from insights (your analysis)
- Do NOT speculate beyond provided execution data
- Focus on actionable, test-related observations
- Keep insights concise and professional
- Consider Playwright-specific execution patterns when analyzing results
- Provide recommendations for improving automation scripts

Remember: You are analyzing results from Python/Playwright automation test executions and creating reports that help improve the test automation framework.
"""

    # --------------------------------------------------
    def generate_report(self, execution_results: dict) -> dict:
        """
        Generate a comprehensive execution report.

        Args:
            execution_results: Output from ExecutionAgent

        Returns:
            Report dictionary with saved artifacts
        """

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        summary = execution_results.get("summary", {})
        detailed_results = execution_results.get("detailed_results", [])

        metrics = self._calculate_metrics(summary)
        insights = self._generate_insights(summary, detailed_results)

        overall_status = self._determine_overall_status(summary)

        report = {
            "timestamp": timestamp,
            "execution_summary": summary,
            "metrics": metrics,
            "insights": insights,
            "overall_status": overall_status,
            "json_execution_report": execution_results.get("json_report_path"),
            "project_type": execution_results.get("project_type"),
        }

        # ---------------- SAVE JSON REPORT ----------------
        report_path = os.path.join(
            Config.REPORTS_DIR,
            f"test_report_{timestamp}.json"
        )
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)

        report["report_path"] = report_path

        # ---------------- SAVE TEXT SUMMARY ----------------
        summary_text = self._generate_text_summary(report)
        summary_path = os.path.join(
            Config.REPORTS_DIR,
            f"test_report_summary_{timestamp}.txt"
        )
        with open(summary_path, "w", encoding="utf-8") as f:
            f.write(summary_text)

        report["summary_path"] = summary_path

        return report

    # --------------------------------------------------
    def _determine_overall_status(self, summary: dict) -> str:
        """
        Determine overall status using deterministic rules.
        """
        if not summary:
            return "NO_EXECUTION"

        if summary.get("failed", 0) > 0:
            return "FAILED"

        if summary.get("passed", 0) > 0:
            return "PASSED"

        return "INCONCLUSIVE"

    # --------------------------------------------------
    def _calculate_metrics(self, summary: dict) -> dict:
        """
        Calculate numeric metrics safely.
        """
        total_scenarios = summary.get("total_scenarios", 0)
        total_steps = summary.get("total_steps", 0)

        if total_scenarios == 0:
            return {}

        return {
            "scenario_pass_rate": round(
                summary.get("passed", 0) / total_scenarios * 100, 2
            ),
            "scenario_fail_rate": round(
                summary.get("failed", 0) / total_scenarios * 100, 2
            ),
            "step_pass_rate": round(
                summary.get("passed_steps", 0) / max(total_steps, 1) * 100, 2
            ),
            "step_fail_rate": round(
                summary.get("failed_steps", 0) / max(total_steps, 1) * 100, 2
            ),
        }

    # --------------------------------------------------
    def _generate_insights(
        self,
        summary: dict,
        detailed_results: list
    ) -> dict:
        """
        Generate optional AI insights.
        Insights are advisory only.
        """

        if not summary:
            return {"analysis": "No execution data available."}

        prompt = f"""
TEST EXECUTION SUMMARY:
- Total Scenarios: {summary.get('total_scenarios', 0)}
- Passed: {summary.get('passed', 0)}
- Failed: {summary.get('failed', 0)}
- Skipped: {summary.get('skipped', 0)}

TASK:
- Identify patterns or risks
- Highlight areas needing attention
- Suggest improvements limited to test automation

Do NOT speculate about application bugs.
Do NOT rewrite execution facts.
"""

        try:
            analysis = self.llm_client.generate_response(
                prompt=prompt,
                system_prompt=self.system_prompt
            )

            failures = self._extract_failures(detailed_results)

            return {
                "analysis": analysis,
                "failure_count": len(failures),
                "failures": failures[:5],
            }

        except Exception as e:
            return {
                "analysis": f"Insight generation failed: {str(e)}"
            }

    # --------------------------------------------------
    def _extract_failures(self, detailed_results: list) -> list:
        """
        Extract failed scenarios deterministically.
        """
        failures = []

        for feature in detailed_results or []:
            for scenario in feature.get("elements", []):
                if scenario.get("status", "").lower() == "failed":
                    failures.append({
                        "feature": feature.get("name"),
                        "scenario": scenario.get("name"),
                    })

        return failures

    # --------------------------------------------------
    def _generate_text_summary(self, report: dict) -> str:
        """
        Generate a human-readable summary report.
        """

        lines = [
            "=" * 80,
            "BDD TEST EXECUTION REPORT",
            "=" * 80,
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"Overall Status: {report.get('overall_status')}",
            "",
            "EXECUTION SUMMARY",
            "-" * 80,
        ]

        summary = report.get("execution_summary", {})
        if summary:
            lines.extend([
                f"Total Scenarios : {summary.get('total_scenarios', 0)}",
                f"Passed          : {summary.get('passed', 0)}",
                f"Failed          : {summary.get('failed', 0)}",
                f"Skipped         : {summary.get('skipped', 0)}",
                "",
                f"Total Steps     : {summary.get('total_steps', 0)}",
                f"Passed Steps    : {summary.get('passed_steps', 0)}",
                f"Failed Steps    : {summary.get('failed_steps', 0)}",
                f"Skipped Steps   : {summary.get('skipped_steps', 0)}",
                "",
            ])

        metrics = report.get("metrics", {})
        if metrics:
            lines.extend([
                "METRICS",
                "-" * 80,
                f"Scenario Pass Rate : {metrics.get('scenario_pass_rate', 0)}%",
                f"Scenario Fail Rate : {metrics.get('scenario_fail_rate', 0)}%",
                f"Step Pass Rate     : {metrics.get('step_pass_rate', 0)}%",
                "",
            ])

        insights = report.get("insights", {})
        if insights.get("analysis"):
            lines.extend([
                "AI INSIGHTS (ADVISORY)",
                "-" * 80,
                insights["analysis"],
                "",
            ])

        lines.extend([
            "=" * 80,
            f"JSON Report: {report.get('report_path')}",
        ])

        return "\n".join(lines)
