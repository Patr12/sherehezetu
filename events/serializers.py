from rest_framework import serializers
from .models import Event, Guest


class GuestSerializer(serializers.ModelSerializer):
    class Meta:
        model = Guest
        fields = [
            'id', 'event', 'title', 'full_name', 'email', 'phone',
            'qr_code', 'qr_code_image', 'invitation_card',
            'confirmed', 'checked_in_at', 'created_at'
        ]
        read_only_fields = [
            'qr_code', 'qr_code_image',
            'invitation_card', 'confirmed',
            'checked_in_at', 'created_at'
        ]


class EventSerializer(serializers.ModelSerializer):
    guests = GuestSerializer(many=True, read_only=True)

    class Meta:
        model = Event
        fields = [
            'id', 'title', 'description',
            'date', 'venue',
            'template_svg',
            'theme_color', 'background_color', 'text_color',
            'created_at', 'guests'
        ]
