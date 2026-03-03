"""
Requirements-Aware UI Discovery Agent

This agent:
1. Reads requirements
2. Navigates to the website using Playwright
3. Discovers actual UI element names/text from the live website
4. Maps requirements to discovered elements
5. Returns enriched requirements with actual UI element names

This ensures code generation is based on REAL UI elements, not guessed names.
"""

from playwright.sync_api import sync_playwright
from llm import get_llm_client
import re
from typing import Dict, List, Tuple
from utils.logging_utils import get_logger

logger = get_logger()


class RequirementsAwareUIDiscoveryAgent:
    """
    Enhanced UI Discovery that maps requirements to actual UI elements
    """

    def __init__(self, headless: bool = True):
        self.headless = headless
        self.llm_client = get_llm_client()
        self.discovered_elements = {}

    def discover_and_map(self, requirements: str, base_url: str) -> Dict:
        """
        Discover UI elements from the website and map them to requirements
        
        Returns:
            {
                'discovered_elements': {
                    'buttons': {'Add to cart': {...}, 'Checkout': {...}},
                    'inputs': {'username': {...}, 'password': {...}},
                    'links': {'Cart': {...}},
                    ...
                },
                'requirements_mapping': {
                    'Add to cart': 'Add to cart',  # Requirement term → Actual UI text
                    'Cart': 'Shopping Cart',       # Requirement term → Actual UI text
                    ...
                },
                'enriched_requirements': '...'  # Requirements with actual UI names
            }
        """
        logger.info(f"Starting requirements-aware UI discovery for: {base_url}")
        
        # Step 1: Extract actionable terms from requirements
        requirement_terms = self._extract_requirement_terms(requirements)
        logger.info(f"Extracted requirement terms: {requirement_terms}")
        
        # Step 2: Extract login credentials if present in requirements
        login_creds = self._extract_login_credentials(requirements)
        logger.info(f"Extracted login credentials: username={login_creds.get('username') if login_creds else 'None'}, password={'***' if login_creds and login_creds.get('password') else 'None'}")
        
        # Step 3: Discover actual UI elements from the website (with login attempt if credentials found)
        discovered = self._discover_ui_elements(base_url, login_creds=login_creds)
        logger.info(f"Discovered {len(discovered.get('buttons', []))} buttons, "
                   f"{len(discovered.get('inputs', []))} inputs, "
                   f"{len(discovered.get('links', []))} links")
        
        # Step 3: Map requirement terms to discovered elements
        mapping = self._map_requirements_to_elements(requirement_terms, discovered)
        logger.info(f"Created mapping: {mapping}")
        
        # Step 4: Enrich requirements with actual UI element names
        enriched_requirements = self._enrich_requirements(requirements, mapping)
        
        return {
            'discovered_elements': discovered,
            'requirements_mapping': mapping,
            'enriched_requirements': enriched_requirements,
            'ui_semantics': discovered.get('ui_semantics', {}),  # NEW: Return UI role semantics
            'discovery_stats': {
                'buttons_found': len(discovered.get('buttons', [])),
                'inputs_found': len(discovered.get('inputs', [])),
                'links_found': len(discovered.get('links', [])),
                'terms_mapped': len([v for v in mapping.values() if v])
            }
        }

    def _extract_requirement_terms(self, requirements: str) -> List[str]:
        """Extract actionable terms from requirements (buttons, links, actions)"""
        # Common patterns: "click X", "navigate to X", "enter into X", "add X", etc.
        patterns = [
            # Pattern for clicks - improved to skip "on/the" and capture the actual button name
            r'(?:click|press|select|choose)\s+(?:on\s+)?(?:the\s+)?["\']?([^"\'\n]+?)["\']?\s+(?:button|link|element)',
            # Pattern for navigation
            r'(?:navigate|go)\s+(?:to|back to)\s+(?:the\s+)?["\']?([^"\'\n]+?)["\']?\s*(?:page|screen)?',
            # Pattern for entering text into fields
            r'(?:enter|input|type)\s+(?:[^-]+?)\s+(?:into|in|as)\s+(?:the\s+)?["\']?([^"\'\n]+?)["\']?\s+(?:field|input|box)?',
            # Pattern for verification text
            r'(?:should see|verify|check|text shown.*?as)\s+["\']([^"\']+)["\']',
            # Pattern for quoted capitalized terms (button names)
            r'["\']([A-Z][^"\']{2,30})["\']',
        ]
        
        terms = set()
        for pattern in patterns:
            matches = re.findall(pattern, requirements, re.IGNORECASE)
            terms.update([m.strip() for m in matches if len(m.strip()) > 2])
        
        # Also extract quoted strings (likely UI element names)
        quoted = re.findall(r'["\']([^"\']+)["\']', requirements)
        terms.update([q.strip() for q in quoted if len(q.strip()) > 2 and q.strip()[0].isupper()])
        
        return list(terms)

    def _extract_login_credentials(self, requirements: str) -> Dict[str, str]:
        """Extract username and password from requirements if present"""
        creds = {}
        
        # Try to find username - multiple patterns to match different requirement formats
        username_patterns = [
            r'User\s+name\s+["\']([^"\']+?)["\']',  # User name "standard_user" (from requirements file)
            r'["\']([^"\']+?)["\']\s+into\s+(?:the\s+)?["\']?username["\']?\s+field',  # "standard_user" into username field
            r'(?:username|user)[\s:=]+["\']([^"\']+?)["\']',  # username: "standard_user"
            r'["\']([^"\']+?)["\']\s+into\s+.*?username',  # More flexible
        ]
        for pattern in username_patterns:
            match = re.search(pattern, requirements, re.IGNORECASE)
            if match:
                value = match.group(1).strip()
                if len(value) > 2 and value.lower() not in ['the', 'user', 'with', 'into', 'name']:  # Filter out common words
                    creds['username'] = value
                    logger.info(f"Extracted username: {value}")
                    break
        
        # Try to find password - multiple patterns to match different requirement formats
        password_patterns = [
            r'Password\s+as\s+["\']([^"\']+?)["\']',  # Password as "secret_sauce" (from requirements file)
            r'["\']([^"\']+?)["\']\s+into\s+(?:the\s+)?["\']?password["\']?\s+field',  # "secret_sauce" into password field
            r'(?:password|pass)[\s:=]+["\']([^"\']+?)["\']',  # password: "secret_sauce"
            r'["\']([^"\']+?)["\']\s+into\s+.*?password',  # More flexible
        ]
        for pattern in password_patterns:
            match = re.search(pattern, requirements, re.IGNORECASE)
            if match:
                value = match.group(1).strip()
                if len(value) > 2 and value.lower() not in ['the', 'user', 'with', 'into', 'as']:  # Filter out common words
                    creds['password'] = value
                    logger.info(f"Extracted password: {'*' * len(value)}")
                    break
        
        return creds

    def _discover_ui_elements(self, base_url: str, login_creds: Dict[str, str] = None) -> Dict:
        """Discover actual UI elements from the website"""
        discovered = {
            'buttons': [],
            'inputs': [],
            'links': [],
            'text_elements': [],
            'selects': [],
            'ui_semantics': {}  # NEW: Store UI role semantics (button, link, etc.)
        }
        
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=self.headless,
                args=['--no-sandbox', '--disable-dev-shm-usage']
            )
            page = browser.new_page()
            page.set_viewport_size({"width": 1920, "height": 1080})
            
            try:
                logger.info(f"Navigating to: {base_url}")
                page.goto(base_url, timeout=30000, wait_until="networkidle")
                page.wait_for_timeout(2000)  # Wait for dynamic content
                
                # Try to log in if credentials are provided
                if login_creds and login_creds.get('username') and login_creds.get('password'):
                    logger.info(f"Attempting login with username: {login_creds.get('username')}")
                    try:
                        # Try to find and fill username field
                        username_selectors = [
                            "input[name*='user']",
                            "input[id*='user']",
                            "input[type='text']",
                            "input[placeholder*='user' i]"
                        ]
                        for selector in username_selectors:
                            try:
                                username_input = page.locator(selector).first
                                if username_input.count() > 0 and username_input.is_visible():
                                    username_input.fill(login_creds['username'])
                                    logger.info("Filled username field")
                                    break
                            except:
                                continue
                        
                        # Try to find and fill password field
                        password_selectors = [
                            "input[type='password']",
                            "input[name*='pass']",
                            "input[id*='pass']"
                        ]
                        for selector in password_selectors:
                            try:
                                password_input = page.locator(selector).first
                                if password_input.count() > 0 and password_input.is_visible():
                                    password_input.fill(login_creds['password'])
                                    logger.info("Filled password field")
                                    break
                            except:
                                continue
                        
                        # Try to click login button
                        login_button_selectors = [
                            "button:has-text('Login')",
                            "input[type='submit']",
                            "button[type='submit']",
                            "button:has-text('Sign in')",
                            "button:has-text('Log in')"
                        ]
                        for selector in login_button_selectors:
                            try:
                                login_btn = page.locator(selector).first
                                if login_btn.count() > 0 and login_btn.is_visible():
                                    login_btn.click()
                                    page.wait_for_load_state("networkidle", timeout=15000)
                                    page.wait_for_timeout(3000)  # Wait longer for products page to render
                                    logger.info("Login successful, discovering post-login elements")
                                    break
                            except:
                                continue
                    except Exception as e:
                        logger.warning(f"Login attempt failed: {e}, continuing with pre-login page")
                
                # Discover buttons - wait a bit more for dynamic content
                page.wait_for_timeout(2000)
                
                # Get all buttons (including those inside containers) - use more comprehensive selectors
                button_selectors = [
                    "button",
                    "[role='button']",
                    "input[type='button']",
                    "input[type='submit']",
                    "a[role='button']",
                    "[data-test*='button']",
                    "[data-test*='add']",
                    "[data-test*='cart']"
                ]
                
                all_buttons = []
                for selector in button_selectors:
                    try:
                        buttons = page.locator(selector).all()
                        all_buttons.extend(buttons)
                    except Exception:
                        continue
                
                logger.info(f"Found {len(all_buttons)} button elements on page")
                
                seen_texts = set()  # Track unique button texts to avoid duplicates
                
                for btn in all_buttons:
                    try:
                        if not btn.is_visible():
                            continue
                        
                        # CRITICAL FIX: Check actual HTML tag name FIRST to filter out links
                        tag_name = None
                        try:
                            tag_name = btn.evaluate("el => el.tagName.toLowerCase()")
                        except Exception as e:
                            logger.debug(f"Could not get tag name: {e}")
                        
                        # Skip <a> tags unless they explicitly have role='button'
                        # This prevents links from being incorrectly classified as buttons
                        if tag_name == "a":
                            role_attr = btn.get_attribute("role")
                            if role_attr != "button":
                                logger.debug(f"Skipping <a> tag without role='button': {btn.get_attribute('data-test')}")
                                continue  # Skip this element - it's a link, not a button
                        
                        # Try multiple ways to get button text/identifier
                        text = btn.inner_text().strip() or ""
                        if not text:
                            text = btn.get_attribute("value") or ""
                        if not text:
                            text = btn.get_attribute("aria-label") or ""
                        if not text:
                            text = btn.get_attribute("title") or ""
                        if not text:
                            # Use data-test as text if available
                            data_test = btn.get_attribute("data-test")
                            if data_test:
                                text = data_test.replace("-", " ").replace("_", " ")
                        
                        # Also get data-test attribute separately (important for sites using data-test attributes)
                        data_test = btn.get_attribute("data-test")
                        
                        # Find associated item name by looking in parent container
                        item_name = ""
                        try:
                            # First, try to extract item name from data-test attribute (works for ANY item)
                            # Example: "add-to-cart-sauce-labs-backpack" -> "Sauce Labs Backpack"
                            if data_test and ('add-to-cart' in data_test.lower() or 'add_to_cart' in data_test.lower()):
                                # Remove prefix and extract item part
                                item_part = data_test.replace('add-to-cart-', '').replace('add_to_cart_', '').replace('add-to-cart_', '').replace('add_to_cart-', '').strip()
                                if item_part:
                                    # Convert kebab-case/snake_case to Title Case
                                    # "sauce-labs-backpack" -> "Sauce Labs Backpack"
                                    parts = item_part.replace('_', '-').split('-')
                                    # Filter out empty parts and clean up
                                    parts = [p for p in parts if p and not p.isdigit()]  # Remove empty and pure numbers
                                    if len(parts) >= 1:
                                        item_name = ' '.join([p.capitalize() for p in parts])
                                        logger.debug(f"Extracted item name '{item_name}' from data-test '{data_test}'")
                            
                            # Also try to find product/item name in the same container as the button
                            if not item_name:
                                for level in range(1, 6):  # Check up to 5 levels up
                                    try:
                                        # Get parent using evaluate (more reliable)
                                        parent_xpath = btn.evaluate("""
                                            (el) => {
                                                let current = el;
                                                for (let i = 0; i < arguments[0]; i++) {
                                                    current = current.parentElement;
                                                    if (!current) break;
                                                }
                                                return current ? current : null;
                                            }
                                        """, level)
                                        if parent_xpath:
                                            # Try to find item name in parent - use multiple selectors
                                            selectors = [
                                                "h3", "h4", "h2", 
                                                "a[href*='id']", 
                                                ".inventory_item_name", 
                                                ".product-name",
                                                "[class*='item-name']",
                                                "[class*='product-name']",
                                                "div[class*='inventory'] a"
                                            ]
                                            for selector in selectors:
                                                try:
                                                    item_elem = btn.locator(f"xpath=ancestor::*/descendant::{selector}").first
                                                    if item_elem.count() > 0:
                                                        item_text = item_elem.inner_text().strip()
                                                        if item_text and 5 < len(item_text) < 100:
                                                            item_name = item_text
                                                            break
                                                except:
                                                    continue
                                            if item_name:
                                                break
                                    except:
                                        continue
                        except Exception as e:
                            logger.debug(f"Error extracting item name: {e}")
                            pass
                        
                        # Note: tag_name already checked at the beginning of the loop
                        # to filter out links masquerading as buttons
                        
                        # Create button info with all attributes
                        button_info = {
                            'text': text if text else "",
                            'type': 'button',
                            'tag_name': tag_name,  # NEW: Store actual HTML tag name
                            'data_test': data_test if data_test else "",
                            'id': btn.get_attribute("id") or "",
                            'name': btn.get_attribute("name") or "",
                            'class': btn.get_attribute("class") or "",
                            'aria_label': btn.get_attribute("aria-label") or "",
                            'item_name': item_name,  # Associated item name if found
                            'xpath': self._get_element_xpath(btn)
                        }
                        
                        # Create unique key using data-test (most reliable) or combination of attributes
                        if data_test:
                            unique_key = data_test.lower().strip()
                        elif text:
                            # For buttons with same text, use combination with item name
                            if item_name:
                                unique_key = f"{text.lower().strip()}|{item_name.lower().strip()}"
                            else:
                                unique_key = text.lower().strip()
                        else:
                            unique_key = btn.get_attribute("id") or str(len(discovered['buttons']))
                        
                        # Store button (allow multiple "Add to cart" buttons if they're for different items)
                        if unique_key not in seen_texts or item_name:  # Always add if we found an item name
                            seen_texts.add(unique_key)
                            discovered['buttons'].append(button_info)
                            logger.info(f"Discovered button: text='{text}', data-test='{data_test}', item='{item_name}'")
                            
                            # Store UI semantics (role + text) for feature generation
                            if text:
                                semantic_key = text.lower().strip()
                                
                                # Determine role based on ACTUAL HTML tag name from browser DOM
                                # This is the most accurate way - check what the browser sees
                                role = "button"  # Default
                                
                                # Priority 1: Check actual HTML tag name (most reliable)
                                if tag_name == "a":
                                    role = "link"  # It's an <a> tag - definitely a link
                                elif tag_name == "button":
                                    role = "button"  # It's a <button> tag - definitely a button
                                # Priority 2: Check data-test attribute for semantic hints
                                elif data_test and "link" in data_test.lower():
                                    role = "link"  # data-test suggests it's a link
                                # Priority 3: Check text content for semantic hints
                                elif "link" in text.lower() and "button" not in text.lower():
                                    role = "link"  # Text suggests it's a link
                                
                                discovered['ui_semantics'][semantic_key] = {
                                    "role": role,
                                    "text": text,
                                    "tag_name": tag_name,  # NEW: Store tag name for reference
                                    "data_test": data_test,
                                    "xpath": button_info.get("xpath", ""),
                                    "item_name": item_name if item_name else None
                                }
                    except Exception as e:
                        logger.debug(f"Error processing button: {e}")
                        continue
                
                logger.info(f"Stored {len(discovered['buttons'])} unique buttons after deduplication")
                
                # 🔑 UNIVERSAL UI RULE: Detect ambiguous actions (same button text appears multiple times)
                # If multiple identical actions exist, they MUST be scoped to a container.
                # This is a UI truth, not site-specific.
                button_text_counts = {}
                for btn_info in discovered['buttons']:
                    btn_text = btn_info.get('text', '').strip()
                    if btn_text:
                        btn_text_lower = btn_text.lower()
                        if btn_text_lower not in button_text_counts:
                            button_text_counts[btn_text_lower] = []
                        button_text_counts[btn_text_lower].append(btn_info)
                
                        # Mark actions that require context (appear multiple times)
                        ambiguous_actions = set()
                        for btn_text_lower, btn_list in button_text_counts.items():
                            if len(btn_list) > 1:
                                # Same button text appears multiple times - requires context
                                ambiguous_actions.add(btn_text_lower)
                                logger.info(f"[WARNING] Ambiguous action detected: '{btn_list[0].get('text')}' appears {len(btn_list)} times - REQUIRES CONTEXT")
                        
                        # Update UI semantics to mark as requiring context
                        if btn_text_lower in discovered['ui_semantics']:
                            discovered['ui_semantics'][btn_text_lower]['requires_context'] = True
                            discovered['ui_semantics'][btn_text_lower]['count'] = len(btn_list)
                            # Check if any of these buttons have associated item names
                            has_item_names = any(btn.get('item_name') for btn in btn_list)
                            discovered['ui_semantics'][btn_text_lower]['has_item_names'] = has_item_names
                            if has_item_names:
                                item_names = [btn.get('item_name') for btn in btn_list if btn.get('item_name')]
                                discovered['ui_semantics'][btn_text_lower]['item_names'] = item_names
                                logger.info(f"   -> Found item names: {item_names}")
                
                # Store ambiguous actions metadata for feature generation
                discovered['ambiguous_actions'] = list(ambiguous_actions)
                logger.info(f"Found {len(ambiguous_actions)} ambiguous actions requiring context")
                
                # Discover inputs
                inputs = page.locator("input[type='text'], input[type='email'], input[type='password'], input[type='number'], textarea").all()
                for inp in inputs:
                    try:
                        if not inp.is_visible():
                            continue
                        name = inp.get_attribute("name") or inp.get_attribute("id") or inp.get_attribute("placeholder") or ""
                        if name:
                            discovered['inputs'].append({
                                'name': name,
                                'type': inp.get_attribute("type") or "text",
                                'placeholder': inp.get_attribute("placeholder"),
                                'id': inp.get_attribute("id"),
                                'label': self._find_input_label(inp, page),
                                'xpath': self._get_element_xpath(inp)
                            })
                    except Exception:
                        continue
                
                # Discover links - include cart/shopping links even without href
                # The shopping cart is often an <a> tag with data-test but no href
                links = page.locator("a[href], [role='link'], a[data-test*='cart'], a[data-test*='shopping']").all()
                logger.info(f"Found {len(links)} total link elements")
                for link in links[:20]:  # Limit to avoid too many
                    try:
                        if not link.is_visible():
                            continue
                        # Try multiple ways to get link text/identifier
                        text = link.inner_text().strip() or link.get_attribute("aria-label") or link.get_attribute("title") or ""
                        
                        # CRITICAL: If link has no text, try data-test attribute
                        if not text:
                            data_test = link.get_attribute("data-test")
                            if data_test:
                                # Convert data-test to readable text (e.g., "shopping-cart-link" -> "Shopping Cart Link")
                                text = ' '.join(word.capitalize() for word in data_test.replace('-', ' ').replace('_', ' ').split())
                        
                        href = link.get_attribute("href") or ""
                        if text or href:  # Accept links with either text OR href
                            # Check actual HTML tag name from browser DOM (most accurate)
                            tag_name = None
                            try:
                                tag_name = link.evaluate("el => el.tagName.toLowerCase()")
                            except Exception as e:
                                logger.debug(f"Could not get link tag name: {e}")
                            
                            link_info = {
                                'text': text,
                                'href': href,
                                'tag_name': tag_name,  # NEW: Store actual HTML tag name
                                'id': link.get_attribute("id"),
                                'xpath': self._get_element_xpath(link)
                            }
                            discovered['links'].append(link_info)
                            
                            # Store UI semantics (role + text) for feature generation
                            semantic_key = text.lower().strip()
                            discovered['ui_semantics'][semantic_key] = {
                                "role": "link",  # Links are always links
                                "text": text,
                                "tag_name": tag_name,  # NEW: Store tag name for reference
                                "href": href,
                                "xpath": link_info.get("xpath", "")
                            }
                    except Exception:
                        continue
                
                # Discover visible text elements (for verification)
                text_elements = page.locator("h1, h2, h3, p, span, div").all()
                for elem in text_elements[:50]:  # Limit to avoid too many
                    try:
                        if not elem.is_visible():
                            continue
                        text = elem.inner_text().strip()
                        if text and 10 < len(text) < 200 and not any(c in text for c in ['{', '}', '<script']):
                            discovered['text_elements'].append({
                                'text': text[:100],  # Truncate long text
                                'tag': elem.evaluate("e => e.tagName.toLowerCase()"),
                                'xpath': self._get_element_xpath(elem)
                            })
                    except Exception:
                        continue
                
                browser.close()
                
            except Exception as e:
                logger.error(f"Error during UI discovery: {e}")
                browser.close()
        
        # Don't remove duplicates - keep all buttons, especially if they have different item associations
        # Just log the count
        logger.info(f"Found {len(discovered['buttons'])} buttons total (including duplicates with different item contexts)")
        
        discovered['inputs'] = self._deduplicate_list(discovered['inputs'], 'name')
        discovered['links'] = self._deduplicate_list(discovered['links'], 'text')
        
        logger.info(f"After deduplication: {len(discovered['buttons'])} buttons, {len(discovered['inputs'])} inputs, {len(discovered['links'])} links")
        
        return discovered

    def _map_requirements_to_elements(self, requirement_terms: List[str], discovered: Dict) -> Dict[str, str]:
        """Map requirement terms to actual discovered UI element names"""
        mapping = {}
        
        # Log all discovered buttons and links for debugging
        logger.info(f"Mapping terms against {len(discovered.get('buttons', []))} discovered buttons")
        for btn in discovered.get('buttons', [])[:10]:  # Log first 10 buttons
            btn_text = btn.get('text') or ''
            data_test = btn.get('data_test') or ''
            aria_label = btn.get('aria_label') or ''
            item_name = btn.get('item_name') or ''
            logger.info(f"  Button: text='{btn_text}', data-test='{data_test}', item='{item_name}'")
        
        logger.info(f"Discovered {len(discovered.get('links', []))} links")
        for link in discovered.get('links', []):  # Log ALL links
            link_text = link.get('text') or ''
            href = link.get('href') or ''
            logger.info(f"  Link: text='{link_text}', href='{href}'")
        
        for term in requirement_terms:
            term_lower = term.lower().strip()
            best_match = None
            best_score = 0
            best_match_type = None  # Track whether best match is button or link
            
            # CRITICAL FIX: Check BOTH buttons AND links, then decide based on context
            # This prevents "Cart" from matching "Add to cart" button when a cart link exists
            
            # Try to match against buttons - check text, data-test, item name, and aria-label
            for btn in discovered.get('buttons', []):
                # Safely get button attributes (handle None values)
                btn_text = (btn.get('text') or '').strip()
                if btn_text:
                    btn_text_lower = btn_text.lower()
                    score = self._calculate_similarity(term_lower, btn_text_lower)
                else:
                    score = 0.0
                
                # Also check data-test attribute (important for sites using data-test attributes like "add-to-cart-item-name")
                data_test = (btn.get('data_test') or '').strip()
                if data_test:
                    data_test_lower = data_test.lower()
                    # Normalize data-test (replace hyphens/underscores with spaces for matching)
                    data_test_normalized = data_test_lower.replace('-', ' ').replace('_', ' ')
                    data_test_score = self._calculate_similarity(term_lower, data_test_normalized)
                    score = max(score, data_test_score)
                    
                    # Also check if data-test contains the requirement term (e.g., "add-to-cart" contains "add to cart")
                    if term_lower.replace(' ', '-') in data_test_lower or term_lower.replace(' ', '_') in data_test_lower:
                        score = max(score, 0.9)  # High score for data-test match
                
                # Check associated item name
                item_name = (btn.get('item_name') or '').strip()
                if item_name:
                    item_name_lower = item_name.lower()
                    item_score = self._calculate_similarity(term_lower, item_name_lower)
                    score = max(score, item_score)
                
                # Also check aria-label
                aria_label = (btn.get('aria_label') or '').strip()
                if aria_label:
                    aria_label_lower = aria_label.lower()
                    aria_score = self._calculate_similarity(term_lower, aria_label_lower)
                    score = max(score, aria_score)
                
                # CRITICAL: Penalize action buttons when term doesn't contain action words
                # This prevents "Cart" from matching "Add to cart" button
                if ("add" in btn_text_lower or "remove" in btn_text_lower) and ("add" not in term_lower and "remove" not in term_lower):
                    score -= 0.6  # Heavy penalty for action buttons when looking for navigation
                
                if score > best_score and score > 0.3:  # Lowered threshold to 30% for better matching
                    best_score = score
                    best_match_type = 'button'
                    # Prefer actual text, but use data-test if text is empty
                    if btn_text:
                        best_match = btn_text
                    elif data_test:
                        # For data-test, use the button text if available, otherwise use normalized data-test
                        best_match = btn_text if btn_text else data_test.replace('-', ' ').replace('_', ' ')
                    else:
                        best_match = aria_label or btn.get('id', '')
            
            # Try to match against links (ALWAYS check, not just when no button match)
            for link in discovered.get('links', []):
                link_text = (link.get('text') or '').strip()
                link_text_lower = link_text.lower()
                score = self._calculate_similarity(term_lower, link_text_lower)
                
                # Boost links for single-word navigation terms (like "Cart", "Home")
                if len(term_lower.split()) == 1 and "add" not in term_lower and "remove" not in term_lower:
                    score += 0.3  # Prefer links for simple navigation
                
                if score > best_score and score > 0.3:  # Same threshold as buttons
                    best_score = score
                    best_match_type = 'link'
                    best_match = link_text
            
            # Try to match against inputs (ALWAYS check, not just when no button/link match)
            for inp in discovered.get('inputs', []):
                inp_name = (inp.get('name') or inp.get('label') or inp.get('placeholder') or '').lower()
                score = self._calculate_similarity(term_lower, inp_name)
                if score > best_score and score > 0.5:
                    best_score = score
                    best_match_type = 'input'
                    best_match = inp.get('name') or inp.get('label')
            
            if best_match:
                mapping[term] = best_match
                logger.info(f"Mapped requirement term '{term}' -> actual UI element '{best_match}' ({best_match_type}, score: {best_score:.2f})")
            else:
                # Keep original term if no match found (will use generic locators)
                mapping[term] = term
                logger.info(f"No UI match found for '{term}', keeping original term")
        
        return mapping

    def _calculate_similarity(self, term1: str, term2: str) -> float:
        """Calculate similarity score between two strings"""
        if not term1 or not term2:
            return 0.0
        
        term1 = term1.lower().strip()
        term2 = term2.lower().strip()
        
        # Exact match
        if term1 == term2:
            return 1.0
        
        # Substring match
        if term1 in term2 or term2 in term1:
            return 0.8
        
        # Word overlap
        words1 = set(term1.split())
        words2 = set(term2.split())
        if words1 and words2:
            overlap = len(words1.intersection(words2))
            total = len(words1.union(words2))
            if total > 0:
                return overlap / total
        
        # Levenshtein-like (simple)
        max_len = max(len(term1), len(term2))
        if max_len == 0:
            return 0.0
        common_chars = sum(1 for c in term1 if c in term2)
        return common_chars / max_len

    def _enrich_requirements(self, requirements: str, mapping: Dict[str, str]) -> str:
        """Enrich requirements by replacing terms with actual UI element names"""
        enriched = requirements
        
        # Replace mapped terms with actual UI names (but keep original if no match)
        for original_term, actual_name in mapping.items():
            if original_term != actual_name:  # Only replace if we found a match
                # Replace in quotes
                enriched = re.sub(
                    rf'["\']{re.escape(original_term)}["\']',
                    f'"{actual_name}"',
                    enriched,
                    flags=re.IGNORECASE
                )
                # Replace without quotes
                enriched = re.sub(
                    rf'\b{re.escape(original_term)}\b',
                    actual_name,
                    enriched,
                    flags=re.IGNORECASE
                )
        
        return enriched

    def _get_element_xpath(self, element) -> str:
        """Generate XPath for an element"""
        try:
            return element.evaluate("""
                (el) => {
                    if (el.id) return `//*[@id="${el.id}"]`;
                    if (el.getAttribute('data-test')) return `//*[@data-test="${el.getAttribute('data-test')}"]`;
                    const tag = el.tagName.toLowerCase();
                    const text = el.innerText?.trim();
                    if (text && text.length < 50) {
                        return `//${tag}[normalize-space(text())="${text.replace(/"/g, '\\"')}"]`;
                    }
                    return `//${tag}`;
                }
            """)
        except Exception:
            return ""

    def _find_input_label(self, input_element, page) -> str:
        """Find associated label for an input element"""
        try:
            # Try by 'for' attribute
            input_id = input_element.get_attribute("id")
            if input_id:
                label = page.locator(f"label[for='{input_id}']").first
                if label.count() > 0:
                    return label.inner_text().strip()
            
            # Try parent label
            parent = input_element.locator("..").first
            if parent.count() > 0:
                parent_tag = parent.evaluate("e => e.tagName.toLowerCase()")
                if parent_tag == "label":
                    return parent.inner_text().strip()
            
            # Try preceding label
            try:
                label = input_element.locator("preceding-sibling::label").first
                if label.count() > 0:
                    return label.inner_text().strip()
            except:
                pass
        except Exception:
            pass
        return ""

    def _deduplicate_list(self, items: List[Dict], key: str) -> List[Dict]:
        """Remove duplicate items based on a key"""
        seen = set()
        result = []
        for item in items:
            value = item.get(key, '').lower().strip()
            if value and value not in seen:
                seen.add(value)
                result.append(item)
        return result

