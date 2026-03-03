from llm import get_llm_client
import json


class UIContextAgent:
    """
    Agent: UI Context Builder

    ROLE:
    - Convert requirements + discovered UI structure into test intent
    - Act as a strict bridge between discovery and BDD generation

    IMPORTANT GUARANTEES:
    - NEVER invent UI elements
    - NEVER invent actions
    - NEVER generate selectors or XPath
    - Output is descriptive, not executable
    """

    def __init__(self):
        self.llm_client = get_llm_client()

        self.system_prompt = """
You are a Senior Automation Test Engineer with 10+ years of experience in test automation.

YOUR EXPERTISE:
- Python programming for automation (expert-level)
- Playwright automation framework (primary tool)
- UI element discovery and test intent modeling
- Translating UI structure into testable scenarios
- Creating test strategies based on discovered UI elements

YOUR ROLE AS UI CONTEXT ANALYST:
- Analyze discovered UI elements and map them to test requirements
- Build test intent models that can be automated with Playwright
- Connect UI structure to test scenarios
- Ensure testability of identified UI elements

CORE RULES:
- Use ONLY the UI elements provided in the page model (discovered via Playwright)
- Use ONLY behaviors implied by the requirements
- Think about how elements will be interacted with using Playwright APIs
- Do NOT invent buttons, inputs, links, or pages
- Do NOT generate selectors, XPath, or code (that comes later)
- Do NOT describe UI state abstractly
- Express intent using observable actions and outcomes that Playwright can verify

OUTPUT REQUIREMENTS:
- Structured and deterministic
- Test-focused and actionable
- Free of implementation details
- Suitable for conversion to Playwright-based automation

Remember: You are analyzing UI structure to build test intent that will be automated using Python and Playwright. You are producing test INTENT, not executable test steps yet.
"""

    # --------------------------------------------------
    def build_context(
        self,
        requirements: str,
        page_model: dict
    ) -> str:
        """
        Build a safe, LLM-constrained test intent context.

        Args:
            requirements: Extracted testable requirements
            page_model: Deterministic UI discovery output

        Returns:
            Structured test intent description (text)
        """

        # Ensure page_model is serialized safely
        page_model_json = json.dumps(page_model, indent=2)

        prompt = f"""
INPUTS:

1. TEST REQUIREMENTS
{requirements}

2. PAGE STRUCTURE (DISCOVERED UI ELEMENTS)
{page_model_json}

TASK:
- Identify valid user actions that can be performed
- Identify verifiable outcomes based on visible UI elements
- Ensure every action maps to an existing element
- Ensure every outcome is observable

FORMAT RULES:
- Use bullet points
- Group by scenario intent
- Do NOT use Gherkin
- Do NOT use imperative step language

OUTPUT EXAMPLE (STYLE ONLY):
- Scenario Intent: User logs in successfully
  - Action: Enter value into username input
  - Action: Enter value into password input
  - Action: Click Login button
  - Outcome: Main page content is visible

Return ONLY the structured test intent.
"""

        return self.llm_client.generate_response(
            prompt=prompt,
            system_prompt=self.system_prompt
        )
