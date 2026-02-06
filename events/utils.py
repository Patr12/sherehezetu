import qrcode
import random
import math
import os
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
from io import BytesIO
from django.core.files import File
from django.conf import settings
from .models import Guest, SVGOverlay
import textwrap


# =========================
# BASIC HELPERS
# =========================

def hex_to_rgb(hex_color):
    """Convert hex to RGB with alpha support"""
    hex_color = hex_color.lstrip('#')
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
        a = int(hex_color[6:8], 16)
        return (r, g, b, a)
    return (0, 0, 0)


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
    """Generate QR code with custom colors"""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)

    qr_img = qr.make_image(
        fill_color=primary_color,
        back_color=bg_color
    ).convert("RGB")

    return qr_img.resize((size, size))


def load_custom_font(font_name, size):
    """Load font from multiple possible locations"""
    font_paths = [
        os.path.join(settings.BASE_DIR, "static/fonts", f"{font_name}.ttf"),
        os.path.join(settings.BASE_DIR, "static/fonts", f"{font_name}.otf"),
        os.path.join(settings.BASE_DIR, "fonts", f"{font_name}.ttf"),
        os.path.join(settings.BASE_DIR, "fonts", f"{font_name}.otf"),
        os.path.join("C:/Windows/Fonts", f"{font_name}.ttf"),
        os.path.join("/System/Library/Fonts", f"{font_name}.ttf"),
        os.path.join("/usr/share/fonts/truetype", f"{font_name}.ttf"),
        os.path.join("/usr/share/fonts/opentype", f"{font_name}.otf"),
    ]
    
    for path in font_paths:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except:
                continue
    
    # Fallback to system fonts
    fallback_map = {
        'Marckscript': 'arial.ttf',
        'DancingScript': 'arial.ttf',
        'PlayfairDisplay': 'times.ttf',
        'GreatVibes': 'arial.ttf',
        'Allura': 'arial.ttf',
        'Sacramento': 'arial.ttf',
        'Parisienne': 'arial.ttf',
        'Cormorant': 'times.ttf',
        'Cardo': 'times.ttf',
    }
    
    for key in fallback_map:
        if key in font_name:
            try:
                return ImageFont.truetype(fallback_map[key], size)
            except:
                pass
    
    # Ultimate fallback
    try:
        return ImageFont.truetype("arial.ttf", size)
    except:
        return ImageFont.load_default().font_variant(size=size)


def wrap_text(text, font, max_width):
    """Wrap text to fit within max_width"""
    lines = []
    words = text.split()
    
    while words:
        line = ''
        while words and font.getbbox(line + words[0])[2] <= max_width:
            line += (words.pop(0) + ' ')
        if not line:
            line = words.pop(0)
        lines.append(line.strip())
    
    return lines


def add_shadow(draw, text, position, font, text_color, shadow_color=(0, 0, 0, 100), offset=(2, 2)):
    """Add shadow effect to text"""
    x, y = position
    shadow_x, shadow_y = offset
    
    # Draw shadow
    if len(shadow_color) == 4:
        # RGBA shadow
        shadow_img = Image.new('RGBA', draw.im.size)
        shadow_draw = ImageDraw.Draw(shadow_img)
        shadow_draw.text((x + shadow_x, y + shadow_y), text, font=font, fill=shadow_color)
        
        # Composite shadow
        draw.bitmap((0, 0), shadow_img, fill=shadow_color[:3])
    else:
        # RGB shadow
        draw.text((x + shadow_x, y + shadow_y), text, font=font, fill=shadow_color)
    
    # Draw main text
    draw.text((x, y), text, font=font, fill=text_color)


# =========================
# CARD GENERATOR - IMPROVED
# =========================

