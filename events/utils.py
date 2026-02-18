import qrcode
import random
import math
import os
import logging
from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageFilter
from io import BytesIO
from django.core.files import File
from django.conf import settings
from .models import Guest, SVGOverlay
import textwrap
from functools import lru_cache
from typing import Tuple, Optional

# Configure logging
logger = logging.getLogger(__name__)

# High-quality DPI settings for printing
PRINT_DPI = 300
SCREEN_DPI = 96
CARD_WIDTH_INCHES = 5
CARD_HEIGHT_INCHES = 7


# =========================
# BASIC HELPERS
# =========================

@lru_cache(maxsize=128)
def hex_to_rgb(hex_color: str, alpha: Optional[int] = None) -> Tuple[int, int, int]:
    """Convert hex to RGB with better error handling and alpha support"""
    if not isinstance(hex_color, str):
        logger.warning(f"Invalid hex color type: {type(hex_color)}, using default")
        return (124, 61, 237)  # Default purple
    
    hex_color = hex_color.lstrip('#').strip()
    
    try:
        if len(hex_color) == 3:
            hex_color = ''.join([c*2 for c in hex_color])
        
        if len(hex_color) == 6:
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)
            return (r, g, b)
        elif len(hex_color) == 8:
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)
            return (r, g, b)
        else:
            logger.warning(f"Invalid hex color length: {hex_color}")
            return (124, 61, 237)
    except ValueError:
        logger.error(f"Could not parse hex color: {hex_color}")
        return (124, 61, 237)


def get_color_contrast(rgb: Tuple[int, int, int]) -> Tuple[int, int, int]:
    """Get contrasting color (black or white) based on luminance"""
    r, g, b = rgb
    luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    return (255, 255, 255) if luminance < 0.5 else (0, 0, 0)


def rgba_to_rgb(rgba, background=(255, 255, 255)):
    """Convert RGBA to RGB with white background"""
    if len(rgba) == 4:
        r, g, b, a = rgba
        bg_r, bg_g, bg_b = background
        alpha = a / 255.0
        
        r = int(r * alpha + bg_r * (1 - alpha))
        g = int(g * alpha + bg_g * (1 - alpha))
        b = int(b * alpha + bg_b * (1 - alpha))
        return (r, g, b)
    return rgba[:3]


def generate_qr_code(data, size=280, primary_color="#7C3AED", bg_color="#FFFFFF"):
    """Generate high-quality QR code with custom colors"""
    try:
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=10,
            border=4,
        )
        qr.add_data(data)
        qr.make(fit=True)

        # Ensure colors are valid RGB tuples
        fill_color = hex_to_rgb(primary_color)
        back_color = hex_to_rgb(bg_color)

        qr_img = qr.make_image(
            fill_color=fill_color,
            back_color=back_color
        ).convert("RGB")

        # Resize with high-quality resampling
        qr_img = qr_img.resize((size, size), Image.Resampling.LANCZOS)
        
        logger.debug(f"QR code generated successfully: {size}x{size}")
        return qr_img
    except Exception as e:
        logger.error(f"Error generating QR code: {str(e)}")
        # Return a blank image as fallback
        return Image.new('RGB', (size, size), back_color)


