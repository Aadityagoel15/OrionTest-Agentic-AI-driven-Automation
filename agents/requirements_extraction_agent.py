"""
Requirements Extraction Agent

ROLE:
- Extract testable requirements from source code, documentation,
  user stories, and project files.
- Focus strictly on WHAT should be tested, not HOW it is implemented.
"""

import os
from pathlib import Path
from llm import get_llm_client
from config import Config


class RequirementsExtractionAgent:
    """
    Agent that extracts testable requirements for BDD testing.

    IMPORTANT:
    - This agent does NOT write Gherkin
    - This agent does NOT write code
    - This agent does NOT invent UI elements or workflows
    """

    # ------------------------------------------------------------------
    # SYSTEM PROMPT (PERSONA)
    # ------------------------------------------------------------------
    SYSTEM_PROMPT = """
You are a Senior Automation Test Engineer with 10+ years of experience in test automation.

YOUR EXPERTISE:
- Python programming for automation (expert-level)
- Playwright automation framework (primary tool)
- BDD (Behavior-Driven Development) methodologies
- Test requirement analysis and extraction
- Creating maintainable, scalable automation frameworks

YOUR ROLE AS REQUIREMENTS EXTRACTION SPECIALIST:
- Extract ONLY testable behaviors from various sources
- Focus on user actions and observable outcomes
- Translate business requirements into testable scenarios
- Identify what can be verified through automation

CORE RESPONSIBILITIES:
- Extract ONLY testable behaviors
- Focus on user actions and observable outcomes
- Ignore implementation details (code structure, libraries, frameworks)
- Do NOT invent UI elements, API endpoints, or workflows
- Do NOT write code or step definitions at this stage
- Do NOT write Playwright, XPath, or selectors yet

RULES:
- Think in terms of "what can be verified by a test using Playwright"
- Prefer clear, atomic requirements
- Avoid vague, abstract, or non-testable statements
- If information is missing, do NOT guess
- Consider how requirements will translate to automated test scenarios

OUTPUT STYLE:
- Concise and structured
- Test-oriented and actionable
- Suitable for later conversion into BDD feature files
- Professional automation engineer perspective
"""

    def __init__(self):
        self.llm_client = get_llm_client()

    # ------------------------------------------------------------------
    # SOURCE CODE ANALYSIS
    # ------------------------------------------------------------------
    def extract_from_code(self, code_content: str, file_path: str = None) -> str:
        """
        Extract testable requirements from source code.

        Args:
            code_content: Source code content
            file_path: Optional file path for context

        Returns:
            Extracted requirements text
        """
        file_type = Path(file_path).suffix if file_path else "unknown"

        prompt = f"""
Analyze the following source code and extract ONLY testable requirements.

FILE TYPE: {file_type}

CODE (PARTIAL):
{code_content[:5000]}

EXTRACT:
- User-visible behaviors
- Functional outcomes
- Error or failure conditions
- Validation rules
- Edge cases that should be tested

DO NOT:
- Describe internal functions or classes
- Mention implementation details
- Assume UI or API behavior not explicitly visible

FORMAT OUTPUT AS:
- A bullet list of clear, testable requirements
"""

        try:
            return self.llm_client.generate_response(prompt, self.SYSTEM_PROMPT)
        except Exception as e:
            return f"Error extracting requirements from code: {str(e)}"

    # ------------------------------------------------------------------
    # DOCUMENTATION ANALYSIS
    # ------------------------------------------------------------------
    def extract_from_documentation(self, doc_content: str, doc_type: str = "Documentation") -> str:
        """
        Extract requirements from documentation files.
        """
        prompt = f"""
Analyze the following {doc_type} and extract testable requirements.

DOCUMENT CONTENT:
{doc_content[:5000]}

EXTRACT:
- Features described
- User-facing behavior
- Functional requirements
- Acceptance conditions (if present)

DO NOT:
- Rewrite documentation
- Add assumptions
- Invent missing behavior

FORMAT OUTPUT AS:
- Clear, testable requirements suitable for BDD
"""

        try:
            return self.llm_client.generate_response(prompt, self.SYSTEM_PROMPT)
        except Exception as e:
            return f"Error extracting requirements from documentation: {str(e)}"

    # ------------------------------------------------------------------
    # USER STORY ANALYSIS
    # ------------------------------------------------------------------
    def extract_from_user_stories(self, user_stories: str) -> str:
        """
        Normalize and extract requirements from user stories text.
        """
        prompt = f"""
Analyze the following user stories and extract testable requirements.

USER STORIES:
{user_stories}

TASK:
- Identify the underlying testable behaviors
- Extract acceptance criteria where implied
- Highlight edge or failure scenarios

FORMAT OUTPUT AS:
- A structured list of testable requirements
- Each requirement must be verifiable by automation
"""

        try:
            return self.llm_client.generate_response(prompt, self.SYSTEM_PROMPT)
        except Exception as e:
            return f"Error processing user stories: {str(e)}"

    # ------------------------------------------------------------------
    # PROJECT DIRECTORY SCAN
    # ------------------------------------------------------------------
    def extract_from_project_directory(self, project_path: str, file_extensions: list = None) -> dict:
        """
        Extract requirements from a project directory.

        Returns:
            Dictionary containing per-file and combined requirements
        """
        if file_extensions is None:
            file_extensions = ['.py', '.js', '.ts', '.java', '.md', '.txt', '.yaml', '.yml', '.json']

        project_path = Path(project_path)
        if not project_path.exists():
            return {"error": f"Project path does not exist: {project_path}"}

        ignore_patterns = {
            '__pycache__', '.git', 'node_modules', 'venv', 'env',
            '.pytest_cache', 'coverage', 'dist', 'build', '.idea', '.vscode'
        }

        extracted = {
            "project_path": str(project_path),
            "requirements_by_file": {},
            "combined_requirements": ""
        }

        collected_requirements = []

        # -------- Documentation first --------
        for doc_file in project_path.rglob("*"):
            if any(p in str(doc_file) for p in ignore_patterns):
                continue

            if doc_file.suffix.lower() in {'.md', '.txt'} and doc_file.is_file():
                try:
                    content = doc_file.read_text(encoding="utf-8", errors="ignore")
                    if len(content) > 200:
                        reqs = self.extract_from_documentation(content, doc_file.name)
                        extracted["requirements_by_file"][doc_file.name] = reqs
                        collected_requirements.append(f"## {doc_file.name}\n{reqs}")
                except Exception:
                    continue

        # -------- Source code (top relevant files) --------
        code_files = [
            f for f in project_path.rglob("*")
            if f.is_file()
            and f.suffix in file_extensions
            and not any(p in str(f) for p in ignore_patterns)
            and f.stat().st_size < 100_000
        ]

        for code_file in sorted(code_files, key=lambda x: x.stat().st_size, reverse=True)[:10]:
            try:
                content = code_file.read_text(encoding="utf-8", errors="ignore")
                if len(content) > 300:
                    reqs = self.extract_from_code(content, str(code_file))
                    extracted["requirements_by_file"][code_file.name] = reqs
                    collected_requirements.append(f"## {code_file.name}\n{reqs}")
            except Exception:
                continue

        extracted["combined_requirements"] = "\n\n".join(collected_requirements)
        return extracted

    # ------------------------------------------------------------------
    # API SPEC EXTRACTION
    # ------------------------------------------------------------------
    def extract_from_api_spec(self, api_spec_content: str, spec_type: str = "API") -> str:
        """
        Extract requirements from API specifications.
        """
        prompt = f"""
Analyze the following {spec_type} specification and extract testable API requirements.

API SPEC (PARTIAL):
{api_spec_content[:5000]}

EXTRACT:
- Endpoints and supported operations
- Success scenarios
- Error scenarios
- Validation rules
- Authentication requirements (if stated)

FORMAT OUTPUT AS:
- Testable API requirements suitable for BDD-style testing
"""

        try:
            return self.llm_client.generate_response(prompt, self.SYSTEM_PROMPT)
        except Exception as e:
            return f"Error extracting requirements from API spec: {str(e)}"

    # ------------------------------------------------------------------
    # SAVE REQUIREMENTS
    # ------------------------------------------------------------------
    def save_extracted_requirements(self, requirements: str, output_file: str = None) -> str:
        """
        Save extracted requirements to a file.
        """
        Config.ensure_directories()

        if not output_file:
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = os.path.join(
                Config.REQUIREMENTS_DIR,
                f"extracted_requirements_{timestamp}.txt"
            )

        with open(output_file, "w", encoding="utf-8") as f:
            f.write(requirements)

        return output_file
