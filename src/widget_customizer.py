"""
Widget Customizer Module

Handles website theme extraction, widget code generation with Gemini,
and user-driven widget customization with prompt injection protection.

Architecture:
- PromptGuard: Sanitizes user input to prevent prompt injection
- ThemeExtractor: Extracts color themes from website URLs
- WidgetConfig: Pydantic model for widget configuration
- WidgetConfigGenerator: Uses Gemini to generate/modify widget configs
- WidgetCodeRenderer: Generates self-contained embeddable widget code
"""

import re
import json
import logging
from collections import Counter
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from typing import Optional, Dict, List, Tuple


# ============================================================
# SVG Icons for Widget Button
# ============================================================

WIDGET_ICONS = {
    'chat': '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm0 14H6l-2 2V4h16v12z"/></svg>',
    'robot': '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M17.753 14a2.25 2.25 0 1 1 0 4.5 2.25 2.25 0 0 1 0-4.5zm-11.506 0a2.25 2.25 0 1 1 0 4.5 2.25 2.25 0 0 1 0-4.5zM12 1.5a2 2 0 0 1 2 2v.537A7.003 7.003 0 0 1 19 11v1h1.5a1 1 0 0 1 1 1v4a1 1 0 0 1-1 1H19v2a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2v-2H3.5a1 1 0 0 1-1-1v-4a1 1 0 0 1 1-1H5v-1a7.003 7.003 0 0 1 5-6.963V3.5a2 2 0 0 1 2-2z"/></svg>',
    'help': '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M11 18h2v-2h-2v2zm1-16C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8zm0-14c-2.21 0-4 1.79-4 4h2c0-1.1.9-2 2-2s2 .9 2 2c0 2-3 1.75-3 5h2c0-2.25 3-2.5 3-5 0-2.21-1.79-4-4-4z"/></svg>',
    'headset': '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M12 1c-4.97 0-9 4.03-9 9v7c0 1.66 1.34 3 3 3h3v-8H5v-2c0-3.87 3.13-7 7-7s7 3.13 7 7v2h-4v8h3c1.66 0 3-1.34 3-3v-7c0-4.97-4.03-9-9-9z"/></svg>',
    'sparkle': '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M12 2L9.19 8.63 2 9.24l5.46 4.73L5.82 21 12 17.27 18.18 21l-1.64-7.03L22 9.24l-7.19-.61z"/></svg>',
}


# ============================================================
# Prompt Injection Guard
# ============================================================

class PromptGuard:
    """Protects against prompt injection in user inputs."""

    MAX_INPUT_LENGTH = 500

    INJECTION_PATTERNS = [
        r'ignore\s+(previous|above|all)\s+(instructions?|prompt|context)',
        r'(system|assistant|user)\s*:',
        r'forget\s+(your|all|previous)\s+instructions',
        r'new\s+instructions?\s*:',
        r'you\s+are\s+now',
        r'pretend\s+(to\s+be|you\s+are)',
        r'<script',
        r'javascript\s*:',
        r'eval\s*\(',
        r'on(click|error|load|mouseover)\s*=',
        r'document\.(cookie|write|location)',
        r'window\.(location|open)',
        r'fetch\s*\(',
        r'XMLHttpRequest',
        r'import\s*\(',
    ]

    @classmethod
    def sanitize(cls, user_input: str) -> Tuple[str, bool]:
        """
        Sanitize user input for safe use in Gemini prompts.
        Returns (sanitized_text, is_safe).
        """
        if not user_input or not user_input.strip():
            return "", False

        sanitized = user_input.strip()[:cls.MAX_INPUT_LENGTH]

        for pattern in cls.INJECTION_PATTERNS:
            if re.search(pattern, sanitized, re.IGNORECASE):
                logging.warning(f"Prompt injection attempt detected: pattern='{pattern}'")
                return "", False

        # Strip HTML tags
        sanitized = re.sub(r'<[^>]+>', '', sanitized)
        # Strip code blocks
        sanitized = re.sub(r'```[\s\S]*?```', '', sanitized)
        sanitized = re.sub(r'`[^`]*`', '', sanitized)

        return sanitized.strip(), True

    @classmethod
    def validate_output(cls, code: str) -> Tuple[str, bool]:
        """Validate that generated widget code is safe."""
        if not code:
            return "", False

        lowered = code.lower()
        if 'eval(' in lowered:
            return "", False
        if 'document.cookie' in lowered:
            return "", False
        if 'window.location =' in lowered or 'window.location=' in lowered:
            return "", False

        return code, True