@lru_cache(maxsize=256)
def load_custom_font(font_name, size):
    """Load font from multiple possible locations with better fallback system"""
    if not font_name or size <= 0:
        logger.warning(f"Invalid font request: {font_name}, size: {size}")
        return ImageFont.load_default()
    
    font_paths = [
        os.path.join(settings.BASE_DIR, "static/fonts", f"{font_name}.ttf"),
        os.path.join(settings.BASE_DIR, "static/fonts", f"{font_name}.otf"),
        os.path.join(settings.BASE_DIR, "fonts", f"{font_name}.ttf"),
        os.path.join(settings.BASE_DIR, "fonts", f"{font_name}.otf"),
        os.path.join("C:/Windows/Fonts", f"{font_name}.ttf"),
        os.path.join("C:/Windows/Fonts", f"{font_name}.otf"),
        os.path.join("/System/Library/Fonts", f"{font_name}.ttf"),
        os.path.join("/usr/share/fonts/truetype", f"{font_name}.ttf"),
        os.path.join("/usr/share/fonts/opentype", f"{font_name}.otf"),
    ]
    
    # Try to load specified font
    for path in font_paths:
        if os.path.exists(path):
            try:
                font = ImageFont.truetype(path, size)
                logger.debug(f"Font loaded: {font_name} from {path}")
                return font
            except Exception as e:
                logger.debug(f"Failed to load font {path}: {e}")
                continue
    
    # Fallback to system fonts based on font name
    fallback_map = {
        'Marckscript': ['/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf', 
                        'C:/Windows/Fonts/arial.ttf'],
        'DancingScript': ['/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf',
                         'C:/Windows/Fonts/arialbd.ttf'],
        'PlayfairDisplay': ['/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf',
                           'C:/Windows/Fonts/times.ttf'],
        'GreatVibes': ['/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf',
                      'C:/Windows/Fonts/arial.ttf'],
        'Allura': ['/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf',
                  'C:/Windows/Fonts/arial.ttf'],
        'Sacramento': ['/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf',
                      'C:/Windows/Fonts/arial.ttf'],
        'Parisienne': ['/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf',
                      'C:/Windows/Fonts/arial.ttf'],
        'Cormorant': ['/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf',
                     'C:/Windows/Fonts/times.ttf'],
        'Cardo': ['/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf',
                 'C:/Windows/Fonts/times.ttf'],
    }
    
    # Try fallback fonts
    for key, paths in fallback_map.items():
        if key.lower() in font_name.lower():
            for path in paths:
                if os.path.exists(path):
                    try:
                        font = ImageFont.truetype(path, size)
                        logger.debug(f"Font fallback loaded: {font_name} -> {path}")
                        return font
                    except Exception as e:
                        logger.debug(f"Failed to load fallback {path}: {e}")
    
    # Ultimate fallback
    try:
        return ImageFont.truetype("arial.ttf", size)
    except:
        logger.warning(f"Using default font for {font_name}, size {size}")
        return ImageFont.load_default()


def wrap_text(text, font, max_width):
    """Wrap text to fit within max_width with better handling"""
    if not text:
        return []
    
    lines = []
    words = text.split()
    
    while words:
        line = ''
        while words:
            test_line = line + words[0] + ' '
            bbox = font.getbbox(test_line)
            if bbox[2] - bbox[0] <= max_width:
                line = test_line
                words.pop(0)
            else:
                break
        
        if not line:
            # Word is too long, break it
            line = words.pop(0)
        
        lines.append(line.strip())
    
    return lines


def add_shadow(draw, text, position, font, text_color, shadow_color=(0, 0, 0, 100), offset=(2, 2)):
    """Add improved shadow effect to text with proper anti-aliasing"""
    if not text:
        return
    
    x, y = position
    shadow_x, shadow_y = offset
    
    try:
        # Convert colors to proper format
        if isinstance(shadow_color, tuple) and len(shadow_color) == 4:
            # Draw shadow with transparency
            draw.text((x + shadow_x, y + shadow_y), text, font=font, fill=shadow_color[:3])
        else:
            draw.text((x + shadow_x, y + shadow_y), text, font=font, fill=shadow_color)
        
        # Draw main text
        draw.text((x, y), text, font=font, fill=text_color)
    except Exception as e:
        logger.error(f"Error drawing text with shadow: {e}")
        # Fallback: just draw text without shadow
        draw.text((x, y), text, font=font, fill=text_color)


def create_gradient_background(width, height, start_color, end_color):
    """Create a smooth gradient background image"""
    start_rgb = hex_to_rgb(start_color)
    end_rgb = hex_to_rgb(end_color)
    
    img = Image.new('RGB', (width, height))
    pixels = img.load()
    
    for y in range(height):
        factor = y / height
        r = int(start_rgb[0] * (1 - factor) + end_rgb[0] * factor)
        g = int(start_rgb[1] * (1 - factor) + end_rgb[1] * factor)
        b = int(start_rgb[2] * (1 - factor) + end_rgb[2] * factor)
        
        for x in range(width):
            pixels[x, y] = (r, g, b)
    
    return img


# =========================
# CARD GENERATOR - IMPROVED
# =========================

