from django import forms
from django.core.exceptions import ValidationError
from .models import Event, Guest, SVGOverlay
import pandas as pd
from io import StringIO
from django import forms
from .models import Event, Guest, TemplateDesign


class EventForm(forms.ModelForm):
    class Meta:
        model = Event
        fields = '__all__'
        widgets = {
            'date': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'primary_color': forms.TextInput(attrs={'type': 'color'}),
            'secondary_color': forms.TextInput(attrs={'type': 'color'}),
            'accent_color': forms.TextInput(attrs={'type': 'color'}),
            'background_color': forms.TextInput(attrs={'type': 'color'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add template preview option
        self.fields['template_choice'].widget.attrs.update({
            'class': 'template-selector',
            'onchange': 'previewTemplate(this.value)'
        })


class GuestForm(forms.ModelForm):
    class Meta:
        model = Guest
        exclude = ('qr_code', 'qr_code_image', 'invitation_card', 'confirmed_at')
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Customize form styling
        for field in self.fields:
            self.fields[field].widget.attrs.update({
                'class': 'form-control'
            })

class BatchGuestForm(forms.Form):
    event = forms.ModelChoiceField(queryset=Event.objects.none())
    input_method = forms.ChoiceField(choices=[
        ('manual', 'Manual Entry'),
        ('csv', 'Upload CSV'),
        ('excel', 'Upload Excel'),
        ('text', 'Paste Text')
    ], initial='manual')
    
    # For manual entry
    guest_data = forms.CharField(
        widget=forms.Textarea(attrs={
            'rows': 10,
            'placeholder': 'Format:\ntitle,full_name,email,phone\nMr,John Doe,john@example.com,0712345678\nMrs,Jane Smith,jane@example.com,0723456789'
        }),
        required=False
    )
    
    # For file upload
    guest_file = forms.FileField(required=False)
    
    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['event'].queryset = Event.objects.filter(organizer=user)
    
    def clean(self):
        cleaned_data = super().clean()
        input_method = cleaned_data.get('input_method')
        
        guests = []
        
        if input_method == 'manual':
            data = cleaned_data.get('guest_data', '')
            if data:
                lines = data.strip().split('\n')
                headers = None
                
                for i, line in enumerate(lines):
                    parts = [part.strip() for part in line.split(',')]
                    
                    if i == 0 and len(parts) >= 3:
                        # Check if first line is headers
                        if parts[0].lower() in ['title', 'name', 'email']:
                            headers = parts
                            continue
                    
                    if len(parts) >= 3:
                        guest = {
                            'title': parts[0] if len(parts) > 0 else 'Mr',
                            'full_name': parts[1] if len(parts) > 1 else '',
                            'email': parts[2] if len(parts) > 2 else '',
                            'phone': parts[3] if len(parts) > 3 else ''
                        }
                        guests.append(guest)
        
        elif input_method in ['csv', 'excel']:
            file = cleaned_data.get('guest_file')
            if file:
                try:
                    if input_method == 'csv':
                        df = pd.read_csv(StringIO(file.read().decode('utf-8')))
                    else:  # excel
                        df = pd.read_excel(file)
                    
                    # Convert to list of dicts
                    guests = df.to_dict('records')
                    
                except Exception as e:
                    raise ValidationError(f'Error reading file: {str(e)}')
        
        cleaned_data['parsed_guests'] = guests
        return cleaned_data

class SVGOverlayForm(forms.ModelForm):
    class Meta:
        model = SVGOverlay
        fields = ['name', 'svg_file', 'position_x', 'position_y', 'size']