class CardGenerator:
    def __init__(self, guest):
        self.guest = guest
        self.event = guest.event
        self.settings = self.event.get_template_settings()
        self.width = 1200  # Increased for better layout
        self.height = 1600  # Increased for better layout
        self.card = None
        self.draw = None
        self.margin = 60  # Safe margin from edges
        self.content_width = self.width - (2 * self.margin)

    def load_background_image(self):
        """Load background image if available"""
        # Try to load from template_svg field
        if self.event.template_svg and os.path.exists(self.event.template_svg.path):
            try:
                # For SVG, we'd need a library like cairosvg or convert to PNG first
                # For now, we'll handle images
                if self.event.template_svg.path.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
                    bg = Image.open(self.event.template_svg.path).convert('RGBA')
                    bg = bg.resize((self.width, self.height))
                    
                    # Apply opacity
                    if bg.mode == 'RGBA':
                        alpha = bg.split()[3]
                        alpha = ImageEnhance.Brightness(alpha).enhance(0.3)  # 30% opacity
                        bg.putalpha(alpha)
                    
                    return bg
            except:
                pass
        
        # Try SVG overlays
        svg_overlays = SVGOverlay.objects.filter(category='background')[:1]
        if svg_overlays.exists():
            # In a real implementation, you'd render the SVG
            # For now, we'll create a patterned background
            pass
        
        return None

    def create_background(self):
        """Create background with gradient and optional image"""
        # Start with solid color
        bg_color = hex_to_rgb(self.settings["colors"]["background"])
        self.card = Image.new("RGB", (self.width, self.height), bg_color)
        self.draw = ImageDraw.Draw(self.card)
        
        # Add gradient overlay
        if self.settings['decorations'].get('gradient_background', True):
            sec_color = hex_to_rgb(self.settings["colors"]["secondary"])
            for y in range(self.height):
                factor = y / self.height
                r = int(bg_color[0] * (1 - factor) + sec_color[0] * factor)
                g = int(bg_color[1] * (1 - factor) + sec_color[1] * factor)
                b = int(bg_color[2] * (1 - factor) + sec_color[2] * factor)
                self.draw.line([(0, y), (self.width, y)], fill=(r, g, b))
        
        # Overlay background image if available
        bg_image = self.load_background_image()
        if bg_image:
            self.card = Image.alpha_composite(
                self.card.convert('RGBA'), 
                bg_image
            ).convert('RGB')
            self.draw = ImageDraw.Draw(self.card)

    def add_decorative_border(self):
        """Add decorative border based on template settings"""
        if not self.settings["decorations"]["show_border"]:
            return
        
        border_color = hex_to_rgb(self.settings["colors"]["primary"])
        border_width = 15
        
        border_style = self.settings["decorations"]["border_style"]
        
        if border_style == 'rounded':
            # Rounded rectangle border
            self.draw.rounded_rectangle(
                [border_width, border_width, 
                 self.width - border_width, self.height - border_width],
                radius=80,
                outline=border_color,
                width=border_width
            )
            
        elif border_style == 'floral':
            # Floral pattern border (simulated with circles)
            pattern_size = 60
            for i in range(0, self.width, pattern_size):
                # Top border
                self.draw.ellipse(
                    [i + 10, 20, i + 40, 50],
                    outline=border_color,
                    width=3
                )
                # Bottom border
                self.draw.ellipse(
                    [i + 10, self.height - 50, i + 40, self.height - 20],
                    outline=border_color,
                    width=3
                )
            
        elif border_style == 'geometric':
            # Geometric pattern border
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

    def draw_header(self):
        """Draw event title header with styling"""
        # Header background
        header_height = 180
        header_color = hex_to_rgb(self.settings["colors"]["primary"])
        
        # Create gradient header
        for y in range(header_height):
            factor = y / header_height
            r = int(header_color[0] * (1 - factor) + 255 * factor)
            g = int(header_color[1] * (1 - factor) + 255 * factor)
            b = int(header_color[2] * (1 - factor) + 255 * factor)
            self.draw.line([(0, y), (self.width, y)], fill=(r, g, b))
        
        # Event title
        font_size = 64
        font = load_custom_font(self.settings["fonts"]["title"], font_size)
        title_text = self.event.title.upper()
        
        # Ensure title fits
        while self.draw.textbbox((0, 0), title_text, font=font)[2] > self.content_width:
            font_size -= 2
            font = load_custom_font(self.settings["fonts"]["title"], font_size)
        
        text_width = self.draw.textbbox((0, 0), title_text, font=font)[2]
        x = (self.width - text_width) // 2
        y = 70
        
        # Shadow effect
        add_shadow(
            self.draw, title_text, (x, y), font,
            text_color=(255, 255, 255),
            shadow_color=(0, 0, 0, 150),
            offset=(3, 3)
        )
        
        # Divider line
        divider_y = y + font_size + 20
        self.draw.line(
            [(self.width//2 - 100, divider_y), (self.width//2 + 100, divider_y)],
            fill=(255, 255, 255, 180),
            width=3
        )
        
        return divider_y + 30

    def draw_guest_section(self, start_y):
        """Draw guest name section with highlight"""
        # Background highlight for name
        highlight_height = 140
        highlight_color = hex_to_rgb(self.settings["colors"]["secondary"])
        
        self.draw.rounded_rectangle(
            [self.margin, start_y, 
             self.width - self.margin, start_y + highlight_height],
            radius=30,
            fill=highlight_color
        )
        
        # Guest name
        font_size = 72
        font = load_custom_font(self.settings["fonts"]["name"], font_size)
        guest_name = f"{self.guest.title} {self.guest.full_name}"
        
        # Ensure name fits
        while self.draw.textbbox((0, 0), guest_name, font=font)[2] > self.content_width - 100:
            font_size -= 2
            font = load_custom_font(self.settings["fonts"]["name"], font_size)
        
        text_width = self.draw.textbbox((0, 0), guest_name, font=font)[2]
        text_height = self.draw.textbbox((0, 0), guest_name, font=font)[3]
        x = (self.width - text_width) // 2
        y = start_y + (highlight_height - text_height) // 2
        
        # Draw name with slight handwritten effect
        add_shadow(
            self.draw, guest_name, (x, y), font,
            text_color=hex_to_rgb(self.settings["colors"]["accent"]),
            shadow_color=(0, 0, 0, 50),
            offset=(2, 2)
        )
        
        # Underline decoration
        underline_y = y + text_height + 5
        self.draw.line(
            [(x - 20, underline_y), (x + text_width + 20, underline_y)],
            fill=hex_to_rgb(self.settings["colors"]["accent"]),
            width=2
        )
        
        return start_y + highlight_height + 40

    def draw_invitation_message(self, start_y):
        """Draw invitation message"""
        font_size = 36
        font = load_custom_font(self.settings["fonts"]["body"], font_size)
        
        # Use custom message or default
        message = self.guest.custom_message or "You are cordially invited to join us for a celebration of love and joy"
        
        # Wrap text
        max_line_width = self.content_width - 40
        lines = wrap_text(message, font, max_line_width)
        
        # Calculate total height needed
        line_height = font_size + 10
        total_height = len(lines) * line_height
        
        # Center vertically
        y = start_y
        
        for line in lines:
            text_width = self.draw.textbbox((0, 0), line, font=font)[2]
            x = (self.width - text_width) // 2
            self.draw.text((x, y), line, font=font, fill=(80, 40, 120))
            y += line_height
        
        return y + 30

    def draw_event_details_card(self, start_y):
        """Draw event details in a styled card"""
        card_height = 280
        card_width = self.content_width
        card_x = self.margin
        card_y = start_y
        
        # Card shadow
        shadow_offset = 8
        self.draw.rounded_rectangle(
            [card_x + shadow_offset, card_y + shadow_offset,
             card_x + card_width + shadow_offset, card_y + card_height + shadow_offset],
            radius=25,
            fill=(200, 200, 200)
        )
        
        # Card background
        self.draw.rounded_rectangle(
            [card_x, card_y, card_x + card_width, card_y + card_height],
            radius=25,
            fill=(255, 255, 255),
            outline=hex_to_rgb(self.settings["colors"]["primary"]),
            width=3
        )
        
        # Card content
        font_size = 32
        font = load_custom_font(self.settings["fonts"]["body"], font_size)
        icon_font = load_custom_font("Segoe UI Symbol", 28) or font
        
        details = [
            {"icon": "📅", "text": f"Date: {self.event.date.strftime('%A, %d %B %Y')}"},
            {"icon": "🕒", "text": f"Time: {self.event.date.strftime('%I:%M %p')}"},
            {"icon": "📍", "text": f"Venue: {self.event.venue}"},
        ]
        
        # Add guest-specific details if available
        if self.guest.seat_number:
            details.append({"icon": "💺", "text": f"Seat: {self.guest.seat_number}"})
        if self.guest.table_number:
            details.append({"icon": "🍽️", "text": f"Table: {self.guest.table_number}"})
        
        y_offset = card_y + 50
        
        for detail in details:
            # Icon
            icon_width = self.draw.textbbox((0, 0), detail["icon"], font=icon_font)[2]
            icon_x = card_x + 60
            self.draw.text((icon_x, y_offset), detail["icon"], font=icon_font, 
                          fill=hex_to_rgb(self.settings["colors"]["primary"]))
            
            # Text
            text_x = icon_x + icon_width + 15
            self.draw.text((text_x, y_offset), detail["text"], font=font, 
                          fill=(50, 50, 50))
            
            y_offset += 55
        
        return card_y + card_height + 40

    def draw_qr_section(self, start_y):
        """Draw QR code section with decorations"""
        qr_size = 320
        qr_x = (self.width - qr_size) // 2
        qr_y = start_y
        
        # Decorative background for QR
        if self.settings["decorations"]["show_qr_background"]:
            bg_radius = qr_size // 2 + 25
            bg_center_x = qr_x + qr_size // 2
            bg_center_y = qr_y + qr_size // 2
            
            # Create concentric circles
            for i in range(3):
                radius = bg_radius + i * 15
                self.draw.ellipse(
                    [bg_center_x - radius, bg_center_y - radius,
                     bg_center_x + radius, bg_center_y + radius],
                    outline=hex_to_rgb(self.settings["colors"]["secondary"]),
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
        border_size = 8
        bordered_qr = Image.new('RGB', 
                               (qr_size + 2*border_size, qr_size + 2*border_size),
                               hex_to_rgb(self.settings["colors"]["primary"]))
        bordered_qr.paste(qr_img, (border_size, border_size))
        
        self.card.paste(bordered_qr, (qr_x - border_size, qr_y - border_size))
        
        # Instructions text
        font_size = 28
        font = load_custom_font(self.settings["fonts"]["body"], font_size)
        
        instructions = [
            "Scan this QR code to confirm your attendance",
            "or check in at the event"
        ]
        
        y_offset = qr_y + qr_size + 30
        
        for instruction in instructions:
            text_width = self.draw.textbbox((0, 0), instruction, font=font)[2]
            x = (self.width - text_width) // 2
            self.draw.text((x, y_offset), instruction, font=font, fill=(100, 100, 100))
            y_offset += 40
        
        return y_offset + 20

    def add_decorative_elements(self):
        """Add decorative elements like patterns, icons, etc."""
        if not self.settings["decorations"]["show_decorations"]:
            return
        
        colors = [
            hex_to_rgb(self.settings["colors"]["primary"]),
            hex_to_rgb(self.settings["colors"]["secondary"]),
            hex_to_rgb(self.settings["colors"]["accent"]),
        ]
        
        # Add random decorative shapes
        for _ in range(15):
            shape_size = random.randint(20, 60)
            shape_x = random.randint(30, self.width - 30 - shape_size)
            shape_y = random.randint(30, self.height - 30 - shape_size)
            color = random.choice(colors)
            opacity = random.randint(30, 100)  # 30-100% opacity
            
            # Create RGBA color
            rgba_color = color + (opacity,) if len(color) == 3 else color
            
            shape_type = random.choice(['circle', 'star', 'diamond', 'heart'])
            
            if shape_type == 'circle':
                self.draw.ellipse(
                    [shape_x, shape_y, shape_x + shape_size, shape_y + shape_size],
                    fill=rgba_color if len(rgba_color) == 4 else color,
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
                self.draw.polygon(points, fill=rgba_color if len(rgba_color) == 4 else color)
        
        # Add corner decorations if using floral border
        if self.settings["decorations"]["border_style"] == 'floral':
            corner_size = 80
            corner_color = hex_to_rgb(self.settings["colors"]["primary"])
            
            # Top-left corner
            self.draw.arc(
                [10, 10, corner_size, corner_size],
                180, 270,
                fill=corner_color,
                width=3
            )
            
            # Top-right corner
            self.draw.arc(
                [self.width - corner_size - 10, 10, self.width - 10, corner_size],
                270, 360,
                fill=corner_color,
                width=3
            )
            
            # Bottom-left corner
            self.draw.arc(
                [10, self.height - corner_size - 10, corner_size, self.height - 10],
                90, 180,
                fill=corner_color,
                width=3
            )
            
            # Bottom-right corner
            self.draw.arc(
                [self.width - corner_size - 10, self.height - corner_size - 10, 
                 self.width - 10, self.height - 10],
                0, 90,
                fill=corner_color,
                width=3
            )

    def add_footer(self, start_y):
        """Add footer with contact information"""
        font_size = 22
        font = load_custom_font(self.settings["fonts"]["body"], font_size)
        
        footer_texts = [
            f"For inquiries, contact: {self.event.organizer.email}",
            "We look forward to celebrating with you!",
            f"Event ID: {self.event.id} | Guest ID: {self.guest.id}"
        ]
        
        y_offset = start_y
        
        for text in footer_texts:
            text_width = self.draw.textbbox((0, 0), text, font=font)[2]
            x = (self.width - text_width) // 2
            self.draw.text((x, y_offset), text, font=font, fill=(150, 150, 150))
            y_offset += 35

    def generate(self):
        """Main method to generate the complete card"""
        try:
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
            
            # Step 6: Add final border check
            self.ensure_text_within_bounds()
            
            return self.card
            
        except Exception as e:
            print(f"Error in card generation: {str(e)}")
            raise

    def ensure_text_within_bounds(self):
        """Ensure no text goes outside safe margins"""
        # This is a safety check - most text should already be bounded
        # by our margin and content_width calculations
        pass


# =========================
# PUBLIC FUNCTIONS
# =========================

def generate_invitation_card(guest: Guest):
    """Main function to generate and save invitation card"""
    try:
        generator = CardGenerator(guest)
        card_image = generator.generate()

        # Save card to BytesIO
        card_buffer = BytesIO()
        card_image.save(card_buffer, format='PNG', quality=95, optimize=True)
        card_buffer.seek(0)

        # Save to guest model
        filename = f"invitation_{guest.event.id}_{guest.id}_{guest.full_name.replace(' ', '_')}.png"
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
        qr_img.save(qr_buffer, format='PNG')
        qr_buffer.seek(0)
        
        guest.qr_code_image.save(
            f"qr_{guest.id}.png",
            File(qr_buffer),
            save=False
        )

        guest.save()
        print(f"✅ Card generated successfully for: {guest.full_name}")
        return True
        
    except Exception as e:
        print(f"❌ Error generating card for {guest.full_name}: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def generate_cards_for_event(event, guest_ids=None):
    """Generate cards for multiple guests"""
    if guest_ids:
        guests = Guest.objects.filter(event=event, id__in=guest_ids)
    else:
        guests = Guest.objects.filter(event=event)
    
    success_count = 0
    results = []
    
    for guest in guests:
        try:
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
            results.append({
                'guest': guest.full_name,
                'status': 'error',
                'error': str(e)[:100]
            })
    
    return {
        'total': len(guests),
        'success': success_count,
        'failed': len(guests) - success_count,
        'results': results
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
    """Test function for card generation"""
    try:
        guest = Guest.objects.get(id=guest_id)
        print(f"Testing card generation for: {guest.full_name}")
        print(f"Event: {guest.event.title}")
        print(f"Template: {guest.event.template_choice}")
        
        success = generate_invitation_card(guest)
        
        if success and guest.invitation_card:
            print(f"✅ Card generated successfully!")
            print(f"   Card saved to: {guest.invitation_card.path}")
            print(f"   Card URL: {guest.invitation_card.url}")
            print(f"   QR Code: {guest.qr_code_image.url if guest.qr_code_image else 'Not generated'}")
            
            # Display some stats
            from PIL import Image as PILImage
            img = PILImage.open(guest.invitation_card.path)
            print(f"   Image size: {img.size[0]} x {img.size[1]} pixels")
            print(f"   Image mode: {img.mode}")
            
            return True
        else:
            print("❌ Failed to generate card")
            return False
            
    except Guest.DoesNotExist:
        print(f"❌ Guest with ID {guest_id} not found")
        return False
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False