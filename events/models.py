from django.db import models
from django.conf import settings
import uuid

class Event(models.Model):
    organizer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    date = models.DateTimeField()
    venue = models.CharField(max_length=200)
    
    # TEMPLATE FIELDS - MPYA
    template_choice = models.CharField(
        max_length=50,
        choices=[
            ('modern', 'Modern Elegant'),
            ('classic', 'Classic Formal'),
            ('floral', 'Floral Design'),
            ('minimal', 'Minimalist'),
            ('custom', 'Custom Template')
        ],
        default='modern'
    )
    template_svg = models.FileField(upload_to='event_templates/', null=True, blank=True)
    
    # COLOR THEME - MPYA
    primary_color = models.CharField(max_length=50, default='#7C3AED')  # Purple
    secondary_color = models.CharField(max_length=50, default='#F0E6FF')  # Light Purple
    accent_color = models.CharField(max_length=50, default='#852D63')  # Maroon
    background_color = models.CharField(max_length=50, default='#FDF4FF')  # Off-white
    
    # FONT SETTINGS - MPYA
    title_font = models.CharField(max_length=100, default='Marckscript-Regular')
    name_font = models.CharField(max_length=100, default='DancingScript-Bold')
    body_font = models.CharField(max_length=100, default='PlayfairDisplay-Regular')
    
    # DECORATION SETTINGS - MPYA
    show_border = models.BooleanField(default=True)
    border_style = models.CharField(
        max_length=50,
        choices=[
            ('simple', 'Simple Line'),
            ('rounded', 'Rounded Corners'),
            ('floral', 'Floral Pattern'),
            ('geometric', 'Geometric')
        ],
        default='rounded'
    )
    show_qr_background = models.BooleanField(default=True)
    show_decorations = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title
    
    def get_template_settings(self):
        """Return template configuration as dict"""
        return {
            'template': self.template_choice,
            'colors': {
                'primary': self.primary_color,
                'secondary': self.secondary_color,
                'accent': self.accent_color,
                'background': self.background_color
            },
            'fonts': {
                'title': self.title_font,
                'name': self.name_font,
                'body': self.body_font
            },
            'decorations': {
                'show_border': self.show_border,
                'border_style': self.border_style,
                'show_qr_background': self.show_qr_background,
                'show_decorations': self.show_decorations
            }
        }


class Guest(models.Model):
    TITLE_CHOICES = [
        ('Mr', 'Mr'),
        ('Mrs', 'Mrs'),
        ('Miss', 'Miss'),
        ('Ms', 'Ms'),
        ('Dr', 'Dr'),
        ('Prof', 'Prof')
    ]

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='guests')
    title = models.CharField(max_length=10, choices=TITLE_CHOICES, default='Mr')
    full_name = models.CharField(max_length=200)
    email = models.EmailField()
    phone = models.CharField(max_length=20, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    
    # QR CODE & INVITATION
    qr_code = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    qr_code_image = models.ImageField(upload_to='guest_qr_codes/', null=True, blank=True)
    invitation_card = models.ImageField(upload_to='invitation_cards/', null=True, blank=True)
    
    # RSVP STATUS
    confirmed = models.BooleanField(default=False)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    checked_in_at = models.DateTimeField(null=True, blank=True)
    
    # ADDITIONAL CUSTOMIZATION PER GUEST
    custom_message = models.TextField(blank=True, null=True)
    seat_number = models.CharField(max_length=20, blank=True, null=True)
    table_number = models.CharField(max_length=10, blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['event', 'email']
        ordering = ['full_name']
    
    def __str__(self):
        return f"{self.full_name} - {self.event.title}"
    
    def save(self, *args, **kwargs):
        if not self.qr_code:
            self.qr_code = str(uuid.uuid4())
        super().save(*args, **kwargs)
    
    def generate_qr_data(self):
        """Generate QR code data string"""
        return f"EVENT:{self.event.id}|GUEST:{self.id}|CODE:{self.qr_code}"


class TemplateDesign(models.Model):
    """Pre-designed templates for invitations"""
    name = models.CharField(max_length=100)
    category = models.CharField(
        max_length=50,
        choices=[
            ('wedding', 'Wedding'),
            ('corporate', 'Corporate'),
            ('birthday', 'Birthday'),
            ('graduation', 'Graduation'),
            ('generic', 'Generic')
        ]
    )
    
    # Design elements
    preview_image = models.ImageField(upload_to='template_previews/')
    background_image = models.ImageField(upload_to='template_backgrounds/', null=True, blank=True)
    svg_overlay = models.FileField(upload_to='template_svgs/', null=True, blank=True)
    
    # Default settings
    default_primary_color = models.CharField(max_length=50, default='#7C3AED')
    default_secondary_color = models.CharField(max_length=50, default='#F0E6FF')
    default_font_family = models.CharField(max_length=100, default='PlayfairDisplay')
    default_layout = models.JSONField(default=dict)  # Layout positions
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.name} ({self.category})"


class SVGOverlay(models.Model):
    name = models.CharField(max_length=100)
    svg_file = models.FileField(upload_to='svg_overlays/')
    category = models.CharField(
        max_length=50,
        choices=[
            ('border', 'Border'),
            ('corner', 'Corner Design'),
            ('pattern', 'Pattern'),
            ('icon', 'Icon'),
            ('floral', 'Floral Design')
        ], null=True, blank= True
    )
    position_x = models.IntegerField(default=0)
    position_y = models.IntegerField(default=0)
    size = models.IntegerField(default=100)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.name


class InvitationHistory(models.Model):
    guest = models.ForeignKey(Guest, on_delete=models.CASCADE, related_name='invitation_history')
    sent_via = models.CharField(max_length=50, choices=[
        ('email', 'Email'),
        ('whatsapp', 'WhatsApp'),
        ('sms', 'SMS'),
        ('manual', 'Manual')
    ])
    sent_at = models.DateTimeField(auto_now_add=True)
    sent_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    message = models.TextField(blank=True)
    status = models.CharField(max_length=50, default='sent')
    
    class Meta:
        ordering = ['-sent_at']
    
    def __str__(self):
        return f"{self.guest.full_name} - {self.sent_via}"
