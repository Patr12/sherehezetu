from django.contrib import admin

# Register your models here.
from django.contrib import admin
from .models import Event, Guest, InvitationHistory, SVGOverlay

# Inline guest display inside Event admin
class GuestInline(admin.TabularInline):
    model = Guest
    extra = 1  # How many empty guest forms to show
    readonly_fields = ('qr_code', 'qr_code_image', 'invitation_card', 'checked_in_at')
    fields = ('title', 'full_name', 'email', 'phone', 'confirmed', 'notes', 'qr_code', 'qr_code_image', 'invitation_card', 'checked_in_at')

from django.contrib import admin
from .models import Event, Guest, TemplateDesign, SVGOverlay
from .utils import generate_cards_for_event, generate_invitation_card


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ('title', 'organizer', 'date', 'venue', 'template_choice')
    list_filter = ('template_choice', 'date')
    search_fields = ('title', 'venue', 'description')
    fieldsets = (
        ('Event Information', {
            'fields': ('title', 'description', 'date', 'venue')
        }),
        ('Design & Template', {
            'fields': ('template_choice', 'template_svg', 
                      'primary_color', 'secondary_color', 
                      'accent_color', 'background_color',
                      'title_font', 'name_font', 'body_font')
        }),
        ('Decoration Settings', {
            'fields': ('show_border', 'border_style', 
                      'show_qr_background', 'show_decorations')
        }),
    )
    
    actions = ['generate_all_cards']
    
    def generate_all_cards(self, request, queryset):
        """Admin action to generate cards for selected events"""
        for event in queryset:
            result = generate_cards_for_event(event)
            self.message_user(
                request,
                f"Generated {result['success']} cards for {event.title} ({result['failed']} failed)"
            )
    generate_all_cards.short_description = "Generate invitation cards"


@admin.register(Guest)
class GuestAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'event', 'email', 'confirmed', 'checked_in_at')
    list_filter = ('event', 'confirmed', 'checked_in_at')
    search_fields = ('full_name', 'email', 'phone')
    actions = ['generate_selected_cards', 'mark_as_confirmed']
    
    def generate_selected_cards(self, request, queryset):
        """Generate cards for selected guests"""
        success_count = 0
        for guest in queryset:
            if generate_invitation_card(guest):
                success_count += 1
        
        self.message_user(
            request,
            f"Successfully generated {success_count} cards out of {queryset.count()}"
        )
    generate_selected_cards.short_description = "Generate invitation cards"
    
    def mark_as_confirmed(self, request, queryset):
        """Mark selected guests as confirmed"""
        updated = queryset.update(confirmed=True)
        self.message_user(request, f"Marked {updated} guests as confirmed")
    mark_as_confirmed.short_description = "Mark as confirmed"


@admin.register(TemplateDesign)
class TemplateDesignAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'is_active')
    list_filter = ('category', 'is_active')
    search_fields = ('name', 'category')


@admin.register(SVGOverlay)
class SVGOverlayAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'size')
    list_filter = ('category',)

@admin.register(InvitationHistory)
class InvitationHistoryAdmin(admin.ModelAdmin):
    list_display = ('guest', 'sent_via', 'sent_at', 'sent_by', 'status')
    list_filter = ('sent_via', 'status', 'sent_by')
    search_fields = ('guest__full_name', 'message')
