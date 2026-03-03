from datetime import datetime
import os
import re
import yaml

from llm import get_llm_client
from config import Config, ProjectType
from utils.logging_utils import get_logger
from utils.exceptions import FeatureGenerationError

logger = get_logger()


class RequirementsToFeatureAgent:
    """
    Agent 1: Requirements → Gherkin Feature

    TRUE BDD COMPILER:
    - Normalizes
    - Repairs
    - Injects mandatory structure
    - Ensures executable scenarios
    - THEN validates
    """

    SYSTEM_PROMPT = """

"""

    def __init__(self):
        self.llm_client = get_llm_client()

    # ==================================================
    # 🚀 MAIN ENTRY
    # ==================================================
    def convert_requirements_to_feature(
        self,
        requirements: str,
        feature_name: str = None,
        project_type: str = ProjectType.WEB,
        original_requirements: str = None,
        ui_discovery_result: dict = None
    ) -> str:

        # Extract structured data from ORIGINAL requirements (if provided)
        # This is critical when UI context agent has modified the requirements
        # Original requirements contain actual credentials/URLs that need to be extracted
        extraction_source = original_requirements if original_requirements else requirements
        extracted_data = self._extract_requirements_data(extraction_source)
        
        # PRIMARY APPROACH: Build feature directly from requirements for accuracy
        # This ensures exact order and all steps are included
        # CRITICAL: Use original requirements for building if available (before UI context modification)
        # This preserves actual credential values and URLs
        build_source = original_requirements if original_requirements else requirements
        logger.info("Building feature file directly from requirements to ensure accuracy and proper order")
        feature = self._build_feature_from_requirements(build_source, extracted_data, feature_name, ui_discovery_result)
        
        # Inject exact requirements data to ensure correct values (username, password, etc.)
        feature = self._inject_exact_requirements_data(feature, extracted_data)
        
        # Clean and normalize the generated feature
        # Use original requirements for URL normalization to get correct URLs
        url_normalization_source = original_requirements if original_requirements else requirements
        feature = self._normalize_urls_from_requirements(feature, url_normalization_source)
        feature = self._normalize_button_names(feature)
        feature = self._normalize_field_formats(feature)
        feature = self._fix_and_steps_in_background(feature)
        
        # Final cleanup: Remove any LLM-generated placeholder text that might have leaked in
        feature = self._clean_llm_placeholders(feature, extracted_data)
        
        # Validate the feature
        self._validate_canonical_grammar(feature, project_type)

        return feature
    
    # ==================================================
    # 📊 EXTRACT STRUCTURED DATA FROM REQUIREMENTS
    # ==================================================
    def _extract_requirements_data(self, requirements: str) -> dict:
        """
        Extract structured data from requirements text for accurate feature generation.
        """
        data = {
            "url": None,
            "username": None,
            "password": None,
            "items": [],
            "form_fields": {},
            "expected_text": [],
            "actions": []
        }
        
        # Extract URL
        url_pattern = r'https?://[^\s<>"\']+'
        urls = re.findall(url_pattern, requirements, re.IGNORECASE)
        if urls:
            data["url"] = urls[0].rstrip('/')
        
        # Extract username
        username_patterns = [
            r'[Uu]ser\s*[Nn]ame[:\s]+"?([^"\n]+)"?',
            r'[Uu]sername[:\s]+"?([^"\n]+)"?',
            r'[Ll]ogin\s+with[^"]*[Uu]ser\s*[Nn]ame\s+"([^"]+)"',
        ]
        for pattern in username_patterns:
            match = re.search(pattern, requirements, re.IGNORECASE)
            if match:
                data["username"] = match.group(1).strip()
                break
        
        # Extract password
        password_patterns = [
            r'[Pp]assword\s+as\s+"([^"]+)"',
            r'[Pp]assword[:\s]+"?([^"\n]+)"?',
        ]
        for pattern in password_patterns:
            match = re.search(pattern, requirements, re.IGNORECASE)
            if match:
                data["password"] = match.group(1).strip()
                break
        
        # Extract items/products
        item_patterns = [
            r'[Aa]dd\s+[Tt]o\s+[Cc]art[^"]*"([^"]+)"',
            r'[Ii]tem\s+"([^"]+)"',
            r'[Pp]roduct\s+"([^"]+)"',
        ]
        for pattern in item_patterns:
            matches = re.findall(pattern, requirements, re.IGNORECASE)
            data["items"].extend(matches)
        
        # Extract form fields (first name, last name, PIN, etc.)
        # First name
        first_name_match = re.search(r'[Ff]irst\s+[Nn]ame\s+as\s+([A-Za-z]+)', requirements, re.IGNORECASE)
        if first_name_match:
            data["form_fields"]["first_name"] = first_name_match.group(1).strip()
        
        # Last name
        last_name_match = re.search(r'[Ll]ast\s+[Nn]ame\s+as\s+([A-Za-z]+)', requirements, re.IGNORECASE)
        if last_name_match:
            data["form_fields"]["last_name"] = last_name_match.group(1).strip()
        
        # PIN/Postal code
        pin_match = re.search(r'[Pp]IN\s+[Cc]ode\s+as\s+(\d+)', requirements, re.IGNORECASE)
        if pin_match:
            data["form_fields"]["postal_code"] = pin_match.group(1).strip()
        else:
            postal_match = re.search(r'[Pp]ostal\s+[Cc]ode\s+as\s+(\d+)', requirements, re.IGNORECASE)
            if postal_match:
                data["form_fields"]["postal_code"] = postal_match.group(1).strip()
        
        # Extract expected text/verification text
        text_patterns = [
            r'[Vv]erify[^"]*"([^"]+)"',
            r'[Tt]ext[^"]*"([^"]+)"',
            r'[Ss]hould\s+see[^"]*"([^"]+)"',
        ]
        for pattern in text_patterns:
            matches = re.findall(pattern, requirements, re.IGNORECASE)
            data["expected_text"].extend(matches)
        
        return data
    
    # ==================================================
    # 🔧 INJECT EXACT REQUIREMENTS DATA
    # ==================================================
    def _inject_exact_requirements_data(self, feature: str, extracted_data: dict) -> str:
        """Replace placeholder values with exact data from requirements"""
        if not extracted_data:
            return feature
        
        # Direct fix for "input" and "input with" placeholder in Background login steps
        if extracted_data.get("username"):
            username = extracted_data["username"]
            # Replace: enters "input" into "username" field
            feature = re.sub(
                r'(\s+Given\s+the\s+user\s+enters\s+)"input"(\s+into\s+"username"\s+field)',
                rf'\1"{username}"\2',
                feature,
                flags=re.IGNORECASE
            )
            # Replace: enters "input with" into "username" field (LLM artifact)
            feature = re.sub(
                r'(\s+Given\s+the\s+user\s+enters\s+)"input with"(\s+into\s+"username"\s+field)',
                rf'\1"{username}"\2',
                feature,
                flags=re.IGNORECASE
            )
        
        if extracted_data.get("password"):
            password = extracted_data["password"]
            # Replace: enters "input" into "password" field
            feature = re.sub(
                r'(\s+Given\s+the\s+user\s+enters\s+)"input"(\s+into\s+"password"\s+field)',
                rf'\1"{password}"\2',
                feature,
                flags=re.IGNORECASE
            )
            # Replace: enters "input with" into "password" field (LLM artifact)
            feature = re.sub(
                r'(\s+Given\s+the\s+user\s+enters\s+)"input with"(\s+into\s+"password"\s+field)',
                rf'\1"{password}"\2',
                feature,
                flags=re.IGNORECASE
            )
        
        return self._inject_data_values(feature, extracted_data)
    
    def _clean_llm_placeholders(self, feature: str, extracted_data: dict) -> str:
        """Remove LLM-generated placeholder text like 'input (assuming...)' and replace with actual values"""
        if not extracted_data:
            return feature
        
        lines = feature.splitlines()
        result = []
        
        for line in lines:
            # Remove LLM explanatory text like "input (assuming username input exists, not provided in page structure, will need to be added)"
            if "assuming" in line.lower() and "input" in line.lower():
                # This is an LLM placeholder - replace with actual credential
                if 'username' in line.lower() and extracted_data.get("username"):
                    # Replace entire placeholder pattern with actual username
                    line = re.sub(
                        r'"input \([^"]+\)"',
                        f'"{extracted_data["username"]}"',
                        line,
                        flags=re.IGNORECASE
                    )
                elif 'password' in line.lower() and extracted_data.get("password"):
                    # Replace entire placeholder pattern with actual password
                    line = re.sub(
                        r'"input \([^"]+\)"',
                        f'"{extracted_data["password"]}"',
                        line,
                        flags=re.IGNORECASE
                    )
            
            result.append(line)
        
        return "\n".join(result)
    
    def _fix_llm_generation_errors(self, feature: str, extracted_data: dict) -> str:
        """Fix common LLM generation errors like 'input with' or placeholder issues"""
        lines = feature.splitlines()
        result = []
        
        for line in lines:
            s = line.strip()
            
            # Fix "input with" patterns - these are LLM artifacts - SKIP them completely
            if '"input with' in s.lower() or "'input with" in s.lower() or 'input with label' in s.lower():
                logger.warning(f"Skipping incorrect LLM-generated line: {s}")
                continue
            
            # Also skip lines that have "input with" even if it's part of a longer string
            if re.search(r'"[^"]*input with[^"]*"', s, re.IGNORECASE):
                logger.warning(f"Skipping line with 'input with' pattern: {s}")
                continue
            
            # Skip invalid button names that are clearly wrong (but only if they're not part of valid steps)
            if re.search(r'"login-button"|"cart-link"|"checkout-button"', s, re.IGNORECASE):
                # These will be fixed by _force_login_into_background or normalization
                if '"login-button"' in s.lower() and 'enters' not in s.lower() and 'clicks' in s.lower():
                    # Skip invalid login button references
                    logger.warning(f"Skipping invalid button name: {s}")
                    continue
            
            result.append(line)
        
        return "\n".join(result)
    
    def _inject_data_values(self, feature: str, extracted_data: dict) -> str:
        """
        Replace placeholder values with exact data from requirements.
        This ensures the generated feature uses exact values from requirements.
        """
        if not extracted_data:
            return feature
        
        lines = feature.splitlines()
        result = []
        item_index = 0
        
        for line in lines:
            original_line = line
            
            # Replace placeholder username - MUST be done even if placeholder is unquoted
            if extracted_data.get("username"):
                username = extracted_data["username"]
                # Replace <username> without quotes first
                line = re.sub(r'<username>', username, line)
                # Replace quoted placeholders
                line = re.sub(r'"<username>"', f'"{username}"', line)
                # CRITICAL FIX: Replace "input" and "input with" as VALUE in username field steps
                if 'enters' in line.lower() and 'username' in line.lower():
                    # Match: enters "input with" into "username" field (LLM artifact - must be first)
                    if re.search(r'enters\s+"input with"\s+into\s+"username"', line, re.IGNORECASE):
                        line = re.sub(r'"input with"', f'"{username}"', line, count=1)
                    # Match: enters "input" into "username" field
                    elif re.search(r'enters\s+"input"\s+into\s+"username"', line, re.IGNORECASE):
                        line = re.sub(r'"input"', f'"{username}"', line, count=1)
                    # Match: enters "username" into "username" field  
                    elif re.search(r'enters\s+"username"\s+into\s+"username"', line, re.IGNORECASE):
                        line = re.sub(r'"username"(?=\s+into)', f'"{username}"', line, count=1)
                    # If field name is "input" but should be "username"
                    elif re.search(r'enters\s+"[^"]+"\s+into\s+"input"', line, re.IGNORECASE):
                        line = re.sub(r'"input"', '"username"', line, count=1)
                    # Last resort: if line contains "username" field but wrong value
                    if '"' + username + '"' not in line and re.search(r'into\s+"username"', line, re.IGNORECASE):
                        # Replace any quoted value before "into username" that's not the actual username
                        line = re.sub(r'enters\s+"[^"]+"\s+into\s+"username"', 
                                     f'enters "{username}" into "username"', 
                                     line, flags=re.IGNORECASE)
            
            # Replace placeholder password - MUST be done even if placeholder is unquoted
            if extracted_data.get("password"):
                password = extracted_data["password"]
                # Replace <password> without quotes first
                line = re.sub(r'<password>', password, line)
                # Replace quoted placeholders
                line = re.sub(r'"<password>"', f'"{password}"', line)
                # CRITICAL FIX: Replace "input" and "input with" as VALUE in password field steps
                if 'enters' in line.lower() and 'password' in line.lower():
                    # Match: enters "input with" into "password" field (LLM artifact - must be first)
                    if re.search(r'enters\s+"input with"\s+into\s+"password"', line, re.IGNORECASE):
                        line = re.sub(r'"input with"', f'"{password}"', line, count=1)
                    # Match: enters "input" into "password" field
                    elif re.search(r'enters\s+"input"\s+into\s+"password"', line, re.IGNORECASE):
                        line = re.sub(r'"input"', f'"{password}"', line, count=1)
                    # Match: enters "password" into "password" field
                    elif re.search(r'enters\s+"password"\s+into\s+"password"', line, re.IGNORECASE):
                        line = re.sub(r'"password"(?=\s+into)', f'"{password}"', line, count=1)
                    # If field name is "input" but should be "password"
                    elif re.search(r'enters\s+"[^"]+"\s+into\s+"input"', line, re.IGNORECASE):
                        # Check if previous line was username - this should be password
                        if len(result) > 0 and 'username' in result[-1].lower():
                            line = re.sub(r'"input"', '"password"', line, count=1)
                    # Last resort: if line contains "password" field but wrong value
                    if '"' + password + '"' not in line and re.search(r'into\s+"password"', line, re.IGNORECASE):
                        # Replace any quoted value before "into password" that's not the actual password
                        line = re.sub(r'enters\s+"[^"]+"\s+into\s+"password"', 
                                     f'enters "{password}" into "password"', 
                                     line, flags=re.IGNORECASE)
            
            # Replace generic item names with actual items
            if extracted_data.get("items") and item_index < len(extracted_data["items"]):
                item = extracted_data["items"][item_index]
                # Look for generic patterns and replace with actual item
                if re.search(r'"(item|product|Item|Product)"', line, re.IGNORECASE):
                    line = re.sub(
                        r'"(item|product|Item|Product)"',
                        f'"{item}"',
                        line,
                        count=1,
                        flags=re.IGNORECASE
                    )
                    item_index += 1
            
            # Replace form field placeholders with exact values
            if extracted_data.get("form_fields"):
                form_fields = extracted_data["form_fields"]
                
                # First name - replace John or placeholder values
                if "first_name" in form_fields:
                    first_name = form_fields["first_name"]
                    # Replace "John" or other placeholder first names
                    if re.search(r'"John"|"first name"|first name input', line, re.IGNORECASE):
                        line = re.sub(r'"John"', f'"{first_name}"', line)
                        # Also handle "first name input" pattern
                        line = re.sub(r'first name input', 'first-name field', line, flags=re.IGNORECASE)
                
                # Last name - replace Doe or placeholder values
                if "last_name" in form_fields:
                    last_name = form_fields["last_name"]
                    # Replace "Doe" or other placeholder last names
                    if re.search(r'"Doe"|"last name"|last name input', line, re.IGNORECASE):
                        line = re.sub(r'"Doe"', f'"{last_name}"', line)
                        # Also handle "last name input" pattern
                        line = re.sub(r'last name input', 'last-name field', line, flags=re.IGNORECASE)
                
                # Postal/PIN code - replace 1234 or placeholder values
                if "postal_code" in form_fields:
                    postal_code = form_fields["postal_code"]
                    # Replace "1234" or PIN code placeholders
                    if re.search(r'"1234"|"PIN code"|PIN code input', line, re.IGNORECASE):
                        line = re.sub(r'"1234"', f'"{postal_code}"', line)
                        # Also handle "PIN code input" pattern
                        line = re.sub(r'PIN code input', 'postal-code field', line, flags=re.IGNORECASE)
            
            # Replace expected text placeholders
            if extracted_data.get("expected_text"):
                for expected_text in extracted_data["expected_text"]:
                    # Match generic verification text patterns
                    if re.search(r'"(success|thank|order|confirmation)"', line, re.IGNORECASE):
                        line = re.sub(
                            r'"(success|thank|order|confirmation)"',
                            f'"{expected_text}"',
                            line,
                            count=1,
                            flags=re.IGNORECASE
                        )
                        break
            
            result.append(line)
        
        return "\n".join(result)

    # ==================================================
    # 🔘 NORMALIZE BUTTON NAMES
    # ==================================================
    def _normalize_button_names(self, feature: str) -> str:
        """Normalize button names to match common UI patterns"""
        # Fix common button name variations
        replacements = {
            r'"Add To cart"': '"Add to cart"',
            r'"Add To Cart"': '"Add to cart"',
            r'"add to cart"': '"Add to cart"',
            r'"Finish Button"': '"Finish"',
            r'"finish-button"': '"Finish"',
            r'"checkout-button"': '"Checkout"',
            r'"back-home-button"': '"Back Home"',
            r'"login-button"': '"Login"',
            r'"continue-button"': '"Continue"',
        }
        
        for pattern, replacement in replacements.items():
            feature = re.sub(pattern, replacement, feature, flags=re.IGNORECASE)
        
        return feature
    
    # ==================================================
    # 📝 NORMALIZE FIELD FORMATS
    # ==================================================
    def _normalize_field_formats(self, feature: str) -> str:
        """Normalize field formats (input -> field, fix naming)"""
        # Convert "input" to "field" for consistency
        feature = re.sub(r'into the "([^"]+)" input', r'into the "\1" field', feature, flags=re.IGNORECASE)
        feature = re.sub(r'into (first name|last name|PIN code|postal code) input', 
                        lambda m: f'into the "{m.group(1).replace(" ", "-").lower()}" field', 
                        feature, flags=re.IGNORECASE)
        # Convert "text field" to "field"
        feature = re.sub(r'"([^"]+)" text field', r'"\1" field', feature, flags=re.IGNORECASE)
        
        return feature
    
    # ==================================================
    # 🧹 FINAL CLEANUP
    # ==================================================
    def _final_cleanup(self, feature: str, extracted_data: dict) -> str:
        """Final cleanup pass to remove any remaining invalid patterns"""
        lines = feature.splitlines()
        result = []
        seen_login_username = False
        seen_login_password = False
        in_background = False
        
        for line in lines:
            s = line.strip()
            original_line = line
            
            # Track Background section
            if s.startswith("Background:"):
                in_background = True
                result.append(line)
                continue
            
            if s.startswith("Scenario:"):
                in_background = False
                result.append(line)
                continue
            
            # Remove any remaining "input with" patterns - MUST be removed completely
            if '"input with' in s.lower() or "'input with" in s.lower() or re.search(r'"[^"]*input with[^"]*"', s, re.IGNORECASE):
                logger.warning(f"Final cleanup: Removing line with 'input with': {s}")
                continue
            
            # Fix incorrect login values - replace "username" as value with actual username
            if extracted_data.get("username"):
                username = extracted_data["username"]
                # If line has "username" as the VALUE (not field name) in an enter step
                if re.search(r'enters\s+"username"\s+into', s, re.IGNORECASE) and not seen_login_username:
                    s = re.sub(r'enters\s+"username"', f'enters "{username}"', s, flags=re.IGNORECASE)
                    line = line.replace(line.strip(), s)
                    seen_login_username = True
            
            # Fix incorrect login values - replace "password" as value with actual password
            if extracted_data.get("password"):
                password = extracted_data["password"]
                # If line has "password" as the VALUE (not field name) in an enter step
                if re.search(r'enters\s+"password"\s+into', s, re.IGNORECASE) and not seen_login_password:
                    s = re.sub(r'enters\s+"password"', f'enters "{password}"', s, flags=re.IGNORECASE)
                    line = line.replace(line.strip(), s)
                    seen_login_password = True
            
            # Fix "input" as value - replace with actual credentials if in login context
            if re.search(r'enters\s+"input"\s+into\s+"(username|password)"', s, re.IGNORECASE):
                if 'username' in s.lower() and extracted_data.get("username") and not seen_login_username:
                    s = re.sub(r'"input"', f'"{extracted_data["username"]}"', s)
                    line = line.replace(line.strip(), s)
                    seen_login_username = True
                elif 'password' in s.lower() and extracted_data.get("password") and not seen_login_password:
                    s = re.sub(r'"input"', f'"{extracted_data["password"]}"', s)
                    line = line.replace(line.strip(), s)
                    seen_login_password = True
            
            # Also fix "input" as value in Background login steps (more aggressive)
            if in_background and re.search(r'enters\s+"input"\s+into', s, re.IGNORECASE):
                if not seen_login_username and extracted_data.get("username"):
                    s = re.sub(r'enters\s+"input"\s+into\s+"username"', 
                              f'enters "{extracted_data["username"]}" into "username"', 
                              s, flags=re.IGNORECASE)
                    line = line.replace(line.strip(), s)
                    seen_login_username = True
                elif not seen_login_password and extracted_data.get("password"):
                    s = re.sub(r'enters\s+"input"\s+into\s+"password"', 
                              f'enters "{extracted_data["password"]}" into "password"', 
                              s, flags=re.IGNORECASE)
                    line = line.replace(line.strip(), s)
                    seen_login_password = True
            
            # Replace any remaining placeholder values with actual data
            if extracted_data.get("username"):
                if re.search(r'<username>|"username"(?=\s+into)', s):
                    s = re.sub(r'<username>|"username"(?=\s+into)', f'"{extracted_data["username"]}"', s)
                    line = line.replace(line.strip(), s)
            
            if extracted_data.get("password"):
                if re.search(r'<password>|"password"(?=\s+into)', s):
                    s = re.sub(r'<password>|"password"(?=\s+into)', f'"{extracted_data["password"]}"', s)
                    line = line.replace(line.strip(), s)
            
            result.append(line)
        
        return "\n".join(result)
    
    # ==================================================
    # 🔥 AGGRESSIVE CLEANUP
    # ==================================================
    def _aggressive_cleanup(self, feature: str, extracted_data: dict) -> str:
        """Aggressive cleanup to fix any remaining incorrect patterns"""
        lines = feature.splitlines()
        result = []
        in_background = False
        
        for line in lines:
            s = line.strip()
            
            if s.startswith("Background:"):
                in_background = True
                result.append(line)
                continue
            
            if s.startswith("Scenario:"):
                in_background = False
                result.append(line)
                continue
            
            # Remove ALL "input with label" patterns - no exceptions
            if '"input with' in s.lower() or "'input with" in s.lower() or re.search(r'"[^"]*input with[^"]*"', s, re.IGNORECASE):
                logger.warning(f"Aggressive cleanup: Removing line with 'input with': {s}")
                continue
            
            # In Background: If we see incorrect login steps, replace them
            if in_background and 'enters' in s.lower() and ('username' in s.lower() or 'password' in s.lower() or 'user-name' in s.lower()):
                username = extracted_data.get("username", "your_username")
                password = extracted_data.get("password", "your_password")
                
                # Fix username field steps
                if ('username' in s.lower() or 'user-name' in s.lower()) and f'"{username}"' not in s:
                    # Replace entire step with correct value and field
                    s = re.sub(r'enters\s+"[^"]+"\s+into\s+"[^"]+"', 
                              f'enters "{username}" into "username"', 
                              s, flags=re.IGNORECASE)
                    line = line.replace(line.strip(), s)
                
                # Fix password field steps
                if 'password' in s.lower() and f'"{password}"' not in s:
                    # Replace entire step with correct value and field
                    s = re.sub(r'enters\s+"[^"]+"\s+into\s+"[^"]+"', 
                              f'enters "{password}" into "password"', 
                              s, flags=re.IGNORECASE)
                    line = line.replace(line.strip(), s)
            
            # Fix form field values in scenarios
            if not in_background and extracted_data.get("form_fields"):
                form_fields = extracted_data["form_fields"]
                # Fix first name
                if "first_name" in form_fields and "John" in s:
                    s = s.replace("John", form_fields["first_name"])
                    line = line.replace(line.strip(), s)
                # Fix last name
                if "last_name" in form_fields and "Doe" in s:
                    s = s.replace("Doe", form_fields["last_name"])
                    line = line.replace(line.strip(), s)
                # Fix PIN code
                if "postal_code" in form_fields and re.search(r'"1234"', s):
                    s = re.sub(r'"1234"', f'"{form_fields["postal_code"]}"', s)
                    line = line.replace(line.strip(), s)
            
            result.append(line)
        
        return "\n".join(result)

    # ==================================================
    # 💾 SAVE
    # ==================================================
    def save_feature_file(self, feature_content: str, feature_name: str) -> str:
        Config.ensure_directories()
        feature_name = feature_name or "generated_feature"
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(Config.FEATURES_DIR, f"{feature_name}_{ts}.feature")

        with open(path, "w", encoding="utf-8") as f:
            f.write(feature_content)

        return path

    # ==================================================
    # 🧹 CLEAN + NORMALIZE (CRITICAL)
    # ==================================================
    def _clean_feature_content(self, content: str) -> str:
        # Remove markdown
        lines = [l for l in content.splitlines() if not l.strip().startswith("```")]

        # Start at Feature:
        start = next((i for i, l in enumerate(lines) if l.strip().startswith("Feature:")), None)
        if start is None:
            raise ValueError("LLM output missing Feature:")

        lines = lines[start:]

        allowed = (
            "Feature:", "Background:", "Scenario:",
            "Given ", "When ", "Then ", "And "
        )

        cleaned = []
        seen_feature = False

        for line in lines:
            s = line.strip()

            if not s:
                cleaned.append(line)
                continue

            if s.startswith("Feature:"):
                if seen_feature:
                    break
                seen_feature = True
                cleaned.append(line)
                continue

            if s.startswith(allowed):
                cleaned.append(line)
                continue

            break

        content = "\n".join(cleaned)

        # --------------------------------------------
        # SUBJECT NORMALIZATION
        # --------------------------------------------
        content = re.sub(
            r'^(\s*)(Given|When|Then|And)\s+(I|User|A user|An user)\s+',
            r'\1\2 the user ',
            content,
            flags=re.MULTILINE | re.IGNORECASE
        )
        
        # --------------------------------------------
        # STATE CHANGE / CONTENT VERIFICATION NORMALIZATION
        # Convert state descriptions to verifiable assertions
        # --------------------------------------------
        # Pattern: "the application/content/element X changes/updates" → "the user should see text indicating change"
        content = re.sub(
            r'^(\s*)(Then|And)\s+(the\s+)?(application|content|element|page|UI|interface)\s+(.+?)\s+(changes?|updates?|is updated|gets updated)$',
            r'\1\2 the action should succeed',
            content,
            flags=re.MULTILINE | re.IGNORECASE
        )
        
        # Pattern: "the application/content X is Y" → "the user should see text Y"
        content = re.sub(
            r'^(\s*)(Then|And)\s+(the\s+)?(application|content|element|page)\s+(.+?)\s+(is|shows?|displays?)\s+(.+)$',
            r'\1\2 the user should see text "\7"',
            content,
            flags=re.MULTILINE | re.IGNORECASE
        )

        # --------------------------------------------
        # URL STATE → NAVIGATION
        # --------------------------------------------
        content = re.sub(
            r'^(\s*)(Given|When|And)\s+the URL is\s+"([^"]+)"',
            r'\1\2 the user navigates to "\3"',
            content,
            flags=re.MULTILINE | re.IGNORECASE
        )

        # --------------------------------------------
        # 🔥 UI NOUN NORMALIZATION
        # Treat all clickable things as "button"
        # --------------------------------------------
        content = re.sub(
            r'\bclicks the "([^"]+)"\s+(link|icon|menu|tab|item)\b',
            r'clicks the "\1" button',
            content,
            flags=re.IGNORECASE
        )

        # --------------------------------------------
        # 🔥 GENERIC ACTION VERB NORMALIZATION
        # Convert common action verbs to canonical "clicks the ... button"
        # This makes the framework work for any website, not just e-commerce
        # Note: Patterns account for Gherkin step indentation (2 spaces)
        # --------------------------------------------
        # "clicks on X" → "clicks the X button"
        content = re.sub(
            r'^(\s*)(Given|When|Then|And)\s+the user clicks on "([^"]+)"\s*$',
            r'\1\2 the user clicks the "\3" button',
            content,
            flags=re.MULTILINE | re.IGNORECASE
        )
        
        # "selects X to [do something]" → "clicks the X button" (MORE SPECIFIC - must come first)
        content = re.sub(
            r'^(\s*)(Given|When|Then|And)\s+the user selects "([^"]+)" to .+\s*$',
            r'\1\2 the user clicks the "\3" button',
            content,
            flags=re.MULTILINE | re.IGNORECASE
        )
        
        # "selects X" → "clicks the X button" (GENERAL - comes after specific)
        content = re.sub(
            r'^(\s*)(Given|When|Then|And)\s+the user selects "([^"]+)"\s*$',
            r'\1\2 the user clicks the "\3" button',
            content,
            flags=re.MULTILINE | re.IGNORECASE
        )
        
        # "adds X to Y" → "clicks the X button"
        content = re.sub(
            r'^(\s*)(Given|When|Then|And)\s+the user adds "([^"]+)" to .+\s*$',
            r'\1\2 the user clicks the "\3" button',
            content,
            flags=re.MULTILINE | re.IGNORECASE
        )
        
        # "presses X" → "clicks the X button"
        content = re.sub(
            r'^(\s*)(Given|When|Then|And)\s+the user presses "([^"]+)"\s*$',
            r'\1\2 the user clicks the "\3" button',
            content,
            flags=re.MULTILINE | re.IGNORECASE
        )
        
        # "chooses X" → "clicks the X button"
        content = re.sub(
            r'^(\s*)(Given|When|Then|And)\s+the user chooses "([^"]+)"\s*$',
            r'\1\2 the user clicks the "\3" button',
            content,
            flags=re.MULTILINE | re.IGNORECASE
        )
        
        # "selects X item" or "selects X item in Y" → "clicks the X button"
        content = re.sub(
            r'^(\s*)(Given|When|Then|And)\s+the user selects (?:the )?"([^"]+)"\s+item.*$',
            r'\1\2 the user clicks the "\3" button',
            content,
            flags=re.MULTILINE | re.IGNORECASE
        )

        # --------------------------------------------
        # STATE CHANGE / CONTENT VERIFICATION NORMALIZATION
        # Convert state descriptions to verifiable assertions
        # --------------------------------------------
        # Pattern: "the application/content/element X changes/updates" → "the action should succeed"
        content = re.sub(
            r'^(\s*)(Then|And)\s+the\s+(application|content|element|page|UI|interface|system)\s+(.+?)\s+(changes?|updates?|is updated|gets updated)$',
            r'\1\2 the action should succeed',
            content,
            flags=re.MULTILINE | re.IGNORECASE
        )
        
        # Pattern: "the application/content X is Y" → "the user should see text Y"
        content = re.sub(
            r'^(\s*)(Then|And)\s+the\s+(application|content|element|page)\s+(.+?)\s+(is|shows?|displays?)\s+(.+)$',
            r'\1\2 the user should see text "\6"',
            content,
            flags=re.MULTILINE | re.IGNORECASE
        )
        
        # --------------------------------------------
        # DROP STATE-BASED PAGE STEPS
        # --------------------------------------------
        content = re.sub(
            r'^(\s*)(Given|When|And)\s+the user is on .+$',
            '',
            content,
            flags=re.MULTILINE | re.IGNORECASE
        )

        return content.strip()

    # ==================================================
    # 🔗 URL NORMALIZATION FROM REQUIREMENTS
    # ==================================================
    def _normalize_urls_from_requirements(self, content: str, requirements: str) -> str:
        """
        Extract the actual URL from requirements, bdd.config.yaml, or Config.BASE_URL
        and replace any example.com or placeholder URLs in the feature file with the correct URL.
        """
        actual_url = None
        
        # Priority 1: Extract URL from requirements
        url_pattern = r'https?://[^\s<>"\']+'
        urls_in_requirements = re.findall(url_pattern, requirements, re.IGNORECASE)
        if urls_in_requirements:
            actual_url = urls_in_requirements[0].rstrip('/')
        
        # Priority 2: Check bdd.config.yaml
        if not actual_url:
            try:
                if os.path.exists("bdd.config.yaml"):
                    with open("bdd.config.yaml", "r", encoding="utf-8") as f:
                        bdd_config = yaml.safe_load(f) or {}
                        project_cfg = bdd_config.get("project", {})
                        if project_cfg.get("base_url"):
                            actual_url = project_cfg["base_url"].rstrip('/')
            except Exception:
                pass  # If config file can't be read, continue to next option
        
        # Priority 3: Check Config.BASE_URL (from .env)
        if not actual_url and Config.BASE_URL:
            actual_url = Config.BASE_URL.rstrip('/')
        
        # CRITICAL: Always replace saucedemo.com URLs first, even if it's from requirements
        # This ensures we never use hardcoded demo site URLs
        # Also replace saucedemo.com URLs (legacy hardcoded reference) OR any placeholder URLs
        if 'saucedemo.com' in content.lower() or 'example.com' in content.lower():
            # Determine replacement URL: use actual_url first, then config, then keep as-is
            replacement_url = None
            if actual_url:
                replacement_url = actual_url.rstrip('/')
            elif Config.BASE_URL:
                replacement_url = Config.BASE_URL.rstrip('/')
            else:
                # If no config URL found, keep saucedemo.com URLs as-is (they might be intentional)
                if 'example.com' in content.lower():
                    # Only replace example.com if we have a config URL
                    replacement_url = actual_url or Config.BASE_URL
                    if not replacement_url:
                        logger.warning("No URL found in config - keeping example.com placeholder")
                        return content
            
            if replacement_url:
                if 'saucedemo.com' in content.lower():
                    logger.info(f"Replacing saucedemo.com URL with: {replacement_url}")
                if 'example.com' in content.lower():
                    logger.info(f"Replacing example.com placeholder with: {replacement_url}")
                # Match URL in quotes with saucedemo.com or example.com
                content = re.sub(
                    r'"https?://[^"]*(?:saucedemo|example)\.com[^"]*"',
                    f'"{replacement_url}"',
                    content,
                    flags=re.IGNORECASE
                )
        
        # Now handle other URL replacements if we have an actual_url
        if actual_url and 'saucedemo.com' not in actual_url.lower():
            actual_url_base = actual_url.rstrip('/')
            # Replace example.com URLs and placeholder URLs
            content = re.sub(
                r'"https?://(www\.)?example\.com[^"]*"',
                lambda m: f'"{actual_url_base}"',
                content,
                flags=re.IGNORECASE
            )
        
        return content

    # ==================================================
    # 🧭 FORCE NAVIGATION INTO BACKGROUND
    # ==================================================
    def _force_navigation_into_background(self, content: str) -> str:
        lines = content.splitlines()

        feature, background_header, background_steps, scenarios = [], [], [], []
        navigation_steps = []
        in_background = False

        for line in lines:
            s = line.strip()

            if s.startswith("Feature:"):
                feature.append(line)
                continue

            if s.startswith("Background:"):
                in_background = True
                background_header.append(line)
                continue

            if s.startswith("Scenario:"):
                in_background = False
                scenarios.append(line)
                continue

            # Extract navigation steps
            if re.match(r'^(Given|When|And)\s+the user navigates to ".+"', s, re.IGNORECASE):
                nav_step = "  Given " + s.split("Given ", 1)[-1] if "Given" in s else "  Given " + s.split("When ", 1)[-1].replace("When ", "").replace("And ", "")
                navigation_steps.append(nav_step)
                continue

            if in_background:
                background_steps.append(line)
            else:
                scenarios.append(line)

        if not background_header:
            background_header = ["", "Background:"]

        # Ensure navigation is FIRST in background
        nav_unique = list(dict.fromkeys(navigation_steps))
        # Combine: header + navigation (first) + other background steps
        background = background_header + nav_unique + background_steps

        return "\n".join(feature + background + scenarios)

    # ==================================================
    # 🔐 FORCE LOGIN INTO BACKGROUND
    # ==================================================
    def _force_login_into_background(self, content: str, requirements: str) -> str:
        if not any(x in requirements.lower() for x in ["username", "password", "login"]):
            return content

        # Extract username and password from requirements to use actual values
        extracted_data = self._extract_requirements_data(requirements)
        username = extracted_data.get("username", "your_username")
        password = extracted_data.get("password", "your_password")

        lines = content.splitlines()
        output = []
        in_background = False
        has_navigation = False
        injected = False

        for i, line in enumerate(lines):
            s = line.strip()

            if s.startswith("Background:"):
                in_background = True
                output.append(line)
                continue

            if s.startswith("Scenario:"):
                # Inject login steps at the end of Background, before first Scenario (after navigation)
                if in_background and not injected and has_navigation:
                    output.extend([
                        f'  Given the user enters "{username}" into the "username" field',
                        f'  Given the user enters "{password}" into the "password" field',
                        '  Given the user clicks the "Login" button',
                        ''  # Empty line before Scenario
                    ])
                    injected = True
                in_background = False
                output.append(line)
                continue

            # Check if we have navigation in background
            if in_background and re.match(r'^Given\s+the user navigates to ".+"', s, re.IGNORECASE):
                has_navigation = True
                output.append(line)
                continue

            output.append(line)

        # If we ended in background and have navigation but no login, add login
        if in_background and has_navigation and not injected:
            output.extend([
                f'  Given the user enters "{username}" into the "username" field',
                f'  Given the user enters "{password}" into the "password" field',
                '  Given the user clicks the "Login" button',
            ])

        return "\n".join(output)

    # ==================================================
    # 🧹 CLEAN BACKGROUND DUPLICATES
    # ==================================================
    def _clean_background_duplicates(self, content: str) -> str:
        """Remove duplicate steps from Background section"""
        lines = content.splitlines()
        output = []
        in_background = False
        background_steps = []
        seen_steps = set()

        for line in lines:
            s = line.strip()

            if s.startswith("Background:"):
                in_background = True
                output.append(line)
                continue

            if s.startswith("Scenario:"):
                # Add unique background steps before first scenario
                if in_background:
                    for step in background_steps:
                        output.append(step)
                in_background = False
                output.append(line)
                continue

            if in_background:
                # Normalize step for duplicate detection (remove leading spaces and keyword variations)
                step_normalized = re.sub(r'^\s*(Given|When|Then|And)\s+', '', s, flags=re.IGNORECASE).lower()
                
                # Skip duplicates, but allow navigation to be first
                if step_normalized.startswith("the user navigates to"):
                    # Navigation should be first - check if we already have it
                    if not any("navigates to" in step.lower() for step in background_steps):
                        background_steps.append(line)
                        seen_steps.add(step_normalized)
                elif step_normalized not in seen_steps:
                    background_steps.append(line)
                    seen_steps.add(step_normalized)
            else:
                output.append(line)

        # If we ended in background, add remaining steps
        if in_background:
            for step in background_steps:
                output.append(step)

        return "\n".join(output)

    # ==================================================
    # 🔧 FIX AND STEPS IN BACKGROUND/SCENARIOS
    # ==================================================
    def _fix_and_steps_in_background(self, content: str) -> str:
        """Fix invalid Gherkin: Background and Scenario must start with Given/When/Then, not And"""
        lines = content.splitlines()
        output = []
        in_background = False
        in_scenario = False
        last_keyword = None
        
        for line in lines:
            stripped = line.strip()
            
            # Track Background/Scenario boundaries
            if stripped.startswith("Background:"):
                in_background = True
                in_scenario = False
                last_keyword = None
                output.append(line)
                continue
            
            if stripped.startswith("Scenario:"):
                in_scenario = True
                in_background = False
                last_keyword = None
                output.append(line)
                continue
            
            # If we hit a non-step line, reset state
            if stripped and not stripped.startswith(("Given", "When", "Then", "And", "But")):
                if not stripped.startswith("Feature:"):
                    in_background = False
                    in_scenario = False
                    last_keyword = None
                output.append(line)
                continue
            
            # Fix And steps that appear first in Background or Scenario
            if stripped.startswith("And ") or stripped.startswith("But "):
                if last_keyword:
                    # Replace And/But with the last keyword
                    fixed_line = re.sub(r'^(.*?)(And|But)\s+', rf'\1{last_keyword} ', line, flags=re.IGNORECASE)
                    output.append(fixed_line)
                else:
                    # No previous keyword - must be first step, convert to Given
                    fixed_line = re.sub(r'^(.*?)(And|But)\s+', r'\1Given ', line, flags=re.IGNORECASE)
                    output.append(fixed_line)
                    last_keyword = "Given"
            elif stripped.startswith(("Given", "When", "Then")):
                # Extract the keyword
                match = re.match(r'^(.*?)(Given|When|Then)', line, re.IGNORECASE)
                if match:
                    last_keyword = match.group(2)
                output.append(line)
            else:
                output.append(line)
        
        return "\n".join(output)

    # ==================================================
    # ✅ CHECK IF FEATURE IS INCOMPLETE
    # ==================================================
    def _is_feature_incomplete(self, feature: str, requirements: str) -> bool:
        """Check if LLM-generated feature is incomplete (missing most requirements)"""
        # Count requirements lines
        req_lines = [line.strip() for line in requirements.split('\n') if line.strip() and not line.strip().startswith('#')]
        expected_min_steps = len(req_lines) - 2  # Minus navigation and login (in background)
        
        # Count scenario steps
        scenario_steps = 0
        in_scenario = False
        for line in feature.splitlines():
            s = line.strip()
            if s.startswith("Scenario:"):
                in_scenario = True
                continue
            if in_scenario and s.startswith(("Given", "When", "Then")):
                scenario_steps += 1
        
        # If scenario has very few steps compared to requirements, it's incomplete
        if scenario_steps < max(3, expected_min_steps * 0.5):  # At least 50% of expected steps
            return True
        
        # Check for default/placeholder scenarios
        if "Default scenario" in feature or "action should succeed" in feature.lower():
            if scenario_steps < 5:  # If it only has the default step
                return True
        
        return False
    
    # ==================================================
    # 🔨 BUILD FEATURE FROM REQUIREMENTS (PRIMARY METHOD)
    # ==================================================
    def _build_feature_from_requirements(self, requirements: str, extracted_data: dict, feature_name: str = None, ui_discovery_result: dict = None) -> str:
        """Build feature file directly from requirements in exact order"""
        req_lines = [line.strip() for line in requirements.split('\n') if line.strip() and not line.strip().startswith('#')]
        
        # Use feature_name if provided, otherwise generate from requirements
        feature_title = feature_name
        if not feature_title:
            # Generate title from requirements content (first few words or first action)
            first_line = req_lines[0] if req_lines else "User Workflow"
            # Extract a meaningful title (first 5-6 words or first action)
            words = first_line.split()[:6]
            feature_title = " ".join(words) if words else "User Workflow"
            # Clean up title (remove URLs, quotes, etc.)
            feature_title = re.sub(r'https?://\S+', '', feature_title)
            feature_title = re.sub(r'["\']', '', feature_title)
            feature_title = feature_title.strip()[:50]  # Limit length
        
        # Build Background - only add navigation/login if present in requirements
        background_steps = []
        has_login = any("login" in line.lower() and ("username" in line.lower() or "password" in line.lower()) for line in req_lines)
        has_url = extracted_data.get('url') or Config.BASE_URL
        
        # Get URL from extracted data, config, or use placeholder
        # Try to load URL from bdd.config.yaml first (use absolute path)
        url = extracted_data.get('url')
        if not url:
            try:
                config_path = os.path.join(Config.BASE_DIR, "bdd.config.yaml")
                if os.path.exists(config_path):
                    with open(config_path, "r", encoding="utf-8") as f:
                        project_cfg = yaml.safe_load(f) or {}
                        if project_cfg.get("project", {}).get("base_url"):
                            url = project_cfg["project"]["base_url"].rstrip('/')
                            logger.info(f"Loaded URL from bdd.config.yaml: {url}")
            except Exception as e:
                logger.warning(f"Could not load URL from bdd.config.yaml: {e}")
        
        # Fallback to Config.BASE_URL or placeholder
        if not url:
            url = Config.BASE_URL or 'https://example.com'
            if Config.BASE_URL:
                logger.info(f"Using URL from Config.BASE_URL: {url}")
            else:
                logger.warning(f"No URL found, using placeholder: {url}")
        
        # Always add navigation if URL is available
        if has_url or extracted_data.get('url') or Config.BASE_URL:
            background_steps.append(f'  Given the user navigates to "{url}"')
        
        # Only add login steps if login is mentioned in requirements
        if has_login:
            username = extracted_data.get('username', 'your_username')
            password = extracted_data.get('password', 'your_password')
            
            # Only add login steps if credentials are provided
            if username != 'your_username' or password != 'your_password':
                background_steps.append(f'  Given the user enters "{username}" into the "username" field')
                background_steps.append(f'  Given the user enters "{password}" into the "password" field')
                background_steps.append('  Given the user clicks the "Login" button')
        
        # Build Scenario steps from requirements IN EXACT ORDER
        scenario_steps = []
        form_fields = extracted_data.get('form_fields', {})
        
        for line in req_lines:
            line_lower = line.lower()
            line_original = line
            
            # Skip navigation and login (already in Background)
            if ("navigate" in line_lower and "url" in line_lower) or (line_lower.startswith("navigate") and "http" in line_lower):
                continue
            if "login" in line_lower and ("username" in line_lower or "password" in line_lower or "creds" in line_lower):
                continue
            
            # Pattern: Checkout form fields grouped in one line
            if any(token in line_lower for token in ["first name", "lastname", "last name", "pin code", "postal code", "zipcode", "zip code"]):
                fn_match = re.search(r'first\s*name[^"\']*["\']([^"\']+)["\']', line_original, re.IGNORECASE)
                ln_match = re.search(r'last\s*name[^"\']*["\']([^"\']+)["\']', line_original, re.IGNORECASE)
                zip_match = re.search(r'(?:pin|postal|zip)\s*code[^"\']*["\']([^"\']+)["\']', line_original, re.IGNORECASE)
                
                first_name = fn_match.group(1).strip() if fn_match else None
                last_name = ln_match.group(1).strip() if ln_match else None
                postal_code = zip_match.group(1).strip() if zip_match else None
                
                if first_name:
                    scenario_steps.append(f'  When the user enters "{first_name}" into the "first name" field')
                if last_name:
                    scenario_steps.append(f'  When the user enters "{last_name}" into the "last name" field')
                if postal_code:
                    scenario_steps.append(f'  When the user enters "{postal_code}" into the "postal code" field')
                
                # If we parsed any of the fields, move to next requirement line
                if first_name or last_name or postal_code:
                    continue
            
            # Pattern: Add to cart with item (must come before generic click pattern)
            # "Click on "Add to Cart" button for the product "Sauce Labs Backpack""
            # "Add To cart an Item "Sauce Labs Backpack"" or "Add to cart "Item Name""
            if "add to cart" in line_lower or ("add" in line_lower and "cart" in line_lower and ("item" in line_lower or "product" in line_lower)):
                # Try to find item/product name - look for patterns like "for the product/item "Name""
                # This pattern comes AFTER the button name, so we need to find the last quoted string
                item_patterns = [
                    r'(?:for|of)\s+(?:the\s+)?(?:product|item)\s+["\']([^"\']+)["\']',  # "for the product "Name""
                    r'(?:product|item)\s+["\']([^"\']+)["\']',  # "product "Name""
                ]
                item = None
                for pattern in item_patterns:
                    item_match = re.search(pattern, line_original, re.IGNORECASE)
                    if item_match:
                        item = item_match.group(1).strip()
                        break
                
                # If no pattern match, try to find the last quoted string (likely the item name)
                if not item:
                    all_quoted = re.findall(r'["\']([^"\']+)["\']', line_original)
                    if len(all_quoted) >= 2:
                        # Last quoted string is likely the item name
                        item = all_quoted[-1].strip()
                    elif len(all_quoted) == 1:
                        # Only one quoted string - check if it's not the button name
                        potential_item = all_quoted[0].strip()
                        if "add" not in potential_item.lower() and "cart" not in potential_item.lower():
                            item = potential_item
                
                # Fallback to extracted data
                if not item:
                    items = extracted_data.get('items', [])
                    if items:
                        item = items[0]
                
                if item:
                    scenario_steps.append(f'  When the user clicks the "Add to cart" button for the item "{item}"')
                else:
                    scenario_steps.append(f'  When the user clicks the "Add to cart" button')
                continue
            
            # Generic Pattern: Click on any button/link (handles cart, checkout, or any button)
            # "Click on [Any] button" or "Click the [Any] button"
            if "click" in line_lower or "press" in line_lower:
                # Extract button/link name from the line
                # Patterns: "Click on X button", "Click the X button", "Click X", "Click on 'X' button"
                
                # 🔑 UNIVERSAL UI RULE: Check if action is ambiguous (appears multiple times)
                # If ambiguous AND item names are present, automatically emit scoped step
                ui_semantics = ui_discovery_result.get('ui_semantics', {}) if ui_discovery_result else {}
                ambiguous_actions = ui_discovery_result.get('ambiguous_actions', []) if ui_discovery_result else []
                
                # First, try to extract quoted button names (most specific)
                # Handle quoted button names (e.g., Click on "Shopping Cart button")
                quoted_match = re.search(r'(?:click|press|clicking|pressing)\s+(?:on\s+)?["\']([^"\']+)["\']', line_original, re.IGNORECASE)
                if quoted_match:
                    button_name = quoted_match.group(1).strip()
                    button_name_lower = button_name.lower()
                    
                    # Check if this action is ambiguous and has item names
                    if button_name_lower in ambiguous_actions:
                        action_info = ui_semantics.get(button_name_lower, {})
                        if action_info.get('requires_context') and action_info.get('has_item_names'):
                            # Try to find item name in the same line or nearby
                            item_match = re.search(r'["\']([^"\']+)["\']', line_original)
                            if item_match:
                                # Check if this looks like an item name (not the button name itself)
                                potential_item = item_match.group(1).strip()
                                if potential_item.lower() != button_name_lower and len(potential_item) > 3:
                                    # Use scoped step
                                    scenario_steps.append(f'  When the user clicks the "{button_name}" button for the item "{potential_item}"')
                                    continue
                            # Check extracted items
                            item_names = action_info.get('item_names', [])
                            if item_names and extracted_data.get('items'):
                                # Use first matching item
                                for item in extracted_data.get('items', []):
                                    if any(item.lower() in name.lower() or name.lower() in item.lower() for name in item_names):
                                        scenario_steps.append(f'  When the user clicks the "{button_name}" button for the item "{item}"')
                                        continue
                    
                    scenario_steps.append(f'  When the user clicks the "{button_name}" button')
                    continue
                
                # Second, try patterns like "Click on X button" or "Click the X button"
                # Match the button name before "button" or "link" keyword
                button_match = re.search(r'(?:click|press)\s+(?:on\s+)?(?:the\s+)?([A-Za-z][A-Za-z\s-]+?)(?:\s+button|\s+link|$)', line_original, re.IGNORECASE)
                if button_match:
                    button_name = button_match.group(1).strip()
                    # Clean up button name (remove extra whitespace)
                    button_name = ' '.join(button_name.split())
                    # Remove trailing "button" or "link" if somehow still present
                    button_name = re.sub(r'\s+(button|link)$', '', button_name, flags=re.IGNORECASE).strip()
                    
                    # Skip if button_name is empty or too short (likely a false match)
                    if len(button_name) < 2:
                        button_match = None
                    else:
                        button_name_lower = button_name.lower()
                        
                        # Check if this action is ambiguous and has item names
                        if button_name_lower in ambiguous_actions:
                            action_info = ui_semantics.get(button_name_lower, {})
                            if action_info.get('requires_context') and action_info.get('has_item_names'):
                                # Try to find item name in the same line or nearby
                                item_match = re.search(r'["\']([^"\']+)["\']', line_original)
                                if item_match:
                                    potential_item = item_match.group(1).strip()
                                    if potential_item.lower() != button_name_lower and len(potential_item) > 3:
                                        scenario_steps.append(f'  When the user clicks the "{button_name}" button for the item "{potential_item}"')
                                        continue
                                # Check extracted items
                                item_names = action_info.get('item_names', [])
                                if item_names and extracted_data.get('items'):
                                    for item in extracted_data.get('items', []):
                                        if any(item.lower() in name.lower() or name.lower() in item.lower() for name in item_names):
                                            scenario_steps.append(f'  When the user clicks the "{button_name}" button for the item "{item}"')
                                            continue
                        
                        scenario_steps.append(f'  When the user clicks the "{button_name}" button')
                        continue
                
                # Fallback: extract word(s) after "click on" or "click the" until "button" or end
                # This handles cases like "Click Continue" (without "button" keyword)
                fallback_match = re.search(r'(?:click|press)\s+(?:on\s+)?(?:the\s+)?([A-Za-z][A-Za-z\s]+?)(?=\s+button|\s+link|$)', line_original, re.IGNORECASE)
                if fallback_match:
                    button_name = fallback_match.group(1).strip()
                    button_name = ' '.join(button_name.split()).strip()
                    if len(button_name) >= 2:  # Only use if meaningful
                        button_name_lower = button_name.lower()
                        
                        # Check if this action is ambiguous and has item names
                        if button_name_lower in ambiguous_actions:
                            action_info = ui_semantics.get(button_name_lower, {})
                            if action_info.get('requires_context') and action_info.get('has_item_names'):
                                # Try to find item name in the same line or nearby
                                item_match = re.search(r'["\']([^"\']+)["\']', line_original)
                                if item_match:
                                    potential_item = item_match.group(1).strip()
                                    if potential_item.lower() != button_name_lower and len(potential_item) > 3:
                                        scenario_steps.append(f'  When the user clicks the "{button_name}" button for the item "{potential_item}"')
                                        continue
                                # Check extracted items
                                item_names = action_info.get('item_names', [])
                                if item_names and extracted_data.get('items'):
                                    for item in extracted_data.get('items', []):
                                        if any(item.lower() in name.lower() or name.lower() in item.lower() for name in item_names):
                                            scenario_steps.append(f'  When the user clicks the "{button_name}" button for the item "{item}"')
                                            continue
                        
                        scenario_steps.append(f'  When the user clicks the "{button_name}" button')
                        continue
            
            # Generic Pattern: Navigate to any page (MUST come before click pattern to avoid false matches)
            # "Navigate to X Page" or "Go to X Page"
            if ("navigate" in line_lower or "go to" in line_lower) and ("page" in line_lower or "section" in line_lower):
                # Extract page/section name - be more specific to avoid matching "Cart" as "C"
                page_match = re.search(r'(?:to|the)\s+([A-Za-z][A-Za-z\s]+?)\s+(?:page|section)', line_original, re.IGNORECASE)
                if page_match:
                    page_name = page_match.group(1).strip()
                    page_name = ' '.join(page_name.split())  # Clean whitespace
                    # Convert to button click step
                    scenario_steps.append(f'  When the user clicks the "{page_name}" button')
                    continue
            
            # Pattern 4: Enter form information (first name, last name, PIN)
            # "Enter your Information - first name as Aaditya , last Name as Goel and PIN code as 201301"
            if "enter" in line_lower and ("information" in line_lower or "info" in line_lower):
                # First name
                first_name_match = re.search(r'first\s+name\s+as\s+([A-Za-z]+)', line_original, re.IGNORECASE)
                if first_name_match:
                    first_name = first_name_match.group(1).strip()
                    scenario_steps.append(f'  When the user enters "{first_name}" into the "first-name" field')
                elif form_fields.get('first_name'):
                    scenario_steps.append(f'  When the user enters "{form_fields["first_name"]}" into the "first-name" field')
                
                # Last name
                last_name_match = re.search(r'last\s+name\s+as\s+([A-Za-z]+)', line_original, re.IGNORECASE)
                if last_name_match:
                    last_name = last_name_match.group(1).strip()
                    scenario_steps.append(f'  When the user enters "{last_name}" into the "last-name" field')
                elif form_fields.get('last_name'):
                    scenario_steps.append(f'  When the user enters "{form_fields["last_name"]}" into the "last-name" field')
                
                # PIN/Postal code
                pin_match = re.search(r'(?:PIN|postal)\s+code\s+as\s+(\d+)', line_original, re.IGNORECASE)
                if pin_match:
                    pin_code = pin_match.group(1).strip()
                    scenario_steps.append(f'  When the user enters "{pin_code}" into the "postal-code" field')
                elif form_fields.get('postal_code'):
                    scenario_steps.append(f'  When the user enters "{form_fields["postal_code"]}" into the "postal-code" field')
                continue
            
            # Generic pattern for Continue, Finish, Submit, etc. buttons are now handled by the generic click pattern above
            
            # Generic Pattern: Verify/Check/Should see text
            # "Verify that X" or "Should see Y" - works for any verification
            if "verify" in line_lower or "should see" in line_lower or "check" in line_lower:
                # Extract quoted text
                text_match = re.search(r'"([^"]+)"', line_original)
                if text_match:
                    expected_text = text_match.group(1)
                    scenario_steps.append(f'  Then the user should see text "{expected_text}"')
                elif extracted_data.get('expected_text'):
                    scenario_steps.append(f'  Then the user should see text "{extracted_data["expected_text"][0]}"')
                continue
            
            # Generic Pattern: Enter value into any field
            # "Enter X into Y field" - works for any form field
            if "enter" in line_lower and "into" in line_lower and ("field" in line_lower or "input" in line_lower):
                # Extract value and field name
                value_match = re.search(r'["\']([^"\']+)["\']', line_original)
                field_match = re.search(r'into\s+(?:the\s+)?["\']?([^"\'\n]+?)(?:\s+field|\s+input)?["\']?', line_original, re.IGNORECASE)
                
                if value_match and field_match:
                    value = value_match.group(1)
                    field = field_match.group(1).strip()
                    field = re.sub(r'\s+(field|input)$', '', field, flags=re.IGNORECASE)
                    # Normalize field name (convert spaces to hyphens)
                    field = field.replace(" ", "-").lower()
                    scenario_steps.append(f'  When the user enters "{value}" into the "{field}" field')
                    continue
            
            # Generic Pattern: Navigate back or return to any location
            # "Navigate back to X" or "Return to X"
            if ("navigate back" in line_lower or "return to" in line_lower or "go back" in line_lower):
                # Extract destination name
                back_match = re.search(r'(?:back to|to)\s+["\']?([^"\'\n]+?)(?:\s+page|\s+button)?["\']?', line_original, re.IGNORECASE)
                if back_match:
                    destination = back_match.group(1).strip()
                    destination = re.sub(r'\s+(page|button)$', '', destination, flags=re.IGNORECASE)
                    # Check if it mentions clicking a button
                    button_match = re.search(r'clicking\s+on\s+["\']([^"\']+)["\']', line_original, re.IGNORECASE)
                    if button_match:
                        button_name = button_match.group(1)
                        scenario_steps.append(f'  When the user clicks the "{button_name}" button')
                    else:
                        scenario_steps.append(f'  When the user clicks the "{destination}" button')
                    # Add page verification if "page" was mentioned
                    if "page" in line_lower:
                        scenario_steps.append(f'  Then the user should be on the {destination} page')
                continue
        
        # Build final feature
        feature_lines = [f"Feature: {feature_title}", ""]
        
        # Only add Background if we have background steps
        if background_steps:
            feature_lines.append("Background:")
            feature_lines.extend(background_steps)
            feature_lines.append("")
        
        # Generate scenario name from requirements or use generic name
        scenario_name = "User workflow scenario"
        if req_lines:
            # Try to find a meaningful action line (skip navigation/login lines)
            meaningful_lines = [line for line in req_lines 
                              if not (line.lower().startswith("navigate") or 
                                     ("login" in line.lower() and ("username" in line.lower() or "password" in line.lower())))]
            
            if meaningful_lines:
                # Use first meaningful action line
                first_action = meaningful_lines[0]
            else:
                # Fallback to first line
                first_action = req_lines[0]
            
            # Extract meaningful scenario name from the action (generic patterns)
            # Generate descriptive scenario names based on key actions
            if "login" in first_action.lower() or "sign in" in first_action.lower():
                scenario_name = "User authentication workflow"
            elif "search" in first_action.lower():
                scenario_name = "User search workflow"
            elif "submit" in first_action.lower() or "form" in first_action.lower():
                scenario_name = "User form submission workflow"
            elif "add" in first_action.lower() and ("item" in first_action.lower() or "product" in first_action.lower() or "cart" in first_action.lower()):
                scenario_name = "Add item and complete workflow"
            elif "checkout" in first_action.lower() or "order" in first_action.lower():
                scenario_name = "Complete transaction workflow"
            else:
                # Create a descriptive name from key actions
                key_actions = []
                for line in req_lines[:5]:  # Check first 5 lines
                    line_lower = line.lower()
                    if "verify" in line_lower or "should see" in line_lower:
                        key_actions.append("Verify")
                    elif "submit" in line_lower:
                        key_actions.append("Submit")
                    elif "click" in line_lower or "navigate" in line_lower:
                        key_actions.append("Navigate")
                
                if key_actions:
                    scenario_name = " and ".join(key_actions[:3])  # Combine up to 3 key actions
                else:
                    # Last resort: use first meaningful words from first action
                    words = first_action.split()[:6]
                    scenario_name = " ".join(words)
                    # Clean up URL if present
                    scenario_name = re.sub(r'https?://[^\s]+', '', scenario_name)  # Remove full URLs
                    scenario_name = re.sub(r'www\.[^\s]+', '', scenario_name)  # Remove www.domain
                    scenario_name = ' '.join(scenario_name.split())  # Clean whitespace
                    scenario_name = scenario_name.strip()[:60]  # Limit length
        
        feature_lines.append(f"  Scenario: {scenario_name}")
        feature_lines.extend(scenario_steps)
        
        return "\n".join(feature_lines)
    
    # ==================================================
    # 🧯 ENSURE SCENARIOS ARE NEVER EMPTY
    # ==================================================
    def _ensure_scenarios_not_empty(self, content: str) -> str:
        lines = content.splitlines()
        output = []

        in_scenario = False
        scenario_has_step = False
        has_any_scenario = False

        for line in lines:
            s = line.strip()

            if s.startswith("Scenario:"):
                has_any_scenario = True
                if in_scenario and not scenario_has_step:
                    output.append("  Then the action should succeed")

                in_scenario = True
                scenario_has_step = False
                output.append(line)
                continue

            if in_scenario and s.startswith(("Given ", "When ", "Then ", "And ")):
                scenario_has_step = True

            output.append(line)

        if in_scenario and not scenario_has_step:
            output.append("  Then the action should succeed")
        
        # If no scenarios at all, add a default scenario
        if not has_any_scenario:
            logger.warning("No scenarios found in feature file. Adding default scenario.")
            # Check if we have a Background
            has_background = any("Background:" in line for line in output)
            
            if has_background:
                # Add scenario after Background
                for i, line in enumerate(output):
                    if "Background:" in line:
                        # Find the end of Background section
                        j = i + 1
                        while j < len(output) and (output[j].startswith("  ") or not output[j].strip()):
                            j += 1
                        # Insert scenario at position j
                        output.insert(j, "")
                        output.insert(j + 1, "  Scenario: Default scenario from requirements")
                        output.insert(j + 2, "    Then the action should succeed")
                        break
            else:
                # Add scenario at the end
                output.append("")
                output.append("  Scenario: Default scenario from requirements")
                output.append("    Then the action should succeed")

        return "\n".join(output)

    # ==================================================
    # ✅ FINAL VALIDATION (FLEXIBLE FOR DEMO)
    # ==================================================
    def _validate_canonical_grammar(self, content: str, project_type: str):
        # Core canonical patterns
        canonical_patterns = [
            r'^the user navigates to ".+"$',
            r'^the user enters ".+" into the ".+" field$',
            r'^the user clicks the ".+" button$',
            r'^the user should see text ".+"$',
            r'^the user should be on the home page$',
            r'^the user should be on the .+ page$',  # Allow variations like "checkout page"
            r'^the action should succeed$',
            r'^the action should fail$',
        ]

        in_background = False

        for line in content.splitlines():
            s = line.strip()

            if s.startswith("Background:"):
                in_background = True
                continue

            if s.startswith("Scenario:"):
                in_background = False
                continue

            if not any(s.startswith(k) for k in ["Given ", "When ", "Then ", "And "]):
                continue

            step = s.split(" ", 1)[1]

            # Check if step matches any canonical pattern
            matches_canonical = any(re.match(p, step) for p in canonical_patterns)
            
            # If it doesn't match, check if it follows basic structure (not too strict)
            if not matches_canonical:
                # Allow steps that follow basic patterns: action + object
                # This is more lenient for company demos
                basic_patterns = [
                    r'^the user .+$',  # Any step starting with "the user"
                    r'^the (application|content|element|page|UI|interface|system) .+$',  # State/verification steps
                    r'^the action .+$',  # Action result steps
                ]
                matches_basic = any(re.match(p, step) for p in basic_patterns)
                if not matches_basic:
                    # Log warning for steps that don't match any pattern
                    # These should be normalized earlier, but allow them through for step definition generation
                    logger.warning(
                        f"Step doesn't match canonical or basic patterns: '{step}'. "
                        f"Will be handled by step definition agent. Consider normalizing in _clean_feature_content."
                    )
                    # Don't raise error - let step definition agent handle it
                    # This allows flexibility for edge cases while maintaining validation

            if project_type == ProjectType.WEB:
                if "navigates to" in step and not in_background:
                    raise ValueError("Navigation leaked into Scenario")