# ============================================================
# Widget Configuration Model
# ============================================================

class WidgetConfig(BaseModel):
    """Configuration for a customized chat widget."""
    # Colors
    primary_color: str = "#667eea"
    secondary_color: str = "#764ba2"
    bg_color: str = "#1a1b2e"
    surface_color: str = "#232442"
    text_color: str = "#e2e4f0"
    text_secondary_color: str = "#9498b8"
    border_color: str = "#2e3055"
    user_msg_text_color: str = "#ffffff"
    bot_msg_bg_color: str = "#232442"
    bot_msg_text_color: str = "#e2e4f0"
    input_bg_color: str = "#232442"
    input_text_color: str = "#e2e4f0"
    input_placeholder_color: str = "#6b70a0"

    # Widget button
    button_text: str = "Virtual Assistant"
    button_shape: str = "pill"  # pill, circle, rounded-square
    button_icon: str = "chat"  # chat, robot, help, headset, sparkle

    # Chat window
    header_title: str = "Chat Assistant"
    input_placeholder: str = "Ask a question..."

    # Meta
    is_dark: bool = True


# ============================================================
# Theme Extractor
# ============================================================

class ThemeExtractor:
    """Extracts color themes from website URLs."""

    HEX_COLOR = re.compile(r'#(?:[0-9a-fA-F]{3}){1,2}\b')
    RGB_COLOR = re.compile(r'rgba?\(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*(?:,\s*[\d.]+\s*)?\)')

    def extract_theme(self, url: str) -> Dict:
        """Fetch a URL and extract its color theme."""
        try:
            if not url.startswith('http'):
                url = f'https://{url}'

            headers = {'User-Agent': 'Mozilla/5.0 (compatible; ChatBotWidget/1.0)'}
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')
            colors = []

            # Inline styles
            for el in soup.find_all(style=True):
                colors.extend(self._extract_colors_from_css(el.get('style', '')))

            # <style> tags
            for style_tag in soup.find_all('style'):
                if style_tag.string:
                    colors.extend(self._extract_colors_from_css(style_tag.string))

            # Linked stylesheets (first 3)
            for link in soup.find_all('link', rel='stylesheet')[:3]:
                href = link.get('href', '')
                if href:
                    css_url = self._resolve_url(url, href)
                    try:
                        css_resp = requests.get(css_url, headers=headers, timeout=10)
                        if css_resp.ok:
                            colors.extend(self._extract_colors_from_css(css_resp.text))
                    except Exception:
                        pass

            # Meta theme-color
            meta_theme = soup.find('meta', attrs={'name': 'theme-color'})
            if meta_theme and meta_theme.get('content'):
                colors.append(('accent', meta_theme['content']))

            return self._analyze_colors(colors, soup)

        except Exception as e:
            logging.error(f"Error extracting theme from {url}: {e}")
            return self._default_theme()

    def _extract_colors_from_css(self, css_text: str) -> List[Tuple[str, str]]:
        """Extract color values from CSS text with their property type."""
        colors = []
        prop_pattern = re.compile(
            r'(background(?:-color)?|color|border(?:-color)?|accent-color)\s*:\s*([^;]+)',
            re.IGNORECASE
        )

        for match in prop_pattern.finditer(css_text):
            prop = match.group(1).lower()
            value = match.group(2).strip()

            color_type = 'background' if 'background' in prop else ('text' if prop == 'color' else 'accent')

            hex_match = self.HEX_COLOR.search(value)
            rgb_match = self.RGB_COLOR.search(value)

            if hex_match:
                colors.append((color_type, hex_match.group()))
            elif rgb_match:
                colors.append((color_type, rgb_match.group()))

        return colors

    def _resolve_url(self, base_url: str, href: str) -> str:
        """Resolve a potentially relative URL to absolute."""
        if href.startswith('http'):
            return href
        if href.startswith('//'):
            return 'https:' + href
        if href.startswith('/'):
            parsed = urlparse(base_url)
            return f"{parsed.scheme}://{parsed.netloc}{href}"
        return base_url.rstrip('/') + '/' + href

    def _analyze_colors(self, colors: List[Tuple[str, str]], soup) -> Dict:
        """Analyze extracted colors to build a theme palette."""
        bg_colors = [c[1] for c in colors if c[0] == 'background']
        text_colors = [c[1] for c in colors if c[0] == 'text']
        accent_colors = [c[1] for c in colors if c[0] == 'accent']

        theme = {
            'background_color': self._most_common(bg_colors) or '#ffffff',
            'text_color': self._most_common(text_colors) or '#333333',
            'accent_color': self._most_common(accent_colors) or '#667eea',
            'primary_color': None,
            'secondary_color': None,
        }

        unique_accents = list(dict.fromkeys(accent_colors))
        theme['primary_color'] = unique_accents[0] if unique_accents else theme['accent_color']
        theme['secondary_color'] = (
            unique_accents[1] if len(unique_accents) > 1
            else self._darken(theme['primary_color'])
        )

        # Determine dark/light mode
        body = soup.find('body')
        if body and ('dark' in str(body.get('class', [])).lower()
                      or 'dark' in body.get('style', '').lower()):
            theme['is_dark'] = True
        else:
            theme['is_dark'] = self._is_dark_color(theme['background_color'])

        return theme

    def _most_common(self, items: list) -> Optional[str]:
        if not items:
            return None
        return Counter(items).most_common(1)[0][0]

    def _hex_to_rgb(self, hex_color: str) -> Tuple[int, int, int]:
        hex_color = hex_color.lstrip('#')
        if len(hex_color) == 3:
            hex_color = ''.join(c * 2 for c in hex_color)
        return (int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16))

    def _is_dark_color(self, color: str) -> bool:
        try:
            if color.startswith('#'):
                r, g, b = self._hex_to_rgb(color)
            elif color.startswith('rgb'):
                nums = re.findall(r'\d+', color)
                r, g, b = int(nums[0]), int(nums[1]), int(nums[2])
            else:
                return False
            return (0.299 * r + 0.587 * g + 0.114 * b) / 255 < 0.5
        except Exception:
            return False

    def _darken(self, color: str, factor: float = 0.2) -> str:
        try:
            r, g, b = self._hex_to_rgb(color)
            r = max(0, int(r * (1 - factor)))
            g = max(0, int(g * (1 - factor)))
            b = max(0, int(b * (1 - factor)))
            return f"#{r:02x}{g:02x}{b:02x}"
        except Exception:
            return color

    def _default_theme(self) -> Dict:
        return {
            'background_color': '#ffffff',
            'text_color': '#333333',
            'accent_color': '#667eea',
            'primary_color': '#667eea',
            'secondary_color': '#764ba2',
            'is_dark': False,
        }


