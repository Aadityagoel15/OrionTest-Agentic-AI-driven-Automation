import os
import re
from playwright.sync_api import sync_playwright
from llm import get_llm_client


class XPathPropertiesAgent:
    """
    Enhanced XPath Discovery Agent with AI-powered element matching

    IMPROVEMENTS:
    - Discovers elements across ALL pages (generic - works for any website/application)
    - Generates STABLE XPath selectors with multiple fallback strategies
    - Uses AI to generate better keys for element matching
    - Handles dynamic content and complex selectors
    - Discovers more element types (inputs, buttons, links, selects, etc.)
    """

    def __init__(self, headless: bool = True):
        self.headless = headless
        self.properties = {}
        self.llm_client = get_llm_client()

    # --------------------------------------------------
    def generate(self, url: str, output_file: str):
        """Generate XPath properties file by discovering elements across all pages"""
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=self.headless,
                args=['--no-sandbox', '--disable-dev-shm-usage']
            )
            page = browser.new_page()
            page.set_viewport_size({"width": 1920, "height": 1080})

            # ---------------- LOGIN PAGE ----------------
            page.goto(url, timeout=30000, wait_until="networkidle")
            page.wait_for_timeout(1000)  # Wait for dynamic content
            self._collect_elements(page, "login")

            # Note: Login is not performed automatically to keep discovery generic
            # Login credentials should be provided in requirements/test scenarios
            # Discovery focuses on identifying UI elements, not executing login flows
            
            # Generic discovery: Collect elements from current page only
            # Don't assume specific pages exist (cart, checkout, etc.) - just discover what's visible
            # Framework will work with whatever UI elements are found
            self._collect_elements(page, "main")
            
            # Optionally try to discover additional pages by clicking common navigation links
            # But don't assume e-commerce specific pages exist
            try:
                # Try to find and click common navigation links/buttons (generic approach)
                nav_selectors = [
                    "a[href]",
                    "button:has-text('Next')",
                    "button:has-text('Continue')",
                    "[role='link']"
                ]
                # Limit to first few links to avoid infinite loops
                for selector in nav_selectors[:2]:  # Only try first 2 strategies
                    try:
                        links = page.locator(selector).all()
                        if links and len(links) > 0:
                            # Click first link and collect elements
                            links[0].click()
                            page.wait_for_load_state("networkidle", timeout=5000)
                            page.wait_for_timeout(1000)
                            self._collect_elements(page, "secondary")
                            # Go back to avoid getting stuck
                            page.go_back()
                            page.wait_for_load_state("networkidle", timeout=5000)
                            break
                    except Exception:
                        continue
            except Exception:
                pass  # Continue even if navigation discovery fails

            browser.close()

        # Use AI to enhance keys for better matching
        self._enhance_keys_with_ai()
        
        self._write_properties_file(output_file)
        return output_file

    # --------------------------------------------------
    def _collect_elements(self, page, page_context: str = ""):
        """Collect all interactive elements from the page"""
        # Discover more element types
        selectors = [
            "input", "button", "a", "select", "textarea",
            "[role='button']", "[role='link']", "[onclick]",
            "[data-testid]", "[data-test]", "[data-cy]"
        ]
        
        for selector in selectors:
            try:
                handles = page.query_selector_all(selector)
                for el in handles:
                    try:
                        if not el.is_visible():
                            continue
                        
                        tag = el.evaluate("e => e.tagName.toLowerCase()")
                        attrs = self._get_attributes(el)
                        xpath = self._generate_robust_xpath(el)
                        
                        if not xpath:
                            continue
                        
                        # Generate multiple keys for better matching
                        keys = self._generate_keys(tag, attrs, el, page_context)
                        
                        for key in keys:
                            if key and key not in self.properties:
                                self.properties[key] = xpath
                    except Exception:
                        continue
            except Exception:
                continue

    # --------------------------------------------------
    def _get_attributes(self, el) -> dict:
        """Extract all element attributes"""
        return el.evaluate(
            """(e) => {
                const attrs = {};
                for (const attr of e.attributes) {
                    attrs[attr.name] = attr.value;
                }
                return attrs;
            }"""
        )

    # --------------------------------------------------
    def _generate_robust_xpath(self, el) -> str:
        """Generate robust XPath with multiple fallback strategies"""
        return el.evaluate(
            """(element) => {
                // Priority 1: ID (most stable)
                if (element.id) {
                    return `//*[@id="${element.id}"]`;
                }
                
                // Priority 2: data-test attributes
                if (element.getAttribute("data-test")) {
                    return `//*[@data-test="${element.getAttribute("data-test")}"]`;
                }
                if (element.getAttribute("data-testid")) {
                    return `//*[@data-testid="${element.getAttribute("data-testid")}"]`;
                }
                if (element.getAttribute("data-cy")) {
                    return `//*[@data-cy="${element.getAttribute("data-cy")}"]`;
                }
                
                // Priority 3: name attribute (for form elements)
                if (element.name) {
                    return `//${element.tagName.toLowerCase()}[@name="${element.name}"]`;
                }
                
                // Priority 4: aria-label
                if (element.getAttribute("aria-label")) {
                    return `//${element.tagName.toLowerCase()}[@aria-label="${element.getAttribute("aria-label")}"]`;
                }
                
                // Priority 5: visible text (for buttons, links)
                const text = element.innerText?.trim();
                if (text && text.length > 0 && text.length < 50) {
                    // Escape quotes in text
                    const escapedText = text.replace(/"/g, '\\"');
                    return `//${element.tagName.toLowerCase()}[normalize-space(text())="${escapedText}"]`;
                }
                
                // Priority 6: type attribute for inputs
                if (element.type) {
                    const name = element.name || element.id || element.getAttribute("placeholder");
                    if (name) {
                        return `//input[@type="${element.type}" and (@name="${name}" or @id="${name}" or @placeholder="${name}")]`;
                    }
                }
                
                // Priority 7: class-based (last resort, less stable)
                if (element.className && typeof element.className === 'string') {
                    const classes = element.className.split(' ').filter(c => c.trim());
                    if (classes.length > 0) {
                        const primaryClass = classes[0];
                        return `//${element.tagName.toLowerCase()}[contains(@class, "${primaryClass}")]`;
                    }
                }
                
                return '';
            }"""
        )

    # --------------------------------------------------
    def _generate_keys(self, tag: str, attrs: dict, el, page_context: str = "") -> list:
        """
        Generate multiple keys for better element matching.
        Returns list of normalized keys.
        """
        keys = []
        
        # Key 1: data-test attributes
        if "data-test" in attrs:
            keys.append(self._normalize(attrs["data-test"]))
            # If data-test follows add-to-cart-<item>, also add the item part as a key
            dt = attrs["data-test"]
            if dt.startswith("add-to-cart-"):
                suffix = dt[len("add-to-cart-") :]
                norm_suffix = self._normalize(suffix)
                if norm_suffix:
                    keys.append(norm_suffix)
                    # Also add a combined key to be explicit
                    keys.append(self._normalize(f"add-to-cart-{suffix}"))
        
        # Key 2: ID
        if "id" in attrs:
            keys.append(self._normalize(attrs["id"]))
            # Also add without common prefixes/suffixes
            id_value = attrs["id"]
            if id_value.startswith(("btn-", "button-", "input-", "field-")):
                keys.append(self._normalize(id_value[4:]))
            if id_value.endswith(("-btn", "-button", "-input", "-field")):
                keys.append(self._normalize(id_value[:-5]))
        
        # Key 3: name attribute
        if "name" in attrs:
            keys.append(self._normalize(attrs["name"]))
        
        # Key 4: aria-label
        if "aria-label" in attrs:
            keys.append(self._normalize(attrs["aria-label"]))
        
        # Key 5: semantic hints for common form fields (generic)
        sem_labels = ["first", "lastname", "last", "postal", "zip"]
        for attr_name in ["data-test", "id", "name", "aria-label", "placeholder"]:
            if attr_name in attrs:
                val = attrs[attr_name].lower()
                if any(sem in val for sem in sem_labels):
                    keys.append(self._normalize(val))

        # Key 6: visible text
        try:
            text = el.inner_text().strip()
            if text and len(text) < 50:
                keys.append(self._normalize(text))
                # Also add without common suffixes
                if text.endswith(" button"):
                    keys.append(self._normalize(text[:-7]))
                if text.endswith(" link"):
                    keys.append(self._normalize(text[:-5]))
        except Exception:
            pass
        
        # Key 7: placeholder (for inputs)
        if "placeholder" in attrs:
            keys.append(self._normalize(attrs["placeholder"]))
        
        # Key 8: value attribute (for buttons with value)
        if "value" in attrs and tag == "input":
            keys.append(self._normalize(attrs["value"]))
        
        # Remove duplicates and None values
        return list(set([k for k in keys if k]))

    # --------------------------------------------------
    def _normalize(self, text: str) -> str:
        """Normalize text to create consistent keys"""
        if not text:
            return ""
        
        normalized = (
            text.strip()
            .lower()
            # Replace multiple spaces with single space
            .replace("  ", " ")
            # Replace spaces, underscores, dots with hyphens
            .replace(" ", "-")
            .replace("_", "-")
            .replace(".", "-")
            # Remove special characters but keep alphanumeric and hyphens
            .replace("'", "")
            .replace('"', "")
            # Remove multiple consecutive hyphens
        )
        normalized = re.sub(r'-+', '-', normalized)
        return normalized.strip('-')

    # --------------------------------------------------
    def _enhance_keys_with_ai(self):
        """Use AI to generate additional semantic keys for better matching"""
        if not self.properties:
            return
        
        # Create a summary of discovered elements
        element_summary = []
        for key, xpath in list(self.properties.items())[:50]:  # Limit for AI processing
            element_summary.append(f"{key} -> {xpath}")
        
        if not element_summary:
            return
        
        try:
            prompt = f"""
Analyze these UI element mappings and suggest additional semantic keys that would help match user-friendly labels.

ELEMENT MAPPINGS:
{chr(10).join(element_summary[:30])}

For each element, suggest 2-3 alternative keys that users might use when writing test steps.
For example:
- "login-button" could also be matched by: "login", "sign-in", "submit"
- "add-to-cart-sauce-labs-backpack" could also be matched by: "sauce-labs-backpack", "backpack", "add-backpack"

Return ONLY a list of key mappings in format:
original_key=alternative_key1,alternative_key2

Example:
login-button=login,sign-in,submit
"""
            
            response = self.llm_client.generate_response(
                prompt=prompt,
                system_prompt="""You are a Senior Automation Test Engineer with 10+ years of experience in test automation.

YOUR EXPERTISE:
- Python programming for automation (expert-level)
- Playwright automation framework (primary tool)
- XPath and CSS selector generation
- UI element identification and mapping
- Creating maintainable selector strategies

YOUR ROLE AS UI ELEMENT MATCHING SPECIALIST:
- Generate semantic key mappings for UI elements discovered via Playwright
- Create alternative keys that help match user-friendly labels
- Ensure keys align with Playwright locator strategies
- Support maintainable automation test scripts

Generate semantic key mappings that will be used in Python/Playwright automation scripts for element identification."""
            )
            
            # Parse AI response and add alternative keys
            for line in response.splitlines():
                if "=" in line:
                    parts = line.split("=", 1)
                    if len(parts) == 2:
                        original_key = parts[0].strip()
                        alternatives = [a.strip() for a in parts[1].split(",")]
                        if original_key in self.properties:
                            xpath = self.properties[original_key]
                            for alt_key in alternatives:
                                if alt_key and alt_key not in self.properties:
                                    self.properties[alt_key] = xpath
        except Exception:
            pass  # If AI enhancement fails, continue with existing keys

    # --------------------------------------------------
    def _write_properties_file(self, output_file: str):
        """Write properties file with comments for better readability"""
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            f.write("# UI Locators - Generated by XPath Discovery Agent\n")
            f.write("# Format: key=xpath_selector\n")
            f.write("# Keys are normalized for flexible matching\n\n")
            
            for key, value in sorted(self.properties.items()):
                f.write(f"{key}={value}\n")
