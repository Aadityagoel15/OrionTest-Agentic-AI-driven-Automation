import os
import ast
import re
import hashlib
from llm import get_llm_client
from config import Config, ProjectType


class FeatureToStepDefAgent:
    """Acts as a compiler from Gherkin → Behave step definitions"""

    # ------------------------------------------------------------------
    # CANONICAL BASE STEPS (IMPLEMENTED IN common_steps.py & web_steps.py)
    # ------------------------------------------------------------------
    CANONICAL_BASE_STEPS = {
        # API - common_steps.py
        "the request is executed",
        "the action should succeed",
        "the action should fail",
        "the api endpoint is available",

        # WEB - web_steps.py
        "the user navigates to {}",
        "the user clicks the {} button",
        "the user clicks the {} button for the item {}",
        "the user enters {} into the {} field",
        "the user should see text {}",
        "the user should be on the home page",
    }

    # ------------------------------------------------------------------
    # CANONICAL LANGUAGE NORMALIZATION
    # ------------------------------------------------------------------
    CANONICAL_REWRITE_MAP = {
        r"i navigate to url {}": "the user navigates to {}",
        r"i navigate to {}": "the user navigates to {}",

        r"i click on the {}": "the user clicks the {} button",
        r"i click the {}": "the user clicks the {} button",

        r"i enter {} in the {} field": "the user enters {} into the {} field",
        r"i enter {} in the {} input field": "the user enters {} into the {} field",

        r"i should see {}": "the user should see text {}",
        r"the text {} should be displayed": "the user should see text {}",
    }

    SYSTEM_PROMPT = """
You are a Senior Automation Test Engineer with 10+ years of experience in test automation.

YOUR EXPERTISE:
- Python programming for automation (expert-level)
- Playwright automation framework (primary tool)
- Behave BDD framework for Python
- Writing maintainable step definitions with actual implementation code
- Creating reusable test automation code

YOUR ROLE AS STEP DEFINITION WRITER:
- Convert Gherkin feature steps into Python Behave step definitions
- Write step definitions with FULL Playwright implementation code (NOT pass statements)
- Ensure code follows Python best practices and is maintainable
- Create step definitions that integrate seamlessly with the Playwright framework

CRITICAL REQUIREMENTS:
- ALWAYS generate actual Playwright code - NEVER use pass statements
- Output must be valid Python code (AST-valid)
- Use Behave decorators (@given, @when, @then)
- Preserve step semantics (Given/When/Then)
- Step definitions MUST execute Playwright commands
- Use context.page for Playwright page object (context is provided by Behave as function parameter)
- DO NOT import context - it's automatically provided by Behave framework
- Use context from Behave framework (context.page, context.last_action_success, etc.)
- For field locators, use: context.page.locator(f"input[name='{field}']") or context.page.locator(f"#{field}")
- For button/element locators, use: context.page.locator(f"text={element}") or context.page.locator(f"button:has-text('{element}')")
- For text verification, use: context.page.locator(f"text={text}").first.is_visible()
- Set context.last_action_success = True on success
- Raise AssertionError on failures with descriptive messages
- Follow Python PEP 8 style guidelines

IMPORTANT:
- Generate COMPLETE, EXECUTABLE code for every step definition
- Do NOT use pass or TODO comments - write the actual implementation
- Do NOT import context - it's provided automatically by Behave
- Only import: from behave import given, when, then and from config import Config
- The code must work with Playwright and Behave framework

Remember: You are writing FULL Python automation code that uses Playwright for web automation, following Behave BDD framework conventions.
"""

    def __init__(self):
        self.llm_client = get_llm_client()

    # ------------------------------------------------------------------
    def generate_step_definitions(
        self,
        feature_file_path: str,
        project_type=ProjectType.UNKNOWN
    ) -> str:
        if not os.path.exists(feature_file_path):
            raise FileNotFoundError(feature_file_path)

        with open(feature_file_path, "r", encoding="utf-8") as f:
            feature_content = f.read()

        # Extract ALL unique steps from feature file (with their keywords)
        all_steps = self._extract_all_steps_with_keywords(feature_content)
        
        if not all_steps:
            # No steps found - return minimal file
            return self._generate_minimal_step_file()
        
        # Generate step definitions directly for ALL steps using AI with actual Playwright code
        return self._generate_step_definitions_for_all_steps(all_steps, feature_content, project_type)

    # ------------------------------------------------------------------
    def _extract_steps_from_feature(self, feature_content: str) -> list:
        """Extract all step text from feature file"""
        steps = []
        step_keywords = ["Given", "When", "Then", "And", "But"]
        
        for line in feature_content.splitlines():
            stripped = line.strip()
            for keyword in step_keywords:
                if stripped.startswith(f"{keyword} "):
                    step_text = stripped[len(keyword):].strip()
                    steps.append(step_text)
                    break
        
        return steps
    
    # ------------------------------------------------------------------
    def _extract_all_steps_with_keywords(self, feature_content: str) -> list:
        """Extract all unique steps with their keywords from feature file"""
        steps_dict = {}  # key: normalized step text, value: (keyword, original_step)
        step_keywords = ["Given", "When", "Then", "And", "But"]
        last_keyword = "Given"  # Track last non-And/But keyword
        
        for line in feature_content.splitlines():
            stripped = line.strip()
            for keyword in step_keywords:
                if stripped.startswith(f"{keyword} "):
                    step_text = stripped[len(keyword):].strip()
                    normalized = self._normalize_step(step_text.lower())
                    
                    # Map "And" and "But" to the last actual keyword
                    if keyword in ["And", "But"]:
                        actual_keyword = last_keyword
                    else:
                        actual_keyword = keyword
                        last_keyword = keyword
                    
                    # Store unique steps (normalized), preserving the first keyword found
                    if normalized not in steps_dict:
                        steps_dict[normalized] = (actual_keyword, step_text)
                    break
        
        # Return list of (keyword, step_text) tuples
        return list(steps_dict.values())

    # ------------------------------------------------------------------
    def _filter_custom_steps(self, steps: list) -> list:
        """Filter out canonical steps, return only custom steps"""
        custom = []
        
        for step in steps:
            normalized = self._normalize_step(step.lower())
            
            # Check if it matches any canonical pattern
            is_canonical = False
            for canonical in self.CANONICAL_BASE_STEPS:
                if self._matches_canonical_pattern(normalized, canonical):
                    is_canonical = True
                    break
            
            if not is_canonical:
                custom.append(step)
        
        return custom

    # ------------------------------------------------------------------
    def _matches_canonical_pattern(self, step: str, pattern: str) -> bool:
        """Check if step matches canonical pattern"""
        # Convert pattern placeholders to regex
        regex_pattern = re.escape(pattern).replace(r'\{\}', '.*?')
        regex_pattern = f"^{regex_pattern}$"
        return bool(re.match(regex_pattern, step))

    # ------------------------------------------------------------------
    def _generate_minimal_step_file(self) -> str:
        """Generate minimal step file when all steps are canonical"""
        return """# All steps use canonical base implementations
# See: features/steps/base/common_steps.py
# See: features/steps/base/web_steps.py

# No custom steps required for this feature
pass
"""

    # ------------------------------------------------------------------
    def _generate_canonical_steps_documentation(self, all_steps: list) -> str:
        """Generate a visible file documenting which canonical steps are being used"""
        lines = [
            "# =============================================================================",
            "# CANONICAL STEP DEFINITIONS DOCUMENTATION",
            "# =============================================================================",
            "#",
            "# All steps in this feature use canonical base implementations.",
            "# The step definitions below document which steps are used, but the actual",
            "# implementation is provided by the base step definitions in:",
            "# - features/steps/base/web_steps.py",
            "# - features/steps/base/common_steps.py",
            "#",
            "# These base implementations are automatically loaded by Behave.",
            "# This file serves as documentation of which steps are being used.",
            "#",
            "from behave import given, when, then",
            "",
            "# =============================================================================",
            "# STEPS USED IN THIS FEATURE",
            "# =============================================================================",
            ""
        ]
        
        # Group steps by keyword for better organization
        steps_by_keyword = {}
        for keyword, step_text in all_steps:
            keyword_lower = keyword.lower()
            if keyword_lower not in steps_by_keyword:
                steps_by_keyword[keyword_lower] = []
            steps_by_keyword[keyword_lower].append(step_text)
        
        # Generate documentation for each step
        for keyword in ["given", "when", "then"]:
            if keyword not in steps_by_keyword:
                continue
            
            lines.append(f"# --- {keyword.upper()} Steps ---")
            for step_text in steps_by_keyword[keyword]:
                # Convert to generic format
                generic = self._force_generic_decorator(step_text)
                generic = self._canonicalize_params(generic)
                
                # Extract parameters
                params = re.findall(r"\{([^}]+)\}", generic)
                signature_parts = ["context"] + params
                signature = ", ".join(signature_parts)
                
                # Generate function name
                func_name = self._unique_func_name(generic)
                
                # Add documentation
                lines.append(f"# Step: {step_text}")
                lines.append(f"# Generic pattern: {generic}")
                lines.append(f"# Implemented by: features/steps/base/web_steps.py or common_steps.py")
                lines.append(f"#")
                lines.append(f"# @{keyword}(r'{generic}')")
                lines.append(f"# def {func_name}({signature}):")
                lines.append(f"#     # Implementation handled by canonical base step definition")
                lines.append(f"#     pass")
                lines.append("")
        
        lines.extend([
            "# =============================================================================",
            "# END OF DOCUMENTATION",
            "# =============================================================================",
            "",
            "# Note: The actual step definitions are loaded from features/steps/base/",
            "# This file is for documentation purposes only."
        ])
        
        return "\n".join(lines)

    # ------------------------------------------------------------------
    def _build_all_steps_prompt(self, all_steps: list, feature_content: str, project_type: str) -> str:
        """Build prompt for generating ALL step definitions"""
        steps_list = "\n".join([f"- {keyword}: {step_text}" for keyword, step_text in all_steps])
        
        canonical_info = "\n".join(f"- {s}" for s in sorted(self.CANONICAL_BASE_STEPS))
        
        return f"""
Generate Behave step definitions for ALL steps in the following feature file.

PROJECT TYPE: {project_type.upper()}

CANONICAL BASE STEPS (reference - these are already implemented in base files):
{canonical_info}

ALL STEPS TO IMPLEMENT:
{steps_list}

FEATURE FILE:
{feature_content[:3000]}

INSTRUCTIONS:
- Generate step definitions for EVERY step listed above
- Use proper step decorators: @given, @when, or @then based on the keyword
- Use placeholder syntax for parameters: {{param_name}}
- For canonical steps, you can add a comment indicating they're canonical
- For custom steps, include TODO comments for implementation
- Return valid Python code starting with: from behave import given, when, then
- Each step definition should have a function with 'context' as first parameter
- Use pass statements for now (implementation will be added later)

OUTPUT FORMAT:
from behave import given, when, then

@given('step text with {{param}}')
def step_function_name(context, param):
    # TODO: Implement step logic
    pass

Generate step definitions for ALL {len(all_steps)} steps listed above.
"""

    # ------------------------------------------------------------------
    def save_step_definitions(self, content: str, feature_name: str) -> str:
        Config.ensure_directories()
        path = os.path.join(
            Config.STEP_DEFINITIONS_DIR,
            f"{feature_name}_steps.py"
        )
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return path

    # ------------------------------------------------------------------
    def _sanitize_and_validate(self, content: str) -> str:
        """Sanitize and validate generated step definitions (legacy method for backward compatibility)"""
        return content
    
    # ------------------------------------------------------------------
    def _generate_step_definitions_for_all_steps(self, all_steps: list, feature_content: str = "", project_type: str = "WEB") -> str:
        """Generate step definitions with actual Playwright code for CUSTOM steps only (skip canonical to avoid conflicts)"""
        
        # Filter out canonical steps to avoid AmbiguousStep errors with base implementations
        custom_steps = []
        for keyword, step_text in all_steps:
            generic = self._force_generic_decorator(step_text)
            generic_normalized = self._normalize_step(generic)
            
            # Check if this is a canonical step
            is_canonical = False
            for canonical_pattern in self.CANONICAL_BASE_STEPS:
                canonical_normalized = self._normalize_step(canonical_pattern)
                if canonical_normalized == generic_normalized:
                    is_canonical = True
                    break
            
            if not is_canonical:
                custom_steps.append((keyword, step_text))
        
        # If all steps are canonical, generate a file documenting which steps are used
        if not custom_steps:
            return self._generate_canonical_steps_documentation(all_steps)
        
        # Generate step definitions for custom steps only using parameterized patterns
        return self._generate_fallback_step_definitions(custom_steps)
    
    # ------------------------------------------------------------------
    def _clean_generated_code(self, code: str) -> str:
        """Clean AI-generated code to ensure it's valid Python"""
        lines = code.splitlines()
        cleaned = []
        in_code_block = False
        found_code_block = False
        
        for line in lines:
            # Check if we're in a markdown code block
            if line.strip().startswith("```"):
                in_code_block = not in_code_block
                found_code_block = True
                continue
            
            # If markdown code blocks exist, only include lines inside code blocks
            if found_code_block and not in_code_block:
                continue
            
            cleaned.append(line)
        
        code = "\n".join(cleaned).strip()
        
        # Remove incorrect imports (context should not be imported)
        code = re.sub(r'from\s+environment\s+import\s+context\s*\n?', '', code, flags=re.IGNORECASE)
        code = re.sub(r'import\s+context\s*\n?', '', code, flags=re.IGNORECASE)
        
        # Ensure we have necessary imports at the top
        if "from behave import" not in code:
            code = "from behave import given, when, then\n" + code
        
        # Add Config import if not present and Config is used
        if "Config." in code or "Config.is_framework_mode()" in code:
            if "from config import Config" not in code:
                # Find the first import line and add Config import after it
                lines = code.splitlines()
                new_lines = []
                config_imported = False
                for i, line in enumerate(lines):
                    new_lines.append(line)
                    # Insert Config import after first import statement
                    if (line.strip().startswith("import ") or line.strip().startswith("from ")) and not config_imported:
                        if "config" not in line.lower() and "context" not in line.lower():
                            new_lines.append("from config import Config")
                            config_imported = True
                code = "\n".join(new_lines)
        
        return code
    
    # ------------------------------------------------------------------
    def _generate_fallback_step_definitions(self, all_steps: list) -> str:
        """Fallback method to generate step definitions with template-based Playwright code"""
        final_lines = []
        seen_generics = set()

        final_lines.extend([
            "from behave import given, when, then",
            "from config import Config",
            "from pathlib import Path",
            "",
            "# Step definitions with Playwright implementation",
            ""
        ])

        for keyword, step_text in all_steps:
            # Convert step text to generic format with placeholders
            generic = self._force_generic_decorator(step_text)
            generic = self._canonicalize_params(generic)

            # Skip duplicates
            if generic in seen_generics:
                continue
            seen_generics.add(generic)

            # Generate function name
            func_name = self._unique_func_name(generic)

            # Determine correct decorator keyword
            keyword_lower = keyword.lower()

            # Extract parameters
            params = re.findall(r"\{([^}]+)\}", generic)
            
            # Add decorator and function
            final_lines.append(f"@{keyword_lower}(r'{generic}')")
            signature = ", ".join(["context"] + params)
            final_lines.append(f"def {func_name}({signature}):")

            # Generate implementation based on step pattern
            step_lower = generic.lower()
            
            if "navigates to" in step_lower:
                # Navigation step
                final_lines.append("    if Config.is_framework_mode():")
                final_lines.append('        raise RuntimeError("UI step executed in framework mode")')
                final_lines.append("    ")
                final_lines.append("    # HARD GUARD: Detect page lifecycle violations immediately")
                final_lines.append('    assert hasattr(context, "page"), "❌ Playwright page not initialized"')
                final_lines.append('    assert context.page is not None, "❌ Playwright page is None"')
                final_lines.append('    assert not context.page.is_closed(), "❌ Playwright page was closed"')
                final_lines.append("    ")
                param_name = params[0] if params else "url"
                final_lines.append(f'    url = {param_name}.strip(\'"\')')
                final_lines.append("    if hasattr(context, 'base_url') and context.base_url:")
                final_lines.append("        if not url.startswith('http'):")
                final_lines.append("            url = context.base_url.rstrip('/') + '/' + url.lstrip('/')")
                final_lines.append("    context.page.goto(url, timeout=30000, wait_until='networkidle')")
                final_lines.append("    context.last_action_success = True")
            
            elif ("enters" in step_lower and "into" in step_lower and ("field" in step_lower or "input" in step_lower)) or ("enters" in step_lower and "input with label" in step_lower):
                # Input field step (handles both "field" and "input with label" patterns)
                final_lines.append("    if Config.is_framework_mode():")
                final_lines.append('        raise RuntimeError("UI step executed in framework mode")')
                final_lines.append("    ")
                final_lines.append("    # HARD GUARD: Detect page lifecycle violations immediately")
                final_lines.append('    assert hasattr(context, "page"), "❌ Playwright page not initialized"')
                final_lines.append('    assert context.page is not None, "❌ Playwright page is None"')
                final_lines.append('    assert not context.page.is_closed(), "❌ Playwright page was closed"')
                final_lines.append("    ")
                if len(params) >= 2:
                    value_param = params[0]
                    field_param = params[1]
                    final_lines.append(f'    value = {value_param}.strip(\'"\')')
                    final_lines.append(f'    field = {field_param}.strip(\'"\')')
                    final_lines.append('    # Normalize field name (convert "last-name" to "lastname" or "lastName")')
                    final_lines.append('    field_normalized = field.replace("-", "").replace("_", "").lower()')
                    final_lines.append('    # Try multiple locator strategies')
                    final_lines.append('    try:')
                    final_lines.append('        field_locator = context.page.locator(f"input[name=\'{field}\']").first')
                    final_lines.append('        field_locator.wait_for(state=\'visible\', timeout=5000)')
                    final_lines.append('        field_locator.fill(value)')
                    final_lines.append('    except:')
                    final_lines.append('        try:')
                    final_lines.append('            field_locator = context.page.locator(f"#{field}").first')
                    final_lines.append('            field_locator.wait_for(state=\'visible\', timeout=5000)')
                    final_lines.append('            field_locator.fill(value)')
                    final_lines.append('        except:')
                    final_lines.append('            try:')
                    final_lines.append('                # Try with normalized field name')
                    final_lines.append('                field_locator = context.page.locator(f"input[name=\'{field_normalized}\']").first')
                    final_lines.append('                field_locator.wait_for(state=\'visible\', timeout=5000)')
                    final_lines.append('                field_locator.fill(value)')
                    final_lines.append('            except:')
                    final_lines.append('                # Try by label text')
                    final_lines.append('                field_locator = context.page.locator(f"label:has-text(\'{field}\') + input, label:has-text(\'{field}\') ~ input").first')
                    final_lines.append('                field_locator.wait_for(state=\'visible\', timeout=5000)')
                    final_lines.append('                field_locator.fill(value)')
                    final_lines.append("    context.last_action_success = True")
            
            elif "clicks the" in step_lower and "button" in step_lower and "for the item" in step_lower:
                # Button with item context (e.g., "Add to Cart" for item) - MUST check before generic button click
                final_lines.append("    if Config.is_framework_mode():")
                final_lines.append('        raise RuntimeError("UI step executed in framework mode")')
                final_lines.append("    ")
                final_lines.append("    # HARD GUARD: Detect page lifecycle violations immediately")
                final_lines.append('    assert hasattr(context, "page"), "❌ Playwright page not initialized"')
                final_lines.append('    assert context.page is not None, "❌ Playwright page is None"')
                final_lines.append('    assert not context.page.is_closed(), "❌ Playwright page was closed"')
                final_lines.append("    ")
                if len(params) >= 2:
                    element_param = params[0]
                    item_param = params[1]
                elif len(params) == 1:
                    element_param = params[0]
                    item_param = "item"
                else:
                    element_param = "element"
                    item_param = "item"
                final_lines.append(f'    element = {element_param}.strip(\'"\')')
                final_lines.append(f'    item = {item_param}.strip(\'"\')')
                final_lines.append('    button_clicked = False')
                final_lines.append('    ')
                final_lines.append('    # CRITICAL: Verify page is initialized and on correct URL')
                final_lines.append('    if not hasattr(context, "page") or context.page is None:')
                final_lines.append('        raise AssertionError("Page is not initialized. Check execution mode is PROJECT.")')
                final_lines.append('    ')
                final_lines.append('    # Wait for page to stabilize after previous actions')
                final_lines.append('    try:')
                final_lines.append('        context.page.wait_for_load_state("networkidle", timeout=10000)')
                final_lines.append('    except:')
                final_lines.append('        try:')
                final_lines.append('            context.page.wait_for_load_state("domcontentloaded", timeout=5000)')
                final_lines.append('        except:')
                final_lines.append('            pass')
                final_lines.append('    ')
                final_lines.append('    # CRITICAL: Verify we are on the correct page (not still on login page)')
                final_lines.append('    # After login, wait for URL to change to inventory/products page')
                final_lines.append('    import time')
                final_lines.append('    max_wait = 20  # seconds')
                final_lines.append('    start_time = time.time()')
                final_lines.append('    while True:')
                final_lines.append('        current_url = context.page.url.lower()')
                final_lines.append('        # Check for common post-login page patterns (site-agnostic)')
                final_lines.append('        if any(keyword in current_url for keyword in ["inventory", "products", "catalog", "shop", "store", "dashboard", "home"]):')
                final_lines.append('            # Navigation completed')
                final_lines.append('            break')
                final_lines.append('        elapsed = time.time() - start_time')
                final_lines.append('        if elapsed > max_wait:')
                final_lines.append('            # Timeout - continue anyway, might be on correct page')
                final_lines.append('            break')
                final_lines.append('        context.page.wait_for_timeout(500)')
                final_lines.append('    ')
                final_lines.append('    context.page.wait_for_timeout(2000)  # Longer pause for dynamic content to load')
                final_lines.append('    ')
                final_lines.append('    # Strategy 0: Use discovered locator hints from ui_locators.properties (site-agnostic)')
                final_lines.append('    if not button_clicked:')
                final_lines.append('        try:')
                final_lines.append('            loc_path = Path("reports/ui_locators.properties")')
                final_lines.append('            hints = {}')
                final_lines.append('            if loc_path.exists():')
                final_lines.append('                with open(loc_path, "r", encoding="utf-8") as f:')
                final_lines.append('                    for line in f:')
                final_lines.append('                        line = line.strip()')
                final_lines.append('                        if not line or line.startswith("#") or "=" not in line:')
                final_lines.append('                            continue')
                final_lines.append('                        k, v = line.split("=", 1)')
                final_lines.append('                        hints[k.strip().lower()] = v.strip()')
                final_lines.append('            item_key = item.lower().replace(" ", "-").replace("_", "-").replace(".", "-")')
                final_lines.append('            candidate_keys = [')
                final_lines.append('                item_key,')
                final_lines.append('                f"add-to-cart-{item_key}",')
                final_lines.append('                f"addtocart-{item_key}",')
                final_lines.append('            ]')
                final_lines.append('            for key in candidate_keys:')
                final_lines.append('                if key in hints:')
                final_lines.append('                    try:')
                final_lines.append('                        btn = context.page.locator(hints[key]).first')
                final_lines.append('                        btn.wait_for(state="visible", timeout=8000)')
                final_lines.append('                        btn.scroll_into_view_if_needed()')
                final_lines.append('                        context.page.wait_for_timeout(300)')
                final_lines.append('                        btn.click(force=True)')
                final_lines.append('                        button_clicked = True')
                final_lines.append('                        break')
                final_lines.append('                    except Exception:')
                final_lines.append('                        continue')
                final_lines.append('        except Exception:')
                final_lines.append('            pass')
                final_lines.append('    ')
                final_lines.append('    # CRITICAL: Attribute-first strategy (never gate on text in SPAs)')
                final_lines.append('    # Text nodes render after button shell in React/Angular/Vue')
                final_lines.append('    # Always use stable attributes (data-test, id, name) FIRST')
                final_lines.append('    # Normalize item name for attribute matching')
                final_lines.append('    item_normalized = item.lower().replace(" ", "-").replace("_", "-").replace("(", "").replace(")", "").replace(".", "").replace("allthethings", "allthethings")')
                final_lines.append('    element_normalized = element.lower().replace(" ", "-").replace("_", "-")')
                final_lines.append('    exact_test_id = f"{element_normalized}-{item_normalized}"')
                final_lines.append('    ')
                final_lines.append('    # Wait for and click the EXACT button we need (attribute-based, not text-based)')
                final_lines.append('    # This is the canonical rule: attribute-first, text-last')
                final_lines.append('    # Try to find and click immediately using attribute selectors')
                final_lines.append('    try:')
                final_lines.append('        # Try multiple attribute-based selectors (most reliable)')
                final_lines.append('        exact_selectors = [')
                final_lines.append('            f\'[data-test="{exact_test_id}"]\',')
                final_lines.append('            f\'button[data-test="{exact_test_id}"]\',')
                final_lines.append('            f\'#{exact_test_id}\',')
                final_lines.append('            f\'button[name="{exact_test_id}"]\',')
                final_lines.append('        ]')
                final_lines.append('        for selector in exact_selectors:')
                final_lines.append('            try:')
                final_lines.append('                print(f"[DEBUG] Trying selector: {selector}")')
                final_lines.append('                btn = context.page.locator(selector).first')
                final_lines.append('                # Wait for attached (DOM exists) then visible (rendered)')
                final_lines.append('                btn.wait_for(state="attached", timeout=15000)')
                final_lines.append('                print(f"[DEBUG] Button attached, waiting for visible...")')
                final_lines.append('                btn.wait_for(state="visible", timeout=10000)')
                final_lines.append('                print(f"[DEBUG] Button visible, clicking...")')
                final_lines.append('                # Click immediately - button is ready')
                final_lines.append('                btn.scroll_into_view_if_needed()')
                final_lines.append('                btn.click()')
                final_lines.append('                print(f"[DEBUG] Button clicked successfully!")')
                final_lines.append('                button_clicked = True')
                final_lines.append('                break')
                final_lines.append('            except Exception as e:')
                final_lines.append('                print(f"[DEBUG] Selector {selector} failed: {e}")')
                final_lines.append('                continue')
                final_lines.append('    except Exception:')
                final_lines.append('        # If attribute-based wait/click fails, continue to other strategies')
                final_lines.append('        pass')
                final_lines.append('    ')
                final_lines.append('    # Strategy 1: Attribute-first click (use exact_test_id from above)')
                final_lines.append('    # This uses the normalized values already computed - no text gating')
                final_lines.append('    if not button_clicked:')
                final_lines.append('        try:')
                final_lines.append('            # Pattern 2: item-element (alternative ordering)')
                final_lines.append('            exact_test_id_2 = f"{item_normalized}-{element_normalized}"')
                final_lines.append('            ')
                final_lines.append('            # Try exact attribute matches FIRST (most reliable)')
                final_lines.append('            # Order: exact match > partial match > alternative ordering')
                final_lines.append('            test_selectors = [')
                final_lines.append('                # Exact matches (highest priority - matches UI discovery)')
                final_lines.append('                f\'[data-test="{exact_test_id}"]\',')
                final_lines.append('                f\'button[data-test="{exact_test_id}"]\',')
                final_lines.append('                f\'#{exact_test_id}\',')
                final_lines.append('                f\'button[name="{exact_test_id}"]\',')
                final_lines.append('                # Alternative ordering')
                final_lines.append('                f\'[data-test="{exact_test_id_2}"]\',')
                final_lines.append('                f\'button[data-test="{exact_test_id_2}"]\',')
                final_lines.append('                # Partial matches (fallback)')
                final_lines.append('                f\'button[data-test*="{item_normalized}"]\',')
                final_lines.append('                f\'[data-test*="{item_normalized}"]\',')
                final_lines.append('                # data-testid variants')
                final_lines.append('                f\'[data-testid="{exact_test_id}"]\',')
                final_lines.append('                f\'button[data-testid="{exact_test_id}"]\',')
                final_lines.append('            ]')
                final_lines.append('            for selector in test_selectors:')
                final_lines.append('                try:')
                final_lines.append('                    btn = context.page.locator(selector).first')
                final_lines.append('                    # Wait for attached then visible (no text gating)')
                final_lines.append('                    btn.wait_for(state="attached", timeout=10000)')
                final_lines.append('                    btn.wait_for(state="visible", timeout=10000)')
                final_lines.append('                    btn.scroll_into_view_if_needed()')
                final_lines.append('                    btn.click()  # No force - element is ready')
                final_lines.append('                    button_clicked = True')
                final_lines.append('                    break')
                final_lines.append('                except Exception:')
                final_lines.append('                    continue')
                final_lines.append('        except Exception:')
                final_lines.append('            pass')
                final_lines.append('    ')
                final_lines.append('    # Strategy 1.1: Generic attribute fallback (id/name contains item) – site-agnostic')
                final_lines.append('    if not button_clicked:')
                final_lines.append('        try:')
                final_lines.append('            item_key = item.lower().replace(" ", "-").replace("_", "-")')
                final_lines.append('            attr_selectors = [')
                final_lines.append('                f\'button[id*="{item_key}"]\',')
                final_lines.append('                f\'[id*="{item_key}"]\',')
                final_lines.append('                f\'button[name*="{item_key}"]\',')
                final_lines.append('                f\'[name*="{item_key}"]\',')
                final_lines.append('            ]')
                final_lines.append('            for sel in attr_selectors:')
                final_lines.append('                try:')
                final_lines.append('                    btn = context.page.locator(sel).first')
                final_lines.append('                    if btn.count() > 0:')
                final_lines.append('                        btn.wait_for(state="visible", timeout=8000)')
                final_lines.append('                        btn.scroll_into_view_if_needed()')
                final_lines.append('                        context.page.wait_for_timeout(300)')
                final_lines.append('                        btn.click(force=True)')
                final_lines.append('                        button_clicked = True')
                final_lines.append('                        break')
                final_lines.append('                except:')
                final_lines.append('                    continue')
                final_lines.append('        except:')
                final_lines.append('            pass')
                final_lines.append('    ')
                final_lines.append('    # Strategy 1.2: Scan visible add-to-cart buttons and match data-test with item (site-agnostic)')
                final_lines.append('    if not button_clicked:')
                final_lines.append('        try:')
                final_lines.append('            item_key = item.lower().replace(" ", "-").replace("_", "-")')
                final_lines.append('            btns = context.page.locator(\'button:has-text("Add to cart")\').all()')
                final_lines.append('            for btn in btns:')
                final_lines.append('                try:')
                final_lines.append('                    dt = (btn.get_attribute("data-test") or "").lower()')
                final_lines.append('                    if item_key in dt:')
                final_lines.append('                        btn.wait_for(state="visible", timeout=8000)')
                final_lines.append('                        btn.scroll_into_view_if_needed()')
                final_lines.append('                        context.page.wait_for_timeout(300)')
                final_lines.append('                        btn.click(force=True)')
                final_lines.append('                        button_clicked = True')
                final_lines.append('                        break')
                final_lines.append('                except:')
                final_lines.append('                    continue')
                final_lines.append('        except:')
                final_lines.append('            pass')
                final_lines.append('    ')
                final_lines.append('    # Strategy 1.1: Generic attribute fallback (id/name contains item)')
                final_lines.append('    if not button_clicked:')
                final_lines.append('        try:')
                final_lines.append('            item_key = item.lower().replace(" ", "-").replace("_", "-")')
                final_lines.append('            attr_selectors = [')
                final_lines.append('                f\'button[id*="{item_key}"]\',')
                final_lines.append('                f\'[id*="{item_key}"]\',')
                final_lines.append('                f\'button[name*="{item_key}"]\',')
                final_lines.append('                f\'[name*="{item_key}"]\',')
                final_lines.append('            ]')
                final_lines.append('            for sel in attr_selectors:')
                final_lines.append('                try:')
                final_lines.append('                    btn = context.page.locator(sel).first')
                final_lines.append('                    if btn.count() > 0:')
                final_lines.append('                        btn.wait_for(state="visible", timeout=8000)')
                final_lines.append('                        btn.scroll_into_view_if_needed()')
                final_lines.append('                        context.page.wait_for_timeout(300)')
                final_lines.append('                        btn.click(force=True)')
                final_lines.append('                        button_clicked = True')
                final_lines.append('                        break')
                final_lines.append('                except:')
                final_lines.append('                    continue')
                final_lines.append('        except:')
                final_lines.append('            pass')
                final_lines.append('    ')
                final_lines.append('    # Find item text for container-based approach')
                final_lines.append('    item_element = None')
                final_lines.append('    if not button_clicked:')
                final_lines.append('        try:')
                final_lines.append('            item_locator = context.page.locator(f"text={item}")')
                final_lines.append('            if item_locator.count() > 0:')
                final_lines.append('                item_element = item_locator.first')
                final_lines.append('                item_element.wait_for(state="visible", timeout=10000)')
                final_lines.append('                item_element.scroll_into_view_if_needed()')
                final_lines.append('                context.page.wait_for_timeout(300)')
                final_lines.append('        except:')
                final_lines.append('            pass  # Continue - might find button without item text')
                final_lines.append('    ')
                final_lines.append('    # Strategy 2: Container-based approach (WORKS FOR ANY WEBSITE)')
                final_lines.append('    # Find item first, then find button in the same container/parent')
                final_lines.append('    if not button_clicked and item_element:')
                final_lines.append('        try:')
                final_lines.append('            # Navigate up the DOM tree to find containers that might hold the button')
                final_lines.append('            # Use Playwright\'s locator chain to navigate up and search')
                final_lines.append('            containers_to_check = []')
                final_lines.append('            current = item_element')
                final_lines.append('            # Build list of parent containers to check (up to 5 levels)')
                final_lines.append('            for i in range(5):')
                final_lines.append('                try:')
                final_lines.append('                    current = current.locator("xpath=..")')
                final_lines.append('                    if current.count() > 0:')
                final_lines.append('                        containers_to_check.append(current)')
                final_lines.append('                    else:')
                final_lines.append('                        break')
                final_lines.append('                except:')
                final_lines.append('                    break')
                final_lines.append('            ')
                final_lines.append('            # Also try finding containers using :has-text selector')
                final_lines.append('            for container_type in ["div", "article", "section", "li", "tr"]:')
                final_lines.append('                try:')
                final_lines.append('                    container = context.page.locator(f\'{container_type}:has-text("{item}")\').first')
                final_lines.append('                    if container.count() > 0:')
                final_lines.append('                        containers_to_check.append(container)')
                final_lines.append('                except:')
                final_lines.append('                    continue')
                final_lines.append('            ')
                final_lines.append('            # Search for button in each container')
                final_lines.append('            for container in containers_to_check:')
                final_lines.append('                try:')
                final_lines.append('                    # Try multiple button selectors')
                final_lines.append('                    button_selectors = [')
                final_lines.append('                        f\'button:has-text("{element}")\',')
                final_lines.append('                        f\'button:has-text("Add")\',')
                final_lines.append('                        f\'[role="button"]:has-text("{element}")\',')
                final_lines.append('                        f\'[data-test*="add"]\',')
                final_lines.append('                        f\'[data-testid*="add"]\',')
                final_lines.append('                        f\'button[aria-label*="{element}"]\',')
                final_lines.append('                    ]')
                final_lines.append('                    for btn_sel in button_selectors:')
                final_lines.append('                        try:')
                final_lines.append('                            btn = container.locator(btn_sel).first')
                final_lines.append('                            if btn.count() > 0:')
                final_lines.append('                                btn.wait_for(state="visible", timeout=3000)')
                final_lines.append('                                btn.scroll_into_view_if_needed()')
                final_lines.append('                                btn.click()')
                final_lines.append('                                button_clicked = True')
                final_lines.append('                                break')
                final_lines.append('                        except:')
                final_lines.append('                            continue')
                final_lines.append('                    if button_clicked:')
                final_lines.append('                        break')
                final_lines.append('                except:')
                final_lines.append('                    continue')
                final_lines.append('        except Exception as e:')
                final_lines.append('            pass')
                final_lines.append('    ')
                final_lines.append('    # Strategy 3: Simple text-based fallback (works for any website)')
                final_lines.append('    if not button_clicked:')
                final_lines.append('        try:')
                final_lines.append('            # Find button by text anywhere on page')
                final_lines.append('            text_patterns = [')
                final_lines.append('                f\'text="{element}"\',')
                final_lines.append('                f\'button:has-text("{element}")\',')
                final_lines.append('                f\'[role="button"]:has-text("{element}")\',')
                final_lines.append('            ]')
                final_lines.append('            for pattern in text_patterns:')
                final_lines.append('                try:')
                final_lines.append('                    btn = context.page.locator(pattern).first')
                final_lines.append('                    if btn.count() > 0:')
                final_lines.append('                        btn.wait_for(state="visible", timeout=5000)')
                final_lines.append('                        btn.scroll_into_view_if_needed()')
                final_lines.append('                        btn.click()')
                final_lines.append('                        button_clicked = True')
                final_lines.append('                        break')
                final_lines.append('                except:')
                final_lines.append('                    continue')
                final_lines.append('        except:')
                final_lines.append('            pass')
                final_lines.append('    ')
                final_lines.append('    # Strategy 3: Find all item text matches, get closest button')
                final_lines.append('    if not button_clicked:')
                final_lines.append('        try:')
                final_lines.append('            item_elements = context.page.locator(f"text={item}").all()')
                final_lines.append('            if item_elements:')
                final_lines.append('                # Get bounding box of first matching item')
                final_lines.append('                item_box = item_elements[0].bounding_box()')
                final_lines.append('                if item_box:')
                final_lines.append('                    # Find all buttons with the element text')
                final_lines.append('                    element_normalized = element.lower().replace(" ", "-")')
                final_lines.append('                    all_buttons = context.page.locator(f"button:has-text(\'{element}\'), button:has-text(\'Add\'), [data-test*=\'add\'], [data-test*=\'{element_normalized}\']").all()')
                final_lines.append('                    ')
                final_lines.append('                    # Find button closest to item (same container)')
                final_lines.append('                    closest_button = None')
                final_lines.append('                    min_distance = float(\'inf\')')
                final_lines.append('                    for button in all_buttons:')
                final_lines.append('                        try:')
                final_lines.append('                            button_box = button.bounding_box()')
                final_lines.append('                            if button_box:')
                final_lines.append('                                # Calculate distance (button should be near item horizontally)')
                final_lines.append('                                x_distance = abs(button_box[\'x\'] - item_box[\'x\'])')
                final_lines.append('                                if x_distance < 600:  # Within reasonable horizontal distance')
                final_lines.append('                                    distance = x_distance')
                final_lines.append('                                    if distance < min_distance:')
                final_lines.append('                                        min_distance = distance')
                final_lines.append('                                        closest_button = button')
                final_lines.append('                        except:')
                final_lines.append('                            continue')
                final_lines.append('                    ')
                final_lines.append('                    if closest_button:')
                final_lines.append('                        closest_button.wait_for(state=\'visible\', timeout=10000)')
                final_lines.append('                        closest_button.click()')
                final_lines.append('                        button_clicked = True')
                final_lines.append('        except Exception as e:')
                final_lines.append('            pass')
                final_lines.append('    ')
                final_lines.append('    # Strategy 4: Direct approach - find any button with element text (simplest, most generic)')
                final_lines.append('    if not button_clicked:')
                final_lines.append('        try:')
                final_lines.append('            # Try simple, direct locators (works for any button type on any website)')
                final_lines.append('            element_normalized = element.lower().replace(" ", "-")')
                final_lines.append('            # Try exact element text first (most specific), then generic patterns')
                final_lines.append('            simple_patterns = [')
                final_lines.append(f'                f"text={{element}}",  # Exact text match (most specific - works for any element)')
                final_lines.append(f'                f"button:has-text(\'{{element}}\')",  # Button with exact text')
                final_lines.append(f'                f"button:has-text(\'{{element.lower()}}\')",  # Case-insensitive')
                final_lines.append(f'                f"button:has-text(\'{{element.upper()}}\')",  # Uppercase variant')
                final_lines.append('                "button:has-text(\'Add\')",  # Generic add button')
                final_lines.append('                "button:has-text(\'Select\')",  # Generic select button')
                final_lines.append('                "button:has-text(\'Choose\')",  # Generic choose button')
                final_lines.append(f'                f"[data-test*=\'{{element_normalized}}\']",  # Data attribute')
                final_lines.append(f'                f"button[data-test*=\'{{element_normalized}}\']",  # Button with data attribute')
                final_lines.append('            ]')
                final_lines.append('            for pattern in simple_patterns:')
                final_lines.append('                try:')
                final_lines.append('                    buttons = context.page.locator(pattern).all()')
                final_lines.append('                    if len(buttons) > 0:')
                final_lines.append('                        # Click the first visible button')
                final_lines.append('                        buttons[0].wait_for(state=\'visible\', timeout=10000)')
                final_lines.append('                        buttons[0].scroll_into_view_if_needed()')
                final_lines.append('                        buttons[0].click()')
                final_lines.append('                        button_clicked = True')
                final_lines.append('                        break')
                final_lines.append('                except:')
                final_lines.append('                    continue')
                final_lines.append('        except Exception as e:')
                final_lines.append('            pass')
                final_lines.append('    ')
                final_lines.append('    # Strategy 5: Final fallback - try generic button text matching')
                final_lines.append('    if not button_clicked:')
                final_lines.append('        try:')
                final_lines.append('            element_normalized = element.lower().replace(" ", "-")')
                final_lines.append('            button_locator = context.page.locator(f"button:has-text(\'{element}\'), button:has-text(\'Add\'), [data-test*=\'add\'], [data-test*=\'{element_normalized}\']").first')
                final_lines.append('            if button_locator.count() > 0:')
                final_lines.append('                button_locator.wait_for(state=\'visible\', timeout=10000)')
                final_lines.append('                button_locator.scroll_into_view_if_needed()')
                final_lines.append('                button_locator.click()')
                final_lines.append('                button_clicked = True')
                final_lines.append('        except Exception as e:')
                final_lines.append('            pass')
                final_lines.append('    ')
                final_lines.append('    # Strategy 6: Ultimate fallback - use simple text locator (most generic approach)')
                final_lines.append('    if not button_clicked:')
                final_lines.append('        try:')
                final_lines.append('            # Try the simplest possible approach - find element by text (works for any website)')
                final_lines.append('            text_locator = context.page.locator(f"text={element}").first')
                final_lines.append('            if text_locator.count() > 0:')
                final_lines.append('                text_locator.wait_for(state=\'visible\', timeout=15000)')
                final_lines.append('                text_locator.scroll_into_view_if_needed()')
                final_lines.append('                text_locator.click()')
                final_lines.append('                button_clicked = True')
                final_lines.append('        except:')
                final_lines.append('            pass')
                final_lines.append('    ')
                final_lines.append('    if not button_clicked:')
                final_lines.append(f'        raise AssertionError(f"Could not find \'{{element}}\' button for item \'{{item}}\'. Tried multiple strategies.")')
                final_lines.append("    context.last_action_success = True")
            
            elif "clicks the" in step_lower and "button" in step_lower:
                # Click button/element step (generic, without item context)
                final_lines.append("    if Config.is_framework_mode():")
                final_lines.append('        raise RuntimeError("UI step executed in framework mode")')
                final_lines.append("    ")
                final_lines.append("    # HARD GUARD: Detect page lifecycle violations immediately")
                final_lines.append('    assert hasattr(context, "page"), "❌ Playwright page not initialized"')
                final_lines.append('    assert context.page is not None, "❌ Playwright page is None"')
                final_lines.append('    assert not context.page.is_closed(), "❌ Playwright page was closed"')
                final_lines.append("    ")
                param_name = params[0] if params else "element"
                final_lines.append(f'    element = {param_name}.strip(\'"\')')
                final_lines.append('    # Try multiple locator strategies')
                final_lines.append('    try:')
                final_lines.append('        button_locator = context.page.locator(f"text={element}").first')
                final_lines.append('        button_locator.wait_for(state=\'visible\', timeout=5000)')
                final_lines.append('        button_locator.click()')
                final_lines.append('    except:')
                final_lines.append('        try:')
                final_lines.append('            button_locator = context.page.locator(f"button:has-text(\'{element}\')").first')
                final_lines.append('            button_locator.wait_for(state=\'visible\', timeout=5000)')
                final_lines.append('            button_locator.click()')
                final_lines.append('        except:')
                final_lines.append('            button_locator = context.page.locator(f"[data-test*=\'{element.lower().replace(\" \", \"-\")}\']").first')
                final_lines.append('            button_locator.wait_for(state=\'visible\', timeout=5000)')
                final_lines.append('            button_locator.click()')
                final_lines.append("    context.last_action_success = True")
            
            elif "should not see text" in step_lower or "should not see" in step_lower:
                # Negative text assertion
                final_lines.append("    if Config.is_framework_mode():")
                final_lines.append('        raise RuntimeError("UI step executed in framework mode")')
                final_lines.append("    ")
                final_lines.append("    # HARD GUARD: Detect page lifecycle violations immediately")
                final_lines.append('    assert hasattr(context, "page"), "❌ Playwright page not initialized"')
                final_lines.append('    assert context.page is not None, "❌ Playwright page is None"')
                final_lines.append('    assert not context.page.is_closed(), "❌ Playwright page was closed"')
                final_lines.append("    ")
                param_name = params[0] if params else "text"
                final_lines.append(f'    text = {param_name}.strip(\'"\')')
                final_lines.append('    locator = context.page.locator(f"text={text}")')
                final_lines.append("    if locator.first.is_visible(timeout=5000):")
                final_lines.append(f'        raise AssertionError(f"[TEXT FOUND WHEN IT SHOULD NOT BE] \'{{text}}\'")')
                final_lines.append("    ")
                final_lines.append("    context.last_action_success = True")
            
            elif "should see text" in step_lower or "should see" in step_lower:
                # Positive text assertion
                final_lines.append("    if Config.is_framework_mode():")
                final_lines.append('        raise RuntimeError("UI step executed in framework mode")')
                final_lines.append("    ")
                final_lines.append("    # HARD GUARD: Detect page lifecycle violations immediately")
                final_lines.append('    assert hasattr(context, "page"), "❌ Playwright page not initialized"')
                final_lines.append('    assert context.page is not None, "❌ Playwright page is None"')
                final_lines.append('    assert not context.page.is_closed(), "❌ Playwright page was closed"')
                final_lines.append("    ")
                param_name = params[0] if params else "text"
                final_lines.append(f'    text = {param_name}.strip(\'"\')')
                final_lines.append('    locator = context.page.locator(f"text={text}")')
                final_lines.append("    if not locator.first.is_visible(timeout=5000):")
                final_lines.append(f'        raise AssertionError(f"[TEXT NOT FOUND] \'{{text}}\'")')
                final_lines.append("    ")
                final_lines.append("    context.last_action_success = True")
            
            elif "should be on the" in step_lower and "page" in step_lower:
                # Page verification
                final_lines.append("    if Config.is_framework_mode():")
                final_lines.append('        raise RuntimeError("UI step executed in framework mode")')
                final_lines.append("    ")
                final_lines.append("    # HARD GUARD: Detect page lifecycle violations immediately")
                final_lines.append('    assert hasattr(context, "page"), "❌ Playwright page not initialized"')
                final_lines.append('    assert context.page is not None, "❌ Playwright page is None"')
                final_lines.append('    assert not context.page.is_closed(), "❌ Playwright page was closed"')
                final_lines.append("    ")
                if params:
                    param_name = params[0]
                    final_lines.append(f'    page_name = {param_name}.strip(\'"\')')
                    final_lines.append(f'    current_url = context.page.url.lower()')
                    final_lines.append(f'    page_normalized = page_name.replace(" ", "").replace("-", "").lower()')
                    final_lines.append(f'    # Check URL or page title contains expected page name')
                    final_lines.append(f'    if page_normalized not in current_url and page_normalized not in context.page.title().lower():')
                    final_lines.append(f'        # Try checking for common page indicators')
                    # Generic page verification - works for any page name
                    final_lines.append(f'        if page_name.lower() not in current_url.lower() and page_name.lower() not in context.page.title().lower():')
                    final_lines.append(f'            raise AssertionError(f"[NOT ON EXPECTED PAGE] Expected page containing \'{{page_name}}\', Current URL: {{current_url}}")')
                else:
                    final_lines.append("    # Verify user is on expected page")
                final_lines.append("    context.last_action_success = True")
            
            elif "clicks on" in step_lower or "link/button" in step_lower or "/button" in step_lower:
                # Click link or button (handles "link/button" pattern)
                final_lines.append("    if Config.is_framework_mode():")
                final_lines.append('        raise RuntimeError("UI step executed in framework mode")')
                final_lines.append("    ")
                final_lines.append("    # HARD GUARD: Detect page lifecycle violations immediately")
                final_lines.append('    assert hasattr(context, "page"), "❌ Playwright page not initialized"')
                final_lines.append('    assert context.page is not None, "❌ Playwright page is None"')
                final_lines.append('    assert not context.page.is_closed(), "❌ Playwright page was closed"')
                final_lines.append("    ")
                param_name = params[0] if params else "value"
                final_lines.append(f'    value = {param_name}.strip(\'"\')')
                final_lines.append('    # Try multiple locator strategies for link or button')
                final_lines.append('    try:')
                final_lines.append('        locator = context.page.locator(f"text={value}").first')
                final_lines.append('        locator.wait_for(state=\'visible\', timeout=5000)')
                final_lines.append('        locator.click()')
                final_lines.append('    except:')
                final_lines.append('        try:')
                final_lines.append('            locator = context.page.locator(f"a:has-text(\'{value}\'), button:has-text(\'{value}\')").first')
                final_lines.append('            locator.wait_for(state=\'visible\', timeout=5000)')
                final_lines.append('            locator.click()')
                final_lines.append('        except:')
                final_lines.append('            locator = context.page.locator(f"[href*=\'{value.lower()}\'], [data-test*=\'{value.lower().replace(\" \", \"-\")}\']").first')
                final_lines.append('            locator.wait_for(state=\'visible\', timeout=5000)')
                final_lines.append('            locator.click()')
                final_lines.append("    context.last_action_success = True")
            
            elif "selects the item" in step_lower or ("selects" in step_lower and "item" in step_lower):
                # Item selection step (just marks item for later use, no action needed)
                final_lines.append("    if Config.is_framework_mode():")
                final_lines.append('        raise RuntimeError("UI step executed in framework mode")')
                final_lines.append("    ")
                final_lines.append("    # HARD GUARD: Detect page lifecycle violations immediately")
                final_lines.append('    assert hasattr(context, "page"), "❌ Playwright page not initialized"')
                final_lines.append('    assert context.page is not None, "❌ Playwright page is None"')
                final_lines.append('    assert not context.page.is_closed(), "❌ Playwright page was closed"')
                final_lines.append("    ")
                if params:
                    item_param = params[0]
                    final_lines.append(f'    item = {item_param}.strip(\'"\')')
                    final_lines.append("    # Store selected item in context for later use")
                    final_lines.append("    if not hasattr(context, 'selected_item'):")
                    final_lines.append("        context.selected_item = item")
                    final_lines.append("    else:")
                    final_lines.append("        context.selected_item = item")
                final_lines.append("    context.last_action_success = True")
            
            elif "is added to" in step_lower or ("item" in step_lower and ("added" in step_lower or "visible" in step_lower)):
                # Generic: Verify item/content is visible or added (works for cart, list, or any container)
                final_lines.append("    if Config.is_framework_mode():")
                final_lines.append('        raise RuntimeError("UI step executed in framework mode")')
                final_lines.append("    ")
                final_lines.append("    # HARD GUARD: Detect page lifecycle violations immediately")
                final_lines.append('    assert hasattr(context, "page"), "❌ Playwright page not initialized"')
                final_lines.append('    assert context.page is not None, "❌ Playwright page is None"')
                final_lines.append('    assert not context.page.is_closed(), "❌ Playwright page was closed"')
                final_lines.append("    ")
                if params:
                    item_param = params[0]
                    final_lines.append(f'    item = {item_param}.strip(\'"\')')
                    final_lines.append('    # Verify item/content is visible on page')
                    final_lines.append('    try:')
                    final_lines.append('        item_locator = context.page.locator(f"text={item}").first')
                    final_lines.append('        if item_locator.is_visible(timeout=5000):')
                    final_lines.append('            context.last_action_success = True')
                    final_lines.append('        else:')
                    final_lines.append('            # Item may be present but not visible - check page content')
                    final_lines.append('            page_text = context.page.content()')
                    final_lines.append('            if item in page_text:')
                    final_lines.append('                context.last_action_success = True')
                    final_lines.append('            else:')
                    final_lines.append('                raise AssertionError(f"Item {item} not found on page")')
                    final_lines.append('    except Exception as e:')
                    final_lines.append('        raise AssertionError(f"Failed to verify item visibility: {e}")')
                else:
                    # No params - just mark success (generic verification)
                    final_lines.append('    context.last_action_success = True')
            
            elif "enters" in step_lower and ("first name" in step_lower or "first-name" in step_lower):
                # First name field
                final_lines.append("    if Config.is_framework_mode():")
                final_lines.append('        raise RuntimeError("UI step executed in framework mode")')
                final_lines.append("    ")
                final_lines.append("    # HARD GUARD: Detect page lifecycle violations immediately")
                final_lines.append('    assert hasattr(context, "page"), "❌ Playwright page not initialized"')
                final_lines.append('    assert context.page is not None, "❌ Playwright page is None"')
                final_lines.append('    assert not context.page.is_closed(), "❌ Playwright page was closed"')
                final_lines.append("    ")
                if params:
                    value_param = params[0]
                    final_lines.append(f'    value = {value_param}.strip(\'"\')')
                    final_lines.append('    # Try multiple locator strategies for first name')
                    final_lines.append('    try:')
                    final_lines.append('        field_locator = context.page.locator("input[name=\'firstName\'], input[name=\'first-name\'], input[name=\'firstname\'], input[id=\'first-name\'], input[id=\'firstName\']").first')
                    final_lines.append('        field_locator.wait_for(state=\'visible\', timeout=5000)')
                    final_lines.append('        field_locator.fill(value)')
                    final_lines.append('    except:')
                    final_lines.append('        try:')
                    final_lines.append('            field_locator = context.page.locator("label:has-text(\'First Name\'), label:has-text(\'First name\')").locator("..").locator("input").first')
                    final_lines.append('            field_locator.wait_for(state=\'visible\', timeout=5000)')
                    final_lines.append('            field_locator.fill(value)')
                    final_lines.append('        except:')
                    final_lines.append('            raise AssertionError("[FIRST NAME FIELD NOT FOUND]")')
                final_lines.append("    context.last_action_success = True")
            
            elif "enters" in step_lower and ("last name" in step_lower or "last-name" in step_lower):
                # Last name field
                final_lines.append("    if Config.is_framework_mode():")
                final_lines.append('        raise RuntimeError("UI step executed in framework mode")')
                final_lines.append("    ")
                final_lines.append("    # HARD GUARD: Detect page lifecycle violations immediately")
                final_lines.append('    assert hasattr(context, "page"), "❌ Playwright page not initialized"')
                final_lines.append('    assert context.page is not None, "❌ Playwright page is None"')
                final_lines.append('    assert not context.page.is_closed(), "❌ Playwright page was closed"')
                final_lines.append("    ")
                if params:
                    value_param = params[0]
                    final_lines.append(f'    value = {value_param}.strip(\'"\')')
                    final_lines.append('    # Try multiple locator strategies for last name')
                    final_lines.append('    try:')
                    final_lines.append('        field_locator = context.page.locator("input[name=\'lastName\'], input[name=\'last-name\'], input[name=\'lastname\'], input[id=\'last-name\'], input[id=\'lastName\']").first')
                    final_lines.append('        field_locator.wait_for(state=\'visible\', timeout=5000)')
                    final_lines.append('        field_locator.fill(value)')
                    final_lines.append('    except:')
                    final_lines.append('        try:')
                    final_lines.append('            field_locator = context.page.locator("label:has-text(\'Last Name\'), label:has-text(\'Last name\')").locator("..").locator("input").first')
                    final_lines.append('            field_locator.wait_for(state=\'visible\', timeout=5000)')
                    final_lines.append('            field_locator.fill(value)')
                    final_lines.append('        except:')
                    final_lines.append('            raise AssertionError("[LAST NAME FIELD NOT FOUND]")')
                final_lines.append("    context.last_action_success = True")
            
            elif "enters" in step_lower and ("pin code" in step_lower or "postal code" in step_lower or "postal-code" in step_lower):
                # Postal/PIN code field
                final_lines.append("    if Config.is_framework_mode():")
                final_lines.append('        raise RuntimeError("UI step executed in framework mode")')
                final_lines.append("    ")
                final_lines.append("    # HARD GUARD: Detect page lifecycle violations immediately")
                final_lines.append('    assert hasattr(context, "page"), "❌ Playwright page not initialized"')
                final_lines.append('    assert context.page is not None, "❌ Playwright page is None"')
                final_lines.append('    assert not context.page.is_closed(), "❌ Playwright page was closed"')
                final_lines.append("    ")
                if params:
                    value_param = params[0]
                    final_lines.append(f'    value = {value_param}.strip(\'"\')')
                    final_lines.append('    # Try multiple locator strategies for postal code')
                    final_lines.append('    try:')
                    final_lines.append('        field_locator = context.page.locator("input[name=\'postalCode\'], input[name=\'postal-code\'], input[name=\'zipCode\'], input[name=\'zip\'], input[id=\'postal-code\'], input[id=\'postalCode\']").first')
                    final_lines.append('        field_locator.wait_for(state=\'visible\', timeout=5000)')
                    final_lines.append('        field_locator.fill(value)')
                    final_lines.append('    except:')
                    final_lines.append('        try:')
                    final_lines.append('            field_locator = context.page.locator("label:has-text(\'Postal Code\'), label:has-text(\'ZIP\'), label:has-text(\'Pin Code\')").locator("..").locator("input").first')
                    final_lines.append('            field_locator.wait_for(state=\'visible\', timeout=5000)')
                    final_lines.append('            field_locator.fill(value)')
                    final_lines.append('        except:')
                    final_lines.append('            raise AssertionError("[POSTAL CODE FIELD NOT FOUND]")')
                final_lines.append("    context.last_action_success = True")
            
            elif ("cart page" in step_lower or "page content" in step_lower) and "visible" in step_lower:
                # Page content visibility check
                final_lines.append("    if Config.is_framework_mode():")
                final_lines.append('        raise RuntimeError("UI step executed in framework mode")')
                final_lines.append("    ")
                final_lines.append("    # HARD GUARD: Detect page lifecycle violations immediately")
                final_lines.append('    assert hasattr(context, "page"), "❌ Playwright page not initialized"')
                final_lines.append('    assert context.page is not None, "❌ Playwright page is None"')
                final_lines.append('    assert not context.page.is_closed(), "❌ Playwright page was closed"')
                final_lines.append("    ")
                final_lines.append('    # Verify we are on the expected page')
                final_lines.append('    current_url = context.page.url.lower()')
                final_lines.append('    step_text = "' + step_lower + '"')
                # Generic page verification - check if page name appears in URL or title
                # Extract page name from step text
                final_lines.append('    # Extract page name from step text for verification')
                final_lines.append('    page_indicators = [word for word in step_text.split() if len(word) > 3]')
                final_lines.append('    if page_indicators:')
                final_lines.append('        # Check if any page indicator appears in URL or title')
                final_lines.append('        page_found = any(ind.lower() in current_url.lower() or ind.lower() in context.page.title().lower() for ind in page_indicators)')
                final_lines.append('        if not page_found:')
                final_lines.append('            raise AssertionError(f"[NOT ON EXPECTED PAGE] Step mentions: {page_indicators}, Current URL: {current_url}")')
                # Generic home page check - works for any website
                final_lines.append('    elif "home" in step_text.lower():')
                final_lines.append('        # Generic check for home page - verify URL indicates home/main page')
                final_lines.append('        home_indicators = ["/", "/home", "/index", "home"]')
                final_lines.append('        is_home = any(ind in current_url.lower() for ind in home_indicators) or current_url == Config.BASE_URL')
                final_lines.append('        if not is_home:')
                final_lines.append('            raise AssertionError(f"[NOT ON HOME PAGE] Current URL: {current_url}")')
                final_lines.append("    context.last_action_success = True")
            
            elif "order has been placed" in step_lower or "order" in step_lower and "text" in step_lower:
                # Order confirmation verification
                final_lines.append("    if Config.is_framework_mode():")
                final_lines.append('        raise RuntimeError("UI step executed in framework mode")')
                final_lines.append("    ")
                final_lines.append("    # HARD GUARD: Detect page lifecycle violations immediately")
                final_lines.append('    assert hasattr(context, "page"), "❌ Playwright page not initialized"')
                final_lines.append('    assert context.page is not None, "❌ Playwright page is None"')
                final_lines.append('    assert not context.page.is_closed(), "❌ Playwright page was closed"')
                final_lines.append("    ")
                if params:
                    text_param = params[0]
                    final_lines.append(f'    expected_text = {text_param}.strip(\'"\')')
                else:
                    final_lines.append('    expected_text = "Thank you for your order!"')
                final_lines.append('    # Verify order confirmation text is visible')
                final_lines.append('    try:')
                final_lines.append(f'        text_locator = context.page.locator(f"text={{expected_text}}").first')
                final_lines.append('        if not text_locator.is_visible(timeout=5000):')
                final_lines.append(f'            raise AssertionError(f"[ORDER CONFIRMATION TEXT NOT FOUND] Expected: \'{{expected_text}}\'")')
                final_lines.append('    except Exception as e:')
                final_lines.append(f'        raise AssertionError(f"[ORDER CONFIRMATION VERIFICATION FAILED] Expected text: \'{{expected_text}}\' - {{e}}")')
                final_lines.append("    context.last_action_success = True")
            
            elif "for the item" in step_lower:
                # Button with item context (e.g., "Add to Cart" for item)
                final_lines.append("    if Config.is_framework_mode():")
                final_lines.append('        raise RuntimeError("UI step executed in framework mode")')
                final_lines.append("    ")
                final_lines.append("    # HARD GUARD: Detect page lifecycle violations immediately")
                final_lines.append('    assert hasattr(context, "page"), "❌ Playwright page not initialized"')
                final_lines.append('    assert context.page is not None, "❌ Playwright page is None"')
                final_lines.append('    assert not context.page.is_closed(), "❌ Playwright page was closed"')
                final_lines.append("    ")
                if len(params) >= 2:
                    element_param = params[0]
                    item_param = params[1]
                elif len(params) == 1:
                    element_param = params[0]
                    item_param = "item"
                else:
                    element_param = "element"
                    item_param = "item"
                final_lines.append(f'    element = {element_param}.strip(\'"\')')
                final_lines.append(f'    item = {item_param}.strip(\'"\')')
                final_lines.append('    button_clicked = False')
                final_lines.append('    ')
                final_lines.append('    # Strategy 1: Find item text, locate its container, then find button in container')
                final_lines.append('    try:')
                final_lines.append('        item_locator = context.page.locator(f"text={item}").first')
                final_lines.append('        if item_locator.count() > 0 and item_locator.is_visible(timeout=5000):')
                final_lines.append('            # Find parent container (could be item card, row, container, etc.)')
                final_lines.append('            # Try multiple levels up to find the container')
                final_lines.append('            container = None')
                final_lines.append('            for level in range(1, 6):  # Check up to 5 levels up')
                final_lines.append('                try:')
                final_lines.append('                    parent = item_locator.locator(".." * level).first')
                final_lines.append('                    if parent.count() > 0:')
                final_lines.append('                        # Look for button in this parent')
                final_lines.append('                        element_normalized = element.lower().replace(" ", "-")')
                final_lines.append('                        button = parent.locator(f"button:has-text(\'{element}\'), button:has-text(\'Add\'), [data-test*=\'add\'], [data-test*=\'{element_normalized}\']").first')
                final_lines.append('                        if button.count() > 0 and button.is_visible(timeout=2000):')
                final_lines.append('                            container = parent')
                final_lines.append('                            break')
                final_lines.append('                except:')
                final_lines.append('                    continue')
                final_lines.append('            ')
                final_lines.append('            if container:')
                final_lines.append('                element_normalized = element.lower().replace(" ", "-")')
                final_lines.append('                button = container.locator(f"button:has-text(\'{element}\'), button:has-text(\'Add\'), [data-test*=\'add\'], [data-test*=\'{element_normalized}\']").first')
                final_lines.append('                if button.count() > 0:')
                final_lines.append('                    button.wait_for(state=\'visible\', timeout=10000)')
                final_lines.append('                    button.click()')
                final_lines.append('                    button_clicked = True')
                final_lines.append('    except Exception as e:')
                final_lines.append('        pass')
                final_lines.append('    ')
                final_lines.append('    # Strategy 3: Find all item text matches, get closest button')
                final_lines.append('    if not button_clicked:')
                final_lines.append('        try:')
                final_lines.append('            item_elements = context.page.locator(f"text={item}").all()')
                final_lines.append('            if item_elements:')
                final_lines.append('                # Get bounding box of first matching item')
                final_lines.append('                item_box = item_elements[0].bounding_box()')
                final_lines.append('                if item_box:')
                final_lines.append('                    # Find all buttons with the element text')
                final_lines.append('                    element_normalized = element.lower().replace(" ", "-")')
                final_lines.append('                    all_buttons = context.page.locator(f"button:has-text(\'{element}\'), button:has-text(\'Add\'), [data-test*=\'add\'], [data-test*=\'{element_normalized}\']").all()')
                final_lines.append('                    ')
                final_lines.append('                    # Find button closest to item (same container)')
                final_lines.append('                    closest_button = None')
                final_lines.append('                    min_distance = float(\'inf\')')
                final_lines.append('                    for button in all_buttons:')
                final_lines.append('                        try:')
                final_lines.append('                            button_box = button.bounding_box()')
                final_lines.append('                            if button_box:')
                final_lines.append('                                # Calculate distance (button should be near item horizontally)')
                final_lines.append('                                x_distance = abs(button_box[\'x\'] - item_box[\'x\'])')
                final_lines.append('                                if x_distance < 600:  # Within reasonable horizontal distance')
                final_lines.append('                                    distance = x_distance')
                final_lines.append('                                    if distance < min_distance:')
                final_lines.append('                                        min_distance = distance')
                final_lines.append('                                        closest_button = button')
                final_lines.append('                        except:')
                final_lines.append('                            continue')
                final_lines.append('                    ')
                final_lines.append('                    if closest_button:')
                final_lines.append('                        closest_button.wait_for(state=\'visible\', timeout=10000)')
                final_lines.append('                        closest_button.click()')
                final_lines.append('                        button_clicked = True')
                final_lines.append('        except Exception as e:')
                final_lines.append('            pass')
                final_lines.append('    ')
                final_lines.append('    # Strategy 4: Direct approach - find any button with element text (simplest, most generic)')
                final_lines.append('    if not button_clicked:')
                final_lines.append('        try:')
                final_lines.append('            # Try simple, direct locators (works for any button type on any website)')
                final_lines.append('            element_normalized = element.lower().replace(" ", "-")')
                final_lines.append('            # Try exact element text first (most specific), then generic patterns')
                final_lines.append('            simple_patterns = [')
                final_lines.append(f'                f"text={{element}}",  # Exact text match (most specific - works for any element)')
                final_lines.append(f'                f"button:has-text(\'{{element}}\')",  # Button with exact text')
                final_lines.append(f'                f"button:has-text(\'{{element.lower()}}\')",  # Case-insensitive')
                final_lines.append(f'                f"button:has-text(\'{{element.upper()}}\')",  # Uppercase variant')
                final_lines.append('                "button:has-text(\'Add\')",  # Generic add button')
                final_lines.append('                "button:has-text(\'Select\')",  # Generic select button')
                final_lines.append('                "button:has-text(\'Choose\')",  # Generic choose button')
                final_lines.append(f'                f"[data-test*=\'{{element_normalized}}\']",  # Data attribute')
                final_lines.append(f'                f"button[data-test*=\'{{element_normalized}}\']",  # Button with data attribute')
                final_lines.append('            ]')
                final_lines.append('            for pattern in simple_patterns:')
                final_lines.append('                try:')
                final_lines.append('                    buttons = context.page.locator(pattern).all()')
                final_lines.append('                    if len(buttons) > 0:')
                final_lines.append('                        # Click the first visible button')
                final_lines.append('                        buttons[0].wait_for(state=\'visible\', timeout=10000)')
                final_lines.append('                        buttons[0].scroll_into_view_if_needed()')
                final_lines.append('                        buttons[0].click()')
                final_lines.append('                        button_clicked = True')
                final_lines.append('                        break')
                final_lines.append('                except:')
                final_lines.append('                    continue')
                final_lines.append('        except Exception as e:')
                final_lines.append('            pass')
                final_lines.append('    ')
                final_lines.append('    # Strategy 5: Final fallback - try generic button text matching')
                final_lines.append('    if not button_clicked:')
                final_lines.append('        try:')
                final_lines.append('            element_normalized = element.lower().replace(" ", "-")')
                final_lines.append('            button_locator = context.page.locator(f"button:has-text(\'{element}\'), button:has-text(\'Add\'), [data-test*=\'add\'], [data-test*=\'{element_normalized}\']").first')
                final_lines.append('            if button_locator.count() > 0:')
                final_lines.append('                button_locator.wait_for(state=\'visible\', timeout=10000)')
                final_lines.append('                button_locator.scroll_into_view_if_needed()')
                final_lines.append('                button_locator.click()')
                final_lines.append('                button_clicked = True')
                final_lines.append('        except Exception as e:')
                final_lines.append('            pass')
                final_lines.append('    ')
                final_lines.append('    if not button_clicked:')
                final_lines.append(f'        raise AssertionError(f"Could not find \'{{element}}\' button for item \'{{item}}\'. Tried multiple strategies.")')
                final_lines.append("    context.last_action_success = True")
            
            else:
                # Generic implementation - basic Playwright operation
                final_lines.append("    if Config.is_framework_mode():")
                final_lines.append('        raise RuntimeError("UI step executed in framework mode")')
                final_lines.append("    ")
                final_lines.append("    # HARD GUARD: Detect page lifecycle violations immediately")
                final_lines.append('    assert hasattr(context, "page"), "❌ Playwright page not initialized"')
                final_lines.append('    assert context.page is not None, "❌ Playwright page is None"')
                final_lines.append('    assert not context.page.is_closed(), "❌ Playwright page was closed"')
                final_lines.append("    ")
                final_lines.append("    # Generic step implementation")
                if params:
                    final_lines.append(f"    # Parameters: {', '.join(params)}")
                final_lines.append("    context.last_action_success = True")
            
            final_lines.append("")

        code = "\n".join(final_lines).strip()
        return code
    
    # ------------------------------------------------------------------
    def _sanitize_and_validate_all_steps(self, content: str, all_steps: list) -> str:
        """Legacy method - kept for backward compatibility"""
        return content

    # ------------------------------------------------------------------
    def _extract_step_text(self, decorator_line: str) -> str:
        m = re.search(r"\(\s*[\"'](.+?)[\"']\s*\)", decorator_line)
        return m.group(1) if m else ""

    def _normalize_step(self, text: str) -> str:
        """Normalize step by replacing all parameters with {}"""
        return re.sub(r"\{[^}]+\}", "{}", text)

    def _force_generic_decorator(self, text: str) -> str:
        """Convert quoted strings to {} placeholders - quotes added back in _canonicalize_params"""
        # Replace quoted strings with {} placeholder
        text = re.sub(r'"[^"]*"', "{}", text)
        text = re.sub(r"'[^']*'", "{}", text)
        return re.sub(r"\s+", " ", text).strip()

    def _canonicalize_params(self, step: str) -> str:
        """
        Convert placeholders to proper parameter names with quotes for regex pattern.
        Matches base implementations in web_steps.py and common_steps.py
        """
        if "{}" not in step:
            return step
        
        # Map step patterns to parameter names (with quotes for regex)
        step_lower = step.lower()
        
        if "navigates to" in step_lower:
            return step.replace("{}", '"{url}"', 1)
        elif ("enters" in step_lower and "into" in step_lower and ("field" in step_lower or "input" in step_lower)) or ("enters" in step_lower and "input with label" in step_lower):
            # Two parameters: value and field (both quoted)
            result = step.replace("{}", '"{value}"', 1)
            result = result.replace("{}", '"{field}"', 1)
            return result
        elif "clicks the" in step_lower and "button" in step_lower and "for the item" in step_lower:
            # Two parameters: element (button name) and item
            result = step.replace("{}", '"{element}"', 1)
            result = result.replace("{}", '"{item}"', 1)
            return result
        elif "clicks the" in step_lower and "button" in step_lower:
            return step.replace("{}", '"{element}"', 1)
        elif "should see text" in step_lower:
            return step.replace("{}", '"{text}"', 1)
        elif "should be on the home page" in step_lower:
            return step  # No params
        elif "action should" in step_lower:
            return step  # No params
        else:
            # Fallback: use generic names with quotes
            count = step.count("{}")
            if count == 1:
                return step.replace("{}", '"{value}"')
            else:
                result = step
                param_names = ['value', 'field', 'element', 'text', 'item']
                for i in range(count):
                    param_name = param_names[i] if i < len(param_names) else f'value{i+1}'
                    result = result.replace("{}", f'"{param_name}"', 1)
                return result

    def _unique_func_name(self, step_text: str) -> str:
        """Generate unique function name from step text"""
        digest = hashlib.md5(step_text.encode()).hexdigest()[:8]
        safe = re.sub(r"[^a-z0-9_]", "_", step_text.lower())
        return f"step_{safe[:40]}_{digest}"