# ============================================================
# Widget Config Generator (Gemini-based)
# ============================================================

THEME_GENERATION_PROMPT = ChatPromptTemplate.from_template("""You are a UI theme expert. Generate a chat widget color configuration that harmonizes with the given website color palette.

Website colors extracted:
- Background: {background_color}
- Text: {text_color}
- Accent/Brand: {accent_color}
- Primary: {primary_color}
- Secondary: {secondary_color}
- Is Dark Theme: {is_dark}

Generate a harmonious widget theme. Use the website's accent/brand colors as the primary widget colors. Ensure good readability and contrast. If the website is dark-themed, make the widget dark too.

Return ONLY a valid JSON object with exactly these fields (no extra text):
{{
  "primary_color": "#hex",
  "secondary_color": "#hex",
  "bg_color": "#hex",
  "surface_color": "#hex",
  "text_color": "#hex",
  "text_secondary_color": "#hex",
  "border_color": "#hex",
  "user_msg_text_color": "#hex",
  "bot_msg_bg_color": "#hex",
  "bot_msg_text_color": "#hex",
  "input_bg_color": "#hex",
  "input_text_color": "#hex",
  "input_placeholder_color": "#hex",
  "button_text": "Virtual Assistant",
  "button_shape": "pill",
  "button_icon": "chat",
  "header_title": "Chat Assistant",
  "input_placeholder": "Ask a question...",
  "is_dark": true/false
}}

All color values MUST be 6-digit hex codes (e.g. #667eea).
button_shape MUST be one of: "pill", "circle", "rounded-square"
button_icon MUST be one of: "chat", "robot", "help", "headset", "sparkle"
""")

CUSTOMIZATION_PROMPT = ChatPromptTemplate.from_template("""You are a chat widget customization expert. Modify the widget configuration based on the user's request.

Current widget configuration:
{current_config}

User's customization request: {instruction}

RULES:
1. Only modify visual properties (colors, text, shape, icon)
2. button_shape MUST be one of: "pill", "circle", "rounded-square"
3. button_icon MUST be one of: "chat", "robot", "help", "headset", "sparkle"
4. All color values MUST be valid 6-digit hex codes (e.g. #667eea)
5. Keep text values under 30 characters
6. Do NOT add any new fields
7. Maintain good contrast and readability

Return ONLY the modified JSON configuration (no extra text, no markdown):
""")


class WidgetConfigGenerator:
    """Uses Gemini to generate and customize widget configurations."""

    GEMINI_MODEL = 'gemini-2.0-flash'

    def __init__(self):
        self.llm = ChatGoogleGenerativeAI(
            model=self.GEMINI_MODEL,
            temperature=0.3,
            max_retries=2,
        )

    def generate_theme_config(self, theme_colors: Dict) -> WidgetConfig:
        """Generate a WidgetConfig that matches the website's theme."""
        try:
            prompt_text = THEME_GENERATION_PROMPT.format(
                background_color=theme_colors.get('background_color', '#ffffff'),
                text_color=theme_colors.get('text_color', '#333333'),
                accent_color=theme_colors.get('accent_color', '#667eea'),
                primary_color=theme_colors.get('primary_color', '#667eea'),
                secondary_color=theme_colors.get('secondary_color', '#764ba2'),
                is_dark=theme_colors.get('is_dark', False),
            )
            response = self.llm.invoke(prompt_text)
            return self._parse_config_response(response.content)
        except Exception as e:
            logging.error(f"Gemini theme generation failed: {e}")
            return self._config_from_theme_colors(theme_colors)

    def customize_config(self, current_config: WidgetConfig, instruction: str) -> WidgetConfig:
        """Customize an existing config based on a user instruction."""
        sanitized, is_safe = PromptGuard.sanitize(instruction)
        if not is_safe:
            raise ValueError("Customization request blocked: unsafe input detected")

        try:
            prompt_text = CUSTOMIZATION_PROMPT.format(
                current_config=json.dumps(current_config.model_dump(), indent=2),
                instruction=sanitized,
            )
            response = self.llm.invoke(prompt_text)
            return self._parse_config_response(response.content)
        except ValueError:
            raise
        except Exception as e:
            logging.error(f"Gemini customization failed: {e}")
            return current_config

    def _parse_config_response(self, content: str) -> WidgetConfig:
        """Parse Gemini's response into a WidgetConfig."""
        try:
            # Strip markdown code fences if present
            cleaned = content.strip()
            if cleaned.startswith('```'):
                cleaned = re.sub(r'^```(?:json)?\s*', '', cleaned)
                cleaned = re.sub(r'\s*```$', '', cleaned)

            data = json.loads(cleaned)

            # Validate button_shape
            if data.get('button_shape') not in ('pill', 'circle', 'rounded-square'):
                data['button_shape'] = 'pill'

            # Validate button_icon
            if data.get('button_icon') not in WIDGET_ICONS:
                data['button_icon'] = 'chat'

            return WidgetConfig(**data)
        except (json.JSONDecodeError, Exception) as e:
            logging.error(f"Failed to parse Gemini config response: {e}")
            return WidgetConfig()

    def _config_from_theme_colors(self, theme_colors: Dict) -> WidgetConfig:
        """Create a WidgetConfig directly from extracted theme colors (fallback)."""
        is_dark = theme_colors.get('is_dark', False)
        primary = theme_colors.get('primary_color', '#667eea')
        secondary = theme_colors.get('secondary_color', '#764ba2')

        if is_dark:
            return WidgetConfig(
                primary_color=primary,
                secondary_color=secondary,
                bg_color=theme_colors.get('background_color', '#1a1b2e'),
                surface_color='#232442',
                text_color=theme_colors.get('text_color', '#e2e4f0'),
                text_secondary_color='#9498b8',
                border_color='#2e3055',
                is_dark=True,
            )
        else:
            return WidgetConfig(
                primary_color=primary,
                secondary_color=secondary,
                bg_color='#ffffff',
                surface_color='#f5f5f5',
                text_color=theme_colors.get('text_color', '#333333'),
                text_secondary_color='#666666',
                border_color='#e0e0e0',
                user_msg_text_color='#ffffff',
                bot_msg_bg_color='#f5f5f5',
                bot_msg_text_color='#333333',
                input_bg_color='#ffffff',
                input_text_color='#333333',
                input_placeholder_color='#999999',
                is_dark=False,
            )


# ============================================================
# Widget Code Renderer
# ============================================================