class CardGenerator:
    """High-quality invitation card generator with modern design"""
    
    def __init__(self, guest):
        self.guest = guest
        self.event = guest.event
        self.settings = self.event.get_template_settings()
        
        # Increased resolution for high-quality printing (300 DPI)
        self.width = CARD_WIDTH_INCHES * PRINT_DPI  # 1500 pixels @ 300 DPI
        self.height = CARD_HEIGHT_INCHES * PRINT_DPI  # 2100 pixels @ 300 DPI
        
        self.card = None
        self.draw = None
        self.margin = int(60 * (PRINT_DPI / SCREEN_DPI))  # Safe margin from edges
        self.content_width = self.width - (2 * self.margin)
        
        logger.info(f"CardGenerator initialized for {guest.full_name} - {guest.event.title}")
        logger.info(f"Card dimensions: {self.width}x{self.height}px @ {PRINT_DPI}DPI")

    def load_background_image(self):
        """Load background image if available"""
        try:
            if self.event.template_svg and os.path.exists(self.event.template_svg.path):
                if self.event.template_svg.path.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
                    bg = Image.open(self.event.template_svg.path).convert('RGBA')
                    bg = bg.resize((self.width, self.height), Image.Resampling.LANCZOS)
                    
                    # Apply opacity
                    if bg.mode == 'RGBA':
                        alpha = bg.split()[3]
                        alpha = ImageEnhance.Brightness(alpha).enhance(0.3)  # 30% opacity
                        bg.putalpha(alpha)
                    
                    logger.debug("Background image loaded successfully")
                    return bg
        except Exception as e:
            logger.warning(f"Could not load background image: {e}")
        
        return None

    def create_background(self):
        """Create background with gradient and optional image"""
        try:
            bg_color = hex_to_rgb(self.settings["colors"]["background"])
            self.card = Image.new("RGB", (self.width, self.height), bg_color)
            self.draw = ImageDraw.Draw(self.card)
            
            # Add gradient overlay
            if self.settings['decorations'].get('gradient_background', True):
                sec_color = hex_to_rgb(self.settings["colors"]["secondary"])
                gradient = create_gradient_background(self.width, self.height, 
                                                     self.settings["colors"]["background"],
                                                     self.settings["colors"]["secondary"])
                self.card.paste(gradient)
                self.draw = ImageDraw.Draw(self.card)
            
            # Overlay background image if available
            bg_image = self.load_background_image()
            if bg_image:
                self.card = Image.alpha_composite(
                    self.card.convert('RGBA'), 
                    bg_image
                ).convert('RGB')
                self.draw = ImageDraw.Draw(self.card)
            
            logger.debug("Background created successfully")
        except Exception as e:
            logger.error(f"Error creating background: {e}")
            # Create solid fallback background
            self.card = Image.new("RGB", (self.width, self.height), (255, 255, 255))
            self.draw = ImageDraw.Draw(self.card)

    def add_decorative_border(self):
        """Add decorative border based on template settings"""
        if not self.settings["decorations"]["show_border"]:
            return
        
        try:
            border_color = hex_to_rgb(self.settings["colors"]["primary"])
            secondary_color = hex_to_rgb(self.settings["colors"]["secondary"])
            border_width = int(15 * (PRINT_DPI / SCREEN_DPI))
            
            border_style = self.settings["decorations"]["border_style"]
            
            if border_style == 'rounded':
                # Rounded rectangle border with gradient effect
                self.draw.rounded_rectangle(
                    [border_width, border_width, 
                     self.width - border_width, self.height - border_width],
                    radius=int(80 * (PRINT_DPI / SCREEN_DPI)),
                    outline=border_color,
                    width=border_width
                )
                # Add secondary colored inner border
                self.draw.rounded_rectangle(
                    [border_width + 5, border_width + 5, 
                     self.width - border_width - 5, self.height - border_width - 5],
                    radius=int(75 * (PRINT_DPI / SCREEN_DPI)),
                    outline=secondary_color,
                    width=2
                )
                
            elif border_style == 'floral':
                # Enhanced floral pattern border with decorative flowers
                pattern_size = 60
                for i in range(0, self.width, pattern_size):
                    # Top border flowers
                    self.draw.ellipse(
                        [i + 10, 20, i + 40, 50],
                        outline=border_color,
                        width=3
                    )
                    # Bottom border flowers
                    self.draw.ellipse(
                        [i + 10, self.height - 50, i + 40, self.height - 20],
                        outline=border_color,
                        width=3
                    )
                
                # Side decorations
                for j in range(0, self.height, pattern_size):
                    self.draw.ellipse(
                        [10, j, 40, j + 30],
                        outline=border_color,
                        width=2
                    )
                    self.draw.ellipse(
                        [self.width - 40, j, self.width - 10, j + 30],
                        outline=border_color,
                        width=2
                    )
            
            elif border_style == 'geometric':
                # Enhanced geometric pattern border
                pattern_size = 40
                for i in range(0, self.width, pattern_size):
                    if i % (pattern_size * 2) == 0:
                        # Top triangles
                        self.draw.polygon(
                            [(i, 0), (i + pattern_size, 0), (i + pattern_size//2, border_width)],
                            fill=border_color
                        )
                        # Bottom triangles
                        self.draw.polygon(
                            [(i, self.height), (i + pattern_size, self.height), 
                             (i + pattern_size//2, self.height - border_width)],
                            fill=border_color
                        )
            
            logger.debug(f"Border added: {border_style}")
        except Exception as e:
            logger.error(f"Error adding decorative border: {e}")

    def draw_header(self):
        """Draw event title header with modern styling"""
        try:
            # Header background with dynamic height
            header_height = int(180 * (PRINT_DPI / SCREEN_DPI))
            header_color = hex_to_rgb(self.settings["colors"]["primary"])
            
            # Create gradient header background
            header_gradient = create_gradient_background(
                self.width, header_height,
                self.settings["colors"]["primary"],
                self.settings["colors"]["secondary"]
            )
            self.card.paste(header_gradient, (0, 0))
            self.draw = ImageDraw.Draw(self.card)
            
            # Event title
            font_size = int(64 * (PRINT_DPI / SCREEN_DPI))
            font = load_custom_font(self.settings["fonts"]["title"], font_size)
            title_text = self.event.title.upper()
            
            # Ensure title fits
            max_attempts = 10
            attempts = 0
            while attempts < max_attempts and self.draw.textbbox((0, 0), title_text, font=font)[2] > self.content_width:
                font_size -= 2
                font = load_custom_font(self.settings["fonts"]["title"], font_size)
                attempts += 1
            
            text_width = self.draw.textbbox((0, 0), title_text, font=font)[2]
            text_height = self.draw.textbbox((0, 0), title_text, font=font)[3]
            x = (self.width - text_width) // 2
            y = int((header_height - text_height) // 2)
            
            # Draw title with enhanced shadow
            add_shadow(
                self.draw, title_text, (x, y), font,
                text_color=(255, 255, 255),
                shadow_color=(0, 0, 0),
                offset=(3, 3)
            )
            
            # Divider line
            divider_y = y + text_height + int(20 * (PRINT_DPI / SCREEN_DPI))
            self.draw.line(
                [(self.width//2 - 100, divider_y), (self.width//2 + 100, divider_y)],
                fill=(255, 255, 255),
                width=3
            )
            
            logger.debug("Header drawn successfully")
            return divider_y + int(30 * (PRINT_DPI / SCREEN_DPI))
        except Exception as e:
            logger.error(f"Error drawing header: {e}")
            return int(200 * (PRINT_DPI / SCREEN_DPI))

    def draw_guest_section(self, start_y):
        """Draw guest name section with modern highlight"""
        try:
            # Background highlight for name
            highlight_height = int(140 * (PRINT_DPI / SCREEN_DPI))
            highlight_color_rgb = hex_to_rgb(self.settings["colors"]["secondary"])
            
            self.draw.rounded_rectangle(
                [self.margin, start_y, 
                 self.width - self.margin, start_y + highlight_height],
                radius=int(30 * (PRINT_DPI / SCREEN_DPI)),
                fill=highlight_color_rgb
            )
            
            # Guest name
            font_size = int(72 * (PRINT_DPI / SCREEN_DPI))
            font = load_custom_font(self.settings["fonts"]["name"], font_size)
            guest_name = f"{self.guest.title} {self.guest.full_name}"
            
            # Ensure name fits with better logic
            max_attempts = 15
            attempts = 0
            while attempts < max_attempts and self.draw.textbbox((0, 0), guest_name, font=font)[2] > self.content_width - 100:
                font_size -= 2
                font = load_custom_font(self.settings["fonts"]["name"], font_size)
                attempts += 1
            
            text_bbox = self.draw.textbbox((0, 0), guest_name, font=font)
            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]
            x = (self.width - text_width) // 2
            y = start_y + (highlight_height - text_height) // 2
            
            # Accent color for name
            accent_color = hex_to_rgb(self.settings["colors"]["accent"])
            
            # Draw name with shadow
            add_shadow(
                self.draw, guest_name, (x, y), font,
                text_color=accent_color,
                shadow_color=(0, 0, 0),
                offset=(2, 2)
            )
            
            # Decorative underline
            underline_y = y + text_height + int(5 * (PRINT_DPI / SCREEN_DPI))
            self.draw.line(
                [(x - 20, underline_y), (x + text_width + 20, underline_y)],
                fill=accent_color,
                width=2
            )
            
            logger.debug("Guest section drawn successfully")
            return start_y + highlight_height + int(40 * (PRINT_DPI / SCREEN_DPI))
        except Exception as e:
            logger.error(f"Error drawing guest section: {e}")
            return start_y + int(180 * (PRINT_DPI / SCREEN_DPI))

    def draw_invitation_message(self, start_y):
        """Draw invitation message with better styling"""
        try:
            font_size = int(36 * (PRINT_DPI / SCREEN_DPI))
            font = load_custom_font(self.settings["fonts"]["body"], font_size)
            
            # Use custom message or default
            message = self.guest.custom_message or "You are cordially invited to join us for a celebration of love and joy"
            
            # Wrap text
            max_line_width = self.content_width - int(40 * (PRINT_DPI / SCREEN_DPI))
            lines = wrap_text(message, font, max_line_width)
            
            # Calculate total height needed
            line_height = font_size + int(10 * (PRINT_DPI / SCREEN_DPI))
            
            # Center vertically
            y = start_y
            message_color = hex_to_rgb(self.settings["colors"]["accent"])
            
            for line in lines:
                text_bbox = self.draw.textbbox((0, 0), line, font=font)
                text_width = text_bbox[2] - text_bbox[0]
                x = (self.width - text_width) // 2
                self.draw.text((x, y), line, font=font, fill=message_color)
                y += line_height
            
            logger.debug("Invitation message drawn successfully")
            return y + int(30 * (PRINT_DPI / SCREEN_DPI))
        except Exception as e:
            logger.error(f"Error drawing invitation message: {e}")
            return start_y + int(150 * (PRINT_DPI / SCREEN_DPI))

    def draw_event_details_card(self, start_y):
        """Draw event details in a styled card"""
        try:
            card_height = int(280 * (PRINT_DPI / SCREEN_DPI))
            card_width = self.content_width
            card_x = self.margin
            card_y = start_y
            
            # Card shadow with blur
            shadow_offset = int(8 * (PRINT_DPI / SCREEN_DPI))
            self.draw.rounded_rectangle(
                [card_x + shadow_offset, card_y + shadow_offset,
                 card_x + card_width + shadow_offset, card_y + card_height + shadow_offset],
                radius=int(25 * (PRINT_DPI / SCREEN_DPI)),
                fill=(200, 200, 200)
            )
            
            # Card background
            primary_color = hex_to_rgb(self.settings["colors"]["primary"])
            self.draw.rounded_rectangle(
                [card_x, card_y, card_x + card_width, card_y + card_height],
                radius=int(25 * (PRINT_DPI / SCREEN_DPI)),
                fill=(255, 255, 255),
                outline=primary_color,
                width=3
            )
            
            # Card content
            font_size = int(32 * (PRINT_DPI / SCREEN_DPI))
            font = load_custom_font(self.settings["fonts"]["body"], font_size)
            
            details = [
                {"icon": "📅", "text": f"Date: {self.event.date.strftime('%A, %d %B %Y')}"},
                {"icon": "🕒", "text": f"Time: {self.event.date.strftime('%I:%M %p')}"},
                {"icon": "📍", "text": f"Venue: {self.event.venue}"},
            ]
            
            # Add guest-specific details if available
            if hasattr(self.guest, 'seat_number') and self.guest.seat_number:
                details.append({"icon": "💺", "text": f"Seat: {self.guest.seat_number}"})
            if hasattr(self.guest, 'table_number') and self.guest.table_number:
                details.append({"icon": "🍽️", "text": f"Table: {self.guest.table_number}"})
            
            y_offset = card_y + int(50 * (PRINT_DPI / SCREEN_DPI))
            
            for detail in details:
                # Icon and text
                text_x = card_x + int(60 * (PRINT_DPI / SCREEN_DPI))
                self.draw.text((text_x, y_offset), detail["text"], font=font, 
                              fill=(50, 50, 50))
                
                y_offset += int(55 * (PRINT_DPI / SCREEN_DPI))
            
            logger.debug("Event details card drawn successfully")
            return card_y + card_height + int(40 * (PRINT_DPI / SCREEN_DPI))
        except Exception as e:
            logger.error(f"Error drawing event details card: {e}")
            return start_y + int(320 * (PRINT_DPI / SCREEN_DPI))

    def draw_qr_section(self, start_y):
        """Draw QR code section with decorations"""
        try:
            qr_size = int(320 * (PRINT_DPI / SCREEN_DPI))
            qr_x = (self.width - qr_size) // 2
            qr_y = start_y
            
            # Decorative background for QR
            if self.settings["decorations"]["show_qr_background"]:
                bg_radius = qr_size // 2 + int(25 * (PRINT_DPI / SCREEN_DPI))
                bg_center_x = qr_x + qr_size // 2
                bg_center_y = qr_y + qr_size // 2
                
                secondary_color = hex_to_rgb(self.settings["colors"]["secondary"])
                
                # Create concentric circles
                for i in range(3):
                    radius = bg_radius + i * int(15 * (PRINT_DPI / SCREEN_DPI))
                    self.draw.ellipse(
                        [bg_center_x - radius, bg_center_y - radius,
                         bg_center_x + radius, bg_center_y + radius],
                        outline=secondary_color,
                        width=2
                    )
            
            # Generate and paste QR code
            qr_data = self.guest.generate_qr_data()
            qr_img = generate_qr_code(
                qr_data, 
                qr_size,
                primary_color=self.settings["colors"]["primary"],
                bg_color="#FFFFFF"
            )
            
            # Add border to QR code
            border_size = int(8 * (PRINT_DPI / SCREEN_DPI))
            primary_color = hex_to_rgb(self.settings["colors"]["primary"])
            bordered_qr = Image.new('RGB', 
                                   (qr_size + 2*border_size, qr_size + 2*border_size),
                                   primary_color)
            bordered_qr.paste(qr_img, (border_size, border_size))
            
            self.card.paste(bordered_qr, (qr_x - border_size, qr_y - border_size))
            self.draw = ImageDraw.Draw(self.card)
            
            # Instructions text
            font_size = int(28 * (PRINT_DPI / SCREEN_DPI))
            font = load_custom_font(self.settings["fonts"]["body"], font_size)
            
            instructions = [
                "Scan this QR code to confirm your attendance",
                "or check in at the event"
            ]
            
            y_offset = qr_y + qr_size + int(30 * (PRINT_DPI / SCREEN_DPI))
            
            for instruction in instructions:
                text_bbox = self.draw.textbbox((0, 0), instruction, font=font)
                text_width = text_bbox[2] - text_bbox[0]
                x = (self.width - text_width) // 2
                self.draw.text((x, y_offset), instruction, font=font, fill=(100, 100, 100))
                y_offset += int(40 * (PRINT_DPI / SCREEN_DPI))
            
            logger.debug("QR code section drawn successfully")
            return y_offset + int(20 * (PRINT_DPI / SCREEN_DPI))
        except Exception as e:
            logger.error(f"Error drawing QR section: {e}")
            return start_y + int(450 * (PRINT_DPI / SCREEN_DPI))

    def add_decorative_elements(self):
        """Add decorative elements with smart placement to avoid text"""
        if not self.settings["decorations"]["show_decorations"]:
            return
        
        try:
            colors = [
                hex_to_rgb(self.settings["colors"]["primary"]),
                hex_to_rgb(self.settings["colors"]["secondary"]),
                hex_to_rgb(self.settings["colors"]["accent"]),
            ]
            
            # Define safe zones where decorations can go
            margin = self.margin + int(50 * (PRINT_DPI / SCREEN_DPI))
            safe_areas = [
                # Top corners
                {'x': (0, margin), 'y': (0, margin)},
                {'x': (self.width - margin, self.width), 'y': (0, margin)},
                # Bottom corners
                {'x': (0, margin), 'y': (self.height - margin, self.height)},
                {'x': (self.width - margin, self.width), 'y': (self.height - margin, self.height)},
            ]
            
            # Add small decorative elements in corners
            for area in safe_areas:
                for _ in range(random.randint(1, 3)):
                    shape_size = random.randint(int(20 * (PRINT_DPI / SCREEN_DPI)), 
                                               int(60 * (PRINT_DPI / SCREEN_DPI)))
                    shape_x = random.randint(area['x'][0], area['x'][1] - shape_size)
                    shape_y = random.randint(area['y'][0], area['y'][1] - shape_size)
                    color = random.choice(colors)
                    
                    shape_type = random.choice(['circle', 'star', 'diamond'])
                    
                    if shape_type == 'circle':
                        self.draw.ellipse(
                            [shape_x, shape_y, shape_x + shape_size, shape_y + shape_size],
                            fill=color,
                            outline=None
                        )
                    elif shape_type == 'diamond':
                        half = shape_size // 2
                        points = [
                            (shape_x + half, shape_y),
                            (shape_x + shape_size, shape_y + half),
                            (shape_x + half, shape_y + shape_size),
                            (shape_x, shape_y + half)
                        ]
                        self.draw.polygon(points, fill=color)
            
            logger.debug("Decorative elements added successfully")
        except Exception as e:
            logger.error(f"Error adding decorative elements: {e}")

    def add_footer(self, start_y):
        """Add footer with contact information"""
        try:
            font_size = int(22 * (PRINT_DPI / SCREEN_DPI))
            font = load_custom_font(self.settings["fonts"]["body"], font_size)
            
            footer_texts = [
                f"For inquiries, contact: {self.event.organizer.email}",
                "We look forward to celebrating with you!",
                f"Event ID: {self.event.id} | Guest ID: {self.guest.id}"
            ]
            
            y_offset = start_y
            footer_color = hex_to_rgb(self.settings["colors"]["secondary"])
            
            for text in footer_texts:
                text_bbox = self.draw.textbbox((0, 0), text, font=font)
                text_width = text_bbox[2] - text_bbox[0]
                x = (self.width - text_width) // 2
                self.draw.text((x, y_offset), text, font=font, fill=footer_color)
                y_offset += int(35 * (PRINT_DPI / SCREEN_DPI))
            
            logger.debug("Footer added successfully")
        except Exception as e:
            logger.error(f"Error adding footer: {e}")

    def generate(self):
        """Main method to generate the complete card with improved error handling"""
        try:
            logger.info(f"Starting card generation for {self.guest.full_name}")
            
            # Step 1: Create background
            self.create_background()
            
            # Step 2: Add border
            self.add_decorative_border()
            
            # Step 3: Draw sections in order
            current_y = self.draw_header()
            current_y = self.draw_guest_section(current_y)
            current_y = self.draw_invitation_message(current_y)
            current_y = self.draw_event_details_card(current_y)
            current_y = self.draw_qr_section(current_y)
            
            # Step 4: Add decorative elements
            self.add_decorative_elements()
            
            # Step 5: Add footer
            self.add_footer(current_y)
            
            logger.info(f"Card generated successfully for {self.guest.full_name}")
            return self.card
            
        except Exception as e:
            logger.error(f"Error in card generation: {str(e)}", exc_info=True)
            # Return a blank white card as fallback
            return Image.new('RGB', (self.width, self.height), (255, 255, 255))


# =========================
# PUBLIC FUNCTIONS
# =========================

def generate_invitation_card(guest: Guest):
    """Main function to generate and save invitation card"""
    try:
        logger.info(f"Generating invitation card for {guest.full_name}")
        
        generator = CardGenerator(guest)
        card_image = generator.generate()

        # Save card to BytesIO with high quality
        card_buffer = BytesIO()
        card_image.save(card_buffer, format='PNG', quality=95, optimize=False)
        card_buffer.seek(0)

        # Save to guest model
        filename = f"invitation_{guest.event.id}_{guest.id}_{guest.full_name.replace(' ', '_').replace('/', '_')}.png"
        guest.invitation_card.save(
            filename,
            File(card_buffer),
            save=False
        )

        # Generate separate QR code
        qr_data = guest.generate_qr_data()
        qr_img = generate_qr_code(
            qr_data,
            300,
            primary_color=guest.event.primary_color,
            bg_color="#FFFFFF"
        )
        
        qr_buffer = BytesIO()
        qr_img.save(qr_buffer, format='PNG', quality=95, optimize=False)
        qr_buffer.seek(0)
        
        guest.qr_code_image.save(
            f"qr_{guest.id}.png",
            File(qr_buffer),
            save=False
        )

        guest.save()
        logger.info(f"✅ Card generated successfully for: {guest.full_name}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error generating card for {guest.full_name}: {str(e)}", exc_info=True)
        return False


def generate_cards_for_event(event, guest_ids=None):
    """Generate cards for multiple guests with batch processing"""
    try:
        if guest_ids:
            guests = Guest.objects.filter(event=event, id__in=guest_ids)
        else:
            guests = Guest.objects.filter(event=event)
        
        total_guests = guests.count()
        logger.info(f"Starting batch generation for {total_guests} guests in event {event.title}")
        
        success_count = 0
        results = []
        
        for idx, guest in enumerate(guests, 1):
            try:
                logger.debug(f"Processing guest {idx}/{total_guests}: {guest.full_name}")
                if generate_invitation_card(guest):
                    success_count += 1
                    results.append({
                        'guest': guest.full_name,
                        'status': 'success',
                        'card_url': guest.invitation_card.url if guest.invitation_card else None
                    })
                else:
                    results.append({
                        'guest': guest.full_name,
                        'status': 'failed',
                        'error': 'Generation failed'
                    })
            except Exception as e:
                logger.error(f"Error processing guest {guest.full_name}: {e}")
                results.append({
                    'guest': guest.full_name,
                    'status': 'error',
                    'error': str(e)[:100]
                })
        
        summary = {
            'total': total_guests,
            'success': success_count,
            'failed': total_guests - success_count,
            'results': results
        }
        
        logger.info(f"Batch generation completed: {success_count}/{total_guests} successful")
        return summary
    except Exception as e:
        logger.error(f"Error in batch generation: {e}", exc_info=True)
        return {
            'total': 0,
            'success': 0,
            'failed': 0,
            'results': []
        }


def process_batch_guests(event, guests_data):
    """Process multiple guests from batch data"""
    created_guests = []
    
    for guest_data in guests_data:
        if not guest_data.get('email') or not guest_data.get('full_name'):
            continue
        
        guest, created = Guest.objects.get_or_create(
            event=event,
            email=guest_data['email'],
            defaults={
                'title': guest_data.get('title', 'Mr'),
                'full_name': guest_data['full_name'],
                'phone': guest_data.get('phone', ''),
                'notes': guest_data.get('notes', ''),
                'custom_message': guest_data.get('custom_message', ''),
                'seat_number': guest_data.get('seat_number', ''),
                'table_number': guest_data.get('table_number', ''),
            }
        )
        
        if not created:
            # Update existing guest
            for field in ['full_name', 'phone', 'notes', 'custom_message', 'seat_number', 'table_number']:
                if field in guest_data:
                    setattr(guest, field, guest_data[field])
            guest.save()
        
        # Generate invitation card
        generate_invitation_card(guest)
        
        if created:
            created_guests.append(guest)
    
    return created_guests


def export_guest_list(event, format='csv'):
    """Export guest list to CSV or Excel"""
    import csv
    from io import StringIO
    
    guests = event.guests.all()
    
    if format == 'csv':
        output = StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow([
            'Title', 'Full Name', 'Email', 'Phone', 
            'Seat Number', 'Table Number', 'Confirmed', 
            'Checked In', 'Invitation Sent'
        ])
        
        # Write data
        for guest in guests:
            writer.writerow([
                guest.title,
                guest.full_name,
                guest.email,
                guest.phone or '',
                guest.seat_number or '',
                guest.table_number or '',
                'Yes' if guest.confirmed else 'No',
                guest.checked_in_at.strftime('%Y-%m-%d %H:%M') if guest.checked_in_at else '',
                'Yes' if hasattr(guest, 'invitation_sent') and guest.invitation_sent else 'No'
            ])
        
        return output.getvalue()
    
    return None


# =========================
# UTILITY FUNCTIONS
# =========================

def test_card_generation(guest_id):
    """Test function for card generation with detailed reporting"""
    try:
        guest = Guest.objects.get(id=guest_id)
        logger.info(f"Testing card generation for: {guest.full_name}")
        logger.info(f"Event: {guest.event.title}")
        logger.info(f"Template: {guest.event.template_choice}")
        
        success = generate_invitation_card(guest)
        
        if success and guest.invitation_card:
            logger.info(f"✅ Card generated successfully!")
            logger.info(f"   Card saved to: {guest.invitation_card.path}")
            logger.info(f"   Card URL: {guest.invitation_card.url}")
            logger.info(f"   QR Code: {guest.qr_code_image.url if guest.qr_code_image else 'Not generated'}")
            
            # Display some stats
            try:
                img = Image.open(guest.invitation_card.path)
                logger.info(f"   Image size: {img.size[0]} x {img.size[1]} pixels")
                logger.info(f"   Image mode: {img.mode}")
                logger.info(f"   Image DPI: {img.info.get('dpi', 'Not set')}")
            except Exception as e:
                logger.warning(f"Could not read image info: {e}")
            
            return True
        else:
            logger.error("❌ Failed to generate card")
            return False
            
    except Guest.DoesNotExist:
        logger.error(f"❌ Guest with ID {guest_id} not found")
        return False
    except Exception as e:
        logger.error(f"❌ Error in test: {str(e)}", exc_info=True)
        return False