class WidgetCodeRenderer:
    """Renders self-contained embeddable widget code from a WidgetConfig."""

    def render(self, config: WidgetConfig, namespace: str, api_base: str) -> str:
        """Generate a complete, self-contained widget code block."""
        # Sanitize namespace to prevent XSS
        safe_namespace = self._escape_js_string(namespace)
        safe_api_base = self._escape_js_string(api_base)

        icon_svg = WIDGET_ICONS.get(config.button_icon, WIDGET_ICONS['chat'])
        button_radius = self._get_button_radius(config.button_shape)
        button_size_css = self._get_button_size_css(config.button_shape)
        safe_button_text = self._escape_js_string(config.button_text)
        safe_header_title = self._escape_js_string(config.header_title)
        safe_placeholder = self._escape_js_string(config.input_placeholder)

        # The button inner HTML depends on shape
        if config.button_shape == 'circle':
            button_inner_html = f'{icon_svg}'
        else:
            button_inner_html = f'<span>{safe_button_text}</span>{icon_svg}'

        code = f'''<!-- Chat Widget - Generated by Virtual Assistant Setup -->
<script src="https://cdnjs.cloudflare.com/ajax/libs/marked/11.1.1/marked.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/dompurify/3.0.8/purify.min.js"></script>
<script>
(function() {{
  var NAMESPACE = "{safe_namespace}";
  var API_BASE = "{safe_api_base}";

  if (typeof marked !== 'undefined') {{
    marked.setOptions({{ breaks: true, gfm: true, headerIds: false, mangle: false }});
  }}

  var conversationHistory = [];

  // --- Styles ---
  var style = document.createElement('style');
  style.textContent = '\\
    #cw-btn {{\\
      position: fixed !important;\\
      bottom: 20px !important;\\
      right: 20px !important;\\
      {button_size_css}\\
      border-radius: {button_radius} !important;\\
      background: linear-gradient(135deg, {config.primary_color} 0%, {config.secondary_color} 100%) !important;\\
      border: none !important;\\
      cursor: pointer !important;\\
      box-shadow: 0 4px 12px rgba(0,0,0,0.15) !important;\\
      display: flex !important;\\
      align-items: center !important;\\
      justify-content: center !important;\\
      gap: 12px !important;\\
      transition: transform 0.2s, box-shadow 0.2s !important;\\
      z-index: 99999 !important;\\
      color: white !important;\\
      font-size: 16px !important;\\
      font-weight: 600 !important;\\
      font-family: -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif !important;\\
    }}\\
    #cw-btn.cw-hide {{ display: none !important; }}\\
    #cw-btn:hover {{ transform: scale(1.05) !important; box-shadow: 0 6px 16px rgba(0,0,0,0.2) !important; }}\\
    #cw-btn svg {{ width: 24px !important; height: 24px !important; fill: white !important; flex-shrink: 0 !important; }}\\
    #cw-win {{\\
      position: fixed !important;\\
      bottom: 20px !important;\\
      right: 20px !important;\\
      width: 450px !important;\\
      height: 600px !important;\\
      background: {config.bg_color} !important;\\
      border-radius: 12px !important;\\
      box-shadow: 0 8px 32px rgba(0,0,0,0.4) !important;\\
      border: 1px solid {config.border_color} !important;\\
      display: none !important;\\
      flex-direction: column !important;\\
      z-index: 99999 !important;\\
      overflow: hidden !important;\\
    }}\\
    #cw-win.cw-open {{ display: flex !important; animation: cwSlide 0.3s ease !important; }}\\
    @keyframes cwSlide {{ from {{ opacity: 0; transform: translateY(20px); }} to {{ opacity: 1; transform: translateY(0); }} }}\\
    #cw-hdr {{\\
      background: linear-gradient(135deg, {config.primary_color} 0%, {config.secondary_color} 100%) !important;\\
      color: white !important;\\
      padding: 16px 20px !important;\\
      display: flex !important;\\
      justify-content: space-between !important;\\
      align-items: center !important;\\
    }}\\
    #cw-hdr h3 {{ font-size: 16px !important; font-weight: 600 !important; margin: 0 !important; }}\\
    #cw-hdr-actions {{ display: flex !important; gap: 12px !important; align-items: center !important; }}\\
    #cw-clear {{\\
      background: rgba(255,255,255,0.2) !important;\\
      border: 1px solid rgba(255,255,255,0.3) !important;\\
      color: white !important;\\
      font-size: 12px !important;\\
      padding: 6px 12px !important;\\
      border-radius: 16px !important;\\
      cursor: pointer !important;\\
      font-weight: 500 !important;\\
    }}\\
    #cw-clear:hover {{ background: rgba(255,255,255,0.3) !important; }}\\
    #cw-close {{\\
      background: none !important;\\
      border: none !important;\\
      color: white !important;\\
      font-size: 24px !important;\\
      cursor: pointer !important;\\
      padding: 0 !important;\\
    }}\\
    #cw-msgs {{\\
      flex: 1 !important;\\
      padding: 20px !important;\\
      overflow-y: auto !important;\\
      background: {config.bg_color} !important;\\
    }}\\
    .cw-msg {{ margin-bottom: 16px !important; animation: cwFade 0.3s ease !important; }}\\
    @keyframes cwFade {{ from {{ opacity: 0; transform: translateY(10px); }} to {{ opacity: 1; transform: translateY(0); }} }}\\
    .cw-msg.cw-usr {{ text-align: right !important; }}\\
    .cw-msg-c {{\\
      display: inline-block !important;\\
      padding: 12px 16px !important;\\
      border-radius: 18px !important;\\
      max-width: 85% !important;\\
      word-wrap: break-word !important;\\
      line-height: 1.5 !important;\\
    }}\\
    .cw-msg.cw-usr .cw-msg-c {{\\
      background: linear-gradient(135deg, {config.primary_color} 0%, {config.secondary_color} 100%) !important;\\
      color: {config.user_msg_text_color} !important;\\
    }}\\
    .cw-msg.cw-bot .cw-msg-c {{\\
      background: {config.bot_msg_bg_color} !important;\\
      color: {config.bot_msg_text_color} !important;\\
      text-align: left !important;\\
      box-shadow: 0 2px 8px rgba(0,0,0,0.3) !important;\\
    }}\\
    .cw-msg.cw-bot .cw-msg-c p {{ margin: 0 0 8px 0 !important; }}\\
    .cw-msg.cw-bot .cw-msg-c p:last-child {{ margin-bottom: 0 !important; }}\\
    .cw-msg.cw-bot .cw-msg-c code {{\\
      background: {config.border_color} !important;\\
      color: {config.bot_msg_text_color} !important;\\
      padding: 2px 6px !important;\\
      border-radius: 4px !important;\\
      font-family: Courier New, monospace !important;\\
      font-size: 0.9em !important;\\
    }}\\
    .cw-msg.cw-bot .cw-msg-c pre {{\\
      background: {config.border_color} !important;\\
      padding: 12px !important;\\
      border-radius: 6px !important;\\
      overflow-x: auto !important;\\
      margin: 8px 0 !important;\\
    }}\\
    .cw-msg.cw-bot .cw-msg-c ul, .cw-msg.cw-bot .cw-msg-c ol {{\\
      margin: 8px 0 !important;\\
      padding-left: 20px !important;\\
    }}\\
    .cw-think {{\\
      display: inline-flex !important;\\
      gap: 6px !important;\\
      padding: 12px 16px !important;\\
      background: {config.bot_msg_bg_color} !important;\\
      border-radius: 18px !important;\\
      box-shadow: 0 2px 8px rgba(0,0,0,0.3) !important;\\
    }}\\
    .cw-think span {{\\
      display: inline-block !important;\\
      width: 8px !important;\\
      height: 8px !important;\\
      border-radius: 50% !important;\\
      background: {config.primary_color} !important;\\
      animation: cwBounce 1.4s infinite ease-in-out !important;\\
    }}\\
    .cw-think span:nth-child(1) {{ animation-delay: -0.32s !important; }}\\
    .cw-think span:nth-child(2) {{ animation-delay: -0.16s !important; }}\\
    @keyframes cwBounce {{ 0%,80%,100% {{ transform: scale(0); }} 40% {{ transform: scale(1); }} }}\\
    #cw-inp-wrap {{\\
      padding: 16px 20px !important;\\
      background: {config.bg_color} !important;\\
      border-top: 1px solid {config.border_color} !important;\\
      display: flex !important;\\
      gap: 10px !important;\\
      align-items: center !important;\\
    }}\\
    #cw-inp {{\\
      flex: 1 !important;\\
      padding: 10px 14px !important;\\
      border: 1px solid {config.border_color} !important;\\
      border-radius: 20px !important;\\
      font-size: 14px !important;\\
      outline: none !important;\\
      background: {config.input_bg_color} !important;\\
      color: {config.input_text_color} !important;\\
      font-family: inherit !important;\\
    }}\\
    #cw-inp::placeholder {{ color: {config.input_placeholder_color} !important; }}\\
    #cw-inp:focus {{ border-color: {config.primary_color} !important; }}\\
    #cw-send {{\\
      width: 40px !important; min-width: 40px !important; height: 40px !important;\\
      border-radius: 50% !important;\\
      background: linear-gradient(135deg, {config.primary_color} 0%, {config.secondary_color} 100%) !important;\\
      border: none !important;\\
      cursor: pointer !important;\\
      display: flex !important;\\
      align-items: center !important;\\
      justify-content: center !important;\\
      flex-shrink: 0 !important;\\
      transition: transform 0.2s !important;\\
    }}\\
    #cw-send:hover {{ transform: scale(1.05) !important; }}\\
    #cw-send:disabled {{ opacity: 0.5 !important; cursor: not-allowed !important; }}\\
    #cw-send svg {{ width: 18px !important; height: 18px !important; fill: white !important; }}\\
    @media (max-width: 480px) {{\\
      #cw-win {{ width: calc(100% - 40px) !important; height: calc(100% - 120px) !important; }}\\
    }}\\
  ';
  document.head.appendChild(style);

  // --- Widget Button ---
  var btn = document.createElement('button');
  btn.id = 'cw-btn';
  btn.setAttribute('aria-label', 'Open chat');
  btn.innerHTML = '{self._escape_for_js_string(button_inner_html)}';
  document.body.appendChild(btn);

  // --- Chat Window ---
  var win = document.createElement('div');
  win.id = 'cw-win';
  win.innerHTML = '\\
    <div id="cw-hdr">\\
      <h3>{safe_header_title}</h3>\\
      <div id="cw-hdr-actions">\\
        <button id="cw-clear">Clear Chat</button>\\
        <button id="cw-close">&times;</button>\\
      </div>\\
    </div>\\
    <div id="cw-msgs"></div>\\
    <div id="cw-inp-wrap">\\
      <input type="text" id="cw-inp" placeholder="{safe_placeholder}" />\\
      <button id="cw-send">\\
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg>\\
      </button>\\
    </div>\\
  ';
  document.body.appendChild(win);

  // --- Logic ---
  var msgs = document.getElementById('cw-msgs');
  var inp = document.getElementById('cw-inp');
  var sendBtn = document.getElementById('cw-send');

  function renderMd(t) {{
    if (typeof marked !== 'undefined' && typeof DOMPurify !== 'undefined') {{
      return DOMPurify.sanitize(marked.parse(t));
    }}
    return t.replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }}

  function escHtml(t) {{
    var d = document.createElement('div');
    d.textContent = t;
    return d.innerHTML;
  }}

  function addWelcome() {{
    var m = document.createElement('div');
    m.className = 'cw-msg cw-bot';
    m.innerHTML = '<div class="cw-msg-c">' + renderMd("Hi! I\\\'m your virtual assistant for **" + NAMESPACE + "**!\\n\\nI can answer questions about this website. Ask me anything!") + '</div>';
    msgs.appendChild(m);
  }}

  function fmtHistory() {{
    if (!conversationHistory.length) return "";
    return conversationHistory.map(function(h) {{ return "User: " + h.u + "\\nChatbot: " + h.b; }}).join("\\n\\n");
  }}

  function sendMsg() {{
    var q = inp.value.trim();
    if (!q) return;
    var um = document.createElement('div');
    um.className = 'cw-msg cw-usr';
    um.innerHTML = '<div class="cw-msg-c">' + escHtml(q) + '</div>';
    msgs.appendChild(um);
    inp.value = '';
    sendBtn.disabled = true;

    var tm = document.createElement('div');
    tm.className = 'cw-msg cw-bot';
    tm.innerHTML = '<div class="cw-think"><span></span><span></span><span></span></div>';
    msgs.appendChild(tm);
    msgs.scrollTop = msgs.scrollHeight;

    fetch(API_BASE + '/chat', {{
      method: 'POST',
      headers: {{ 'Accept': 'application/json', 'Content-Type': 'application/json' }},
      body: JSON.stringify({{ question: q, conv_history: fmtHistory(), namespace: NAMESPACE }})
    }})
    .then(function(r) {{ if (!r.ok) throw new Error('Network error'); return r.json(); }})
    .then(function(data) {{
      msgs.removeChild(tm);
      var bm = document.createElement('div');
      bm.className = 'cw-msg cw-bot';
      bm.innerHTML = '<div class="cw-msg-c">' + renderMd(data.answer) + '</div>';
      msgs.appendChild(bm);
      msgs.scrollTop = msgs.scrollHeight;
      conversationHistory.push({{ u: q, b: data.answer }});
    }})
    .catch(function() {{
      msgs.removeChild(tm);
      var em = document.createElement('div');
      em.className = 'cw-msg cw-bot';
      em.innerHTML = '<div class="cw-msg-c">Sorry, I encountered an error. Please try again.</div>';
      msgs.appendChild(em);
    }})
    .finally(function() {{ sendBtn.disabled = false; inp.focus(); }});
  }}

  btn.addEventListener('click', function() {{
    win.classList.add('cw-open');
    btn.classList.add('cw-hide');
    if (!msgs.children.length) addWelcome();
    inp.focus();
  }});
  document.getElementById('cw-close').addEventListener('click', function() {{
    win.classList.remove('cw-open');
    btn.classList.remove('cw-hide');
  }});
  document.getElementById('cw-clear').addEventListener('click', function() {{
    conversationHistory = [];
    msgs.innerHTML = '';
    addWelcome();
  }});
  sendBtn.addEventListener('click', sendMsg);
  inp.addEventListener('keypress', function(e) {{ if (e.key === 'Enter') sendMsg(); }});

  console.log('Chat widget loaded for namespace: ' + NAMESPACE);
}})();
</script>'''

        # Validate the output
        validated_code, is_safe = PromptGuard.validate_output(code)
        if not is_safe:
            logging.error("Generated widget code failed safety validation")
            return self.render(WidgetConfig(), namespace, api_base)

        return code

    def get_integration_guide(self) -> str:
        """Return step-by-step integration instructions."""
        return """## How to Add the Chat Widget to Your Website

**Step 1: Copy the Code**
Click the "Copy Code" button above to copy the widget code to your clipboard.

**Step 2: Open Your Website's HTML**
Open the HTML file of the page where you want the widget to appear (typically `index.html` or your main layout template).

**Step 3: Paste Before the Closing Body Tag**
Paste the copied code just before the closing `</body>` tag at the bottom of your HTML file:

```html
    <!-- Your existing page content above -->

    <!-- Paste the widget code here -->
    <script src="https://cdnjs.cloudflare.com/ajax/libs/marked/..."></script>
    <script>
    (function() {
      // ... widget code ...
    })();
    </script>

  </body>
</html>
```

**Step 4: Save and Deploy**
Save the file and deploy/publish your changes. The chat widget will appear as a floating button in the bottom-right corner of your website.

**Step 5: Test It**
Visit your website and click the widget button to open the chat. Try asking a question to make sure everything is working.

**Tips:**
- The widget works on all modern browsers (Chrome, Firefox, Safari, Edge)
- It's mobile-responsive and will adapt to smaller screens
- The widget loads its own dependencies (marked.js for markdown, DOMPurify for security)
- You can place the code in your site's footer template to make it appear on all pages"""

    def _escape_js_string(self, s: str) -> str:
        """Escape a string for safe embedding in JavaScript."""
        s = s.replace('\\', '\\\\')
        s = s.replace('"', '\\"')
        s = s.replace("'", "\\'")
        s = s.replace('\n', '\\n')
        s = s.replace('\r', '\\r')
        s = s.replace('</', '<\\/')  # Prevent </script> injection
        s = s.replace('<script', '&lt;script')
        s = s.replace('</script', '&lt;/script')
        return s

    def _escape_for_js_string(self, s: str) -> str:
        """Escape HTML content for embedding inside a JS string literal."""
        s = s.replace('\\', '\\\\')
        s = s.replace("'", "\\'")
        s = s.replace('"', '\\"')
        s = s.replace('\n', '')
        s = s.replace('</', '<\\/')
        return s

    def _get_button_radius(self, shape: str) -> str:
        if shape == 'circle':
            return '50%'
        elif shape == 'rounded-square':
            return '12px'
        else:  # pill
            return '30px'

    def _get_button_size_css(self, shape: str) -> str:
        if shape == 'circle':
            return 'width: 60px !important; height: 60px !important; padding: 0 !important;'
        elif shape == 'rounded-square':
            return 'width: auto !important; height: 60px !important; padding: 0 24px !important;'
        else:  # pill
            return 'width: auto !important; height: 60px !important; padding: 0 24px !important;'
