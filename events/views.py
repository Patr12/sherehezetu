from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from django.utils import timezone
from django.shortcuts import get_object_or_404

from .models import Event, Guest
from .serializers import EventSerializer, GuestSerializer
from .utils import process_batch_guests, export_guest_list
from .tasks import send_invitation_email, send_whatsapp_invitation, batch_send_invitations


# ======================
# API: EVENT VIEWSET
# ======================

class EventViewSet(viewsets.ModelViewSet):
    """API ViewSet for Events"""
    serializer_class = EventSerializer
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        """Return events for authenticated user"""
        return Event.objects.filter(organizer=self.request.user)

    def perform_create(self, serializer):
        """Set organizer when creating event"""
        serializer.save(organizer=self.request.user)

    @action(detail=True, methods=['post'])
    def add_guests_batch(self, request, pk=None):
        """Add multiple guests to an event"""
        event = self.get_object()
        guests_data = request.data.get('guests', [])

        if not guests_data:
            return Response(
                {"error": "No guest data provided"}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        created_guests = process_batch_guests(event, guests_data)

        return Response({
            "message": f"{len(created_guests)} guests added successfully",
            "guests": GuestSerializer(created_guests, many=True).data
        })

    @action(detail=True, methods=['post'])
    def send_invitations(self, request, pk=None):
        """Send invitations for an event"""
        event = self.get_object()
        via = request.data.get('via', 'email')
        message = request.data.get('message', '')

        # Start background task
        batch_send_invitations.delay(event.id, via, message)

        return Response({
            "message": f"Invitations are being sent via {via}",
            "event_id": event.id,
            "total_guests": event.guests.count()
        })

    @action(detail=True, methods=['get'])
    def export_guests(self, request, pk=None):
        """Export guests to CSV"""
        event = self.get_object()
        csv_data = export_guest_list(event, 'csv')

        response = Response(csv_data)
        response['Content-Type'] = 'text/csv'
        response['Content-Disposition'] = f'attachment; filename="guests_{event.id}.csv"'
        return response

    @action(detail=True, methods=['get'])
    def statistics(self, request, pk=None):
        """Get event statistics"""
        event = self.get_object()
        
        total_guests = event.guests.count()
        confirmed_guests = event.guests.filter(confirmed=True).count()
        checked_in_guests = event.guests.filter(checked_in_at__isnull=False).count()
        
        return Response({
            "event_id": event.id,
            "event_title": event.title,
            "statistics": {
                "total_guests": total_guests,
                "confirmed_guests": confirmed_guests,
                "checked_in_guests": checked_in_guests,
                "confirmation_rate": (confirmed_guests / total_guests * 100) if total_guests > 0 else 0,
                "check_in_rate": (checked_in_guests / total_guests * 100) if total_guests > 0 else 0
            }
        })


# ======================
# API: GUEST VIEWSET
# ======================

class GuestViewSet(viewsets.ModelViewSet):
    """API ViewSet for Guests"""
    serializer_class = GuestSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Return guests for authenticated user's events"""
        return Guest.objects.filter(event__organizer=self.request.user)

    @action(detail=True, methods=['post'])
    def resend_invitation(self, request, pk=None):
        """Resend invitation to guest"""
        guest = self.get_object()
        via = request.data.get('via', 'email')

        if via == 'email':
            send_invitation_email.delay(guest.id)
        elif via == 'whatsapp':
            send_whatsapp_invitation.delay(guest.id)
        else:
            return Response(
                {"error": "Invalid channel. Use 'email' or 'whatsapp'"},
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response({
            "message": f"Invitation being resent via {via}",
            "guest_id": guest.id,
            "guest_name": guest.full_name
        })

    @action(detail=True, methods=['post'])
    def check_in(self, request, pk=None):
        """Check in a guest"""
        guest = self.get_object()
        
        if guest.confirmed:
            return Response(
                {"message": "Guest already confirmed"},
                status=status.HTTP_200_OK
            )
        
        guest.confirmed = True
        guest.checked_in_at = timezone.now()
        guest.save()

        return Response({
            "message": f"{guest.full_name} checked in successfully",
            "guest_id": guest.id,
            "checked_in_at": guest.checked_in_at,
            "confirmed": guest.confirmed
        })

    @action(detail=True, methods=['get'])
    def invitation_card(self, request, pk=None):
        """Get guest invitation card URL"""
        guest = self.get_object()
        
        if not guest.invitation_card:
            return Response(
                {"error": "Invitation card not generated yet"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        return Response({
            "guest_id": guest.id,
            "invitation_card_url": request.build_absolute_uri(guest.invitation_card.url),
            "qr_code_url": request.build_absolute_uri(guest.qr_code_image.url) if guest.qr_code_image else None
        })

    @action(detail=False, methods=['get'])
    def by_qr(self, request):
        """Get guest by QR code"""
        code = request.query_params.get("code")

        if not code:
            return Response(
                {"error": "QR code parameter required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            guest = Guest.objects.get(qr_code=code)
            serializer = self.get_serializer(guest)
            return Response(serializer.data)
        except Guest.DoesNotExist:
            return Response(
                {"error": "Guest not found"},
                status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=True, methods=['get'])
    def history(self, request, pk=None):
        """Get guest invitation history"""
        guest = self.get_object()
        history = guest.invitation_history.all().order_by('-sent_at')
        
        history_data = []
        for record in history:
            history_data.append({
                "id": record.id,
                "sent_via": record.sent_via,
                "sent_at": record.sent_at,
                "sent_by": record.sent_by.username if record.sent_by else None,
                "status": record.status,
                "message": record.message[:100] if record.message else ""
            })
        
        return Response({
            "guest_id": guest.id,
            "guest_name": guest.full_name,
            "invitation_history": history_data
        })


# ======================
# PUBLIC API ENDPOINTS
# ======================

@api_view(['GET', 'POST'])
@permission_classes([permissions.AllowAny])
def confirm_attendance(request, qr_code):
    """Public endpoint for QR code attendance confirmation"""
    try:
        guest = Guest.objects.get(qr_code=qr_code)
    except Guest.DoesNotExist:
        return Response(
            {"error": "Invalid QR code"},
            status=status.HTTP_404_NOT_FOUND
        )

    if request.method == 'GET':
        # Return guest info (public)
        serializer = GuestSerializer(guest)
        return Response(serializer.data)

    elif request.method == 'POST':
        # Confirm attendance
        if guest.confirmed:
            return Response({
                "message": "Attendance already confirmed",
                "confirmed_at": guest.checked_in_at,
                "guest": GuestSerializer(guest).data
            }, status=status.HTTP_200_OK)
        
        guest.confirmed = True
        guest.checked_in_at = timezone.now()
        guest.save()

        return Response({
            "message": "Attendance confirmed successfully",
            "confirmed_at": guest.checked_in_at,
            "guest": GuestSerializer(guest).data
        }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def public_event_info(request, event_id):
    """Public event information (read-only)"""
    try:
        event = Event.objects.get(id=event_id)
    except Event.DoesNotExist:
        return Response(
            {"error": "Event not found"},
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Return limited public info
    return Response({
        "event_id": event.id,
        "title": event.title,
        "description": event.description[:200] if event.description else "",
        "date": event.date,
        "venue": event.venue,
        "organizer": event.organizer.username if event.organizer else "Unknown"
    })


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def user_statistics(request):
    """Get user dashboard statistics"""
    user = request.user
    
    events = Event.objects.filter(organizer=user)
    guests = Guest.objects.filter(event__organizer=user)
    
    total_events = events.count()
    total_guests = guests.count()
    confirmed_guests = guests.filter(confirmed=True).count()
    checked_in_guests = guests.filter(checked_in_at__isnull=False).count()
    
    # Upcoming events
    upcoming_events = events.filter(
        date__gte=timezone.now()
    ).order_by('date')[:5]
    
    upcoming_data = []
    for event in upcoming_events:
        event_guests = event.guests.count()
        event_confirmed = event.guests.filter(confirmed=True).count()
        upcoming_data.append({
            "id": event.id,
            "title": event.title,
            "date": event.date,
            "venue": event.venue,
            "guest_count": event_guests,
            "confirmed_count": event_confirmed
        })
    
    return Response({
        "user": user.username,
        "statistics": {
            "total_events": total_events,
            "total_guests": total_guests,
            "confirmed_guests": confirmed_guests,
            "checked_in_guests": checked_in_guests,
            "confirmation_rate": (confirmed_guests / total_guests * 100) if total_guests > 0 else 0,
            "check_in_rate": (checked_in_guests / total_guests * 100) if total_guests > 0 else 0
        },
        "upcoming_events": upcoming_data
    })


import csv
from django.http import Http404, HttpResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.urls import reverse_lazy
from django.utils import timezone
from django.db.models import Count, Q
from datetime import timedelta
from django.views.generic import CreateView, ListView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import authenticate, login, logout
from django.core.paginator import Paginator
from .permissions import is_officer
from .models import Event, Guest, InvitationHistory
from .forms import EventForm, GuestForm, BatchGuestForm
from .utils import generate_invitation_card
from .tasks import send_invitation_email, send_whatsapp_invitation, batch_send_invitations
import urllib.parse
from django.conf import settings


# ======================
# AUTHENTICATION VIEWS
# ======================

def home_view(request):
    """Home page view"""
    return render(request, 'events/home.html')

def signup_view(request):
    """User registration view"""
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('dashboard')
    else:
        form = UserCreationForm()
    return render(request, 'events/signup.html', {'form': form})

def login_view(request):
    """User login view"""
    if request.method == "POST":
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)

            # Redirect based on role
            if user.groups.filter(name="Officer").exists():
                return redirect("officer_dashboard")
            else:
                return redirect("dashboard")  # organizer dashboard
    else:
        form = AuthenticationForm()
    return render(request, 'events/login.html', {'form': form})

def logout_view(request):
    """User logout view"""
    logout(request)
    return redirect('home')


# ======================
# OFFICER VIEWS
# ======================

@login_required
@user_passes_test(is_officer)
def officer_dashboard(request):
    """Officer dashboard view"""
    events = Event.objects.all()
    return render(request, "events/officer/dashboard.html", {"events": events})

@login_required
@user_passes_test(is_officer)
def officer_event_detail(request, event_id):
    """Officer event detail view"""
    event = get_object_or_404(Event, id=event_id)
    guests = event.guests.all()

    return render(request, "events/officer/event_detail.html", {
        "event": event,
        "guests": guests
    })

@login_required
@user_passes_test(is_officer)
def officer_add_guest(request, event_id):
    """Officer add guest view"""
    event = get_object_or_404(Event, id=event_id)

    if request.method == "POST":
        form = GuestForm(request.POST)
        if form.is_valid():
            guest = form.save(commit=False)
            guest.event = event
            guest.save()
            generate_invitation_card(guest)
            return redirect("officer_event_detail", event_id=event.id)
    else:
        form = GuestForm()

    return render(request, "events/officer/add_guest.html", {
        "form": form,
        "event": event
    })

@login_required
@user_passes_test(is_officer)
def officer_send_invite(request, guest_id):
    """Officer send invitation view"""
    guest = get_object_or_404(Guest, id=guest_id)

    if request.method == "POST":
        via = request.POST.get("via")

        if via == "email":
            send_invitation_email.delay(guest.id)
        elif via == "whatsapp":
            send_whatsapp_invitation.delay(guest.id)

        return redirect("officer_event_detail", event_id=guest.event.id)

    return render(request, "events/officer/send_invite.html", {"guest": guest})


# ======================
# ORGANIZER DASHBOARD VIEWS
# ======================

@login_required
def dashboard(request):
    """Enhanced Dashboard with real statistics"""
    user = request.user
    
    # Get user's events
    events = Event.objects.filter(organizer=user)
    
    # Calculate statistics with annotations
    events_with_stats = events.annotate(
        guest_count=Count('guests', distinct=True),
        confirmed_count=Count('guests', filter=Q(guests__confirmed=True), distinct=True)
    )
    
    # Basic counts
    total_events = events.count()
    total_guests = Guest.objects.filter(event__organizer=user).count()
    confirmed_guests = Guest.objects.filter(
        event__organizer=user, 
        confirmed=True
    ).count()
    
    # Get events for display
    recent_events = events_with_stats.order_by('-created_at')[:5]
    
    # Upcoming events (next 30 days)
    thirty_days_later = timezone.now() + timedelta(days=30)
    upcoming_events = events_with_stats.filter(
        date__gte=timezone.now(),
        date__lte=thirty_days_later
    ).order_by('date')[:5]
    
    # Recent activity from InvitationHistory
    recent_activity = InvitationHistory.objects.filter(
        guest__event__organizer=user
    ).select_related('guest', 'guest__event')[:10]
    
    # Channel statistics
    channel_stats = InvitationHistory.objects.filter(
        guest__event__organizer=user
    ).values('sent_via').annotate(
        count=Count('id')
    ).order_by('-count')
    
    # Calculate percentages
    confirmation_rate = (confirmed_guests / total_guests * 100) if total_guests > 0 else 0
    
    # Daily statistics for chart
    today = timezone.now().date()
    week_ago = today - timedelta(days=7)
    
    daily_stats = []
    for i in range(7):
        date = week_ago + timedelta(days=i)
        day_sent = InvitationHistory.objects.filter(
            guest__event__organizer=user,
            sent_at__date=date
        ).count()
        day_confirmed = Guest.objects.filter(
            event__organizer=user,
            confirmed=True,
            checked_in_at__date=date
        ).count()
        daily_stats.append({
            'date': date.strftime('%a'),
            'sent': day_sent,
            'confirmed': day_confirmed
        })
    
    context = {
        # Basic statistics
        'total_events': total_events,
        'total_guests': total_guests,
        'confirmed_guests': confirmed_guests,
        'confirmation_rate': round(confirmation_rate, 1),
        
        # Event lists
        'recent_events': recent_events,
        'upcoming_events': upcoming_events,
        
        # Additional data for enhanced dashboard
        'recent_activity': recent_activity,
        'channel_stats': channel_stats,
        'daily_stats': daily_stats,
        
        # Calculated stats
        'pending_guests': total_guests - confirmed_guests,
        'today_sent': InvitationHistory.objects.filter(
            guest__event__organizer=user,
            sent_at__date=today
        ).count(),
        'qr_scans': Guest.objects.filter(
            event__organizer=user,
            checked_in_at__isnull=False
        ).count(),
        
        # For trend calculations (simulated for now)
        'last_month_events': max(0, total_events - 3),  # Simulated
        'last_month_guests': max(0, total_guests - 10),  # Simulated
    }
    
    return render(request, 'events/dashboard.html', context)


# ======================
# EVENT WEB VIEWS
# ======================

class EventListView(LoginRequiredMixin, ListView):
    """Event list view for organizer"""
    model = Event
    template_name = 'events/event_list.html'
    context_object_name = 'events'

    def get_queryset(self):
        return Event.objects.filter(organizer=self.request.user)

class EventDetailView(LoginRequiredMixin, DetailView):
    """Event detail view"""
    model = Event
    template_name = 'events/event_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        event = self.object
        guests = event.guests.all()
        context['guests'] = guests
        context['guest_count'] = guests.count()
        context['confirmed_count'] = guests.filter(confirmed=True).count()
        context['pending_count'] = guests.filter(confirmed=False).count()
        return context

class EventCreateView(LoginRequiredMixin, CreateView):
    """Create event view"""
    model = Event
    form_class = EventForm
    template_name = 'events/event_form.html'
    success_url = reverse_lazy('event_list')
    
    def form_valid(self, form):
        form.instance.organizer = self.request.user
        return super().form_valid(form)


# ======================
# GUEST WEB VIEWS
# ======================

@login_required
def event_guests_view(request, event_id):
    """View to display all guests for a specific event"""
    event = get_object_or_404(Event, id=event_id, organizer=request.user)
    
    # Get all guests for this event
    guests = event.guests.all().order_by('full_name')
    
    # Apply filters
    status = request.GET.get('status', 'all')
    search_query = request.GET.get('search', '')
    
    if search_query:
        guests = guests.filter(
            Q(full_name__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(phone__icontains=search_query)
        )
    
    if status == 'confirmed':
        guests = guests.filter(confirmed=True)
    elif status == 'pending':
        guests = guests.filter(confirmed=False)
    # 'all' shows all guests
    
    # Count statistics
    total_guests = event.guests.count()
    confirmed_count = event.guests.filter(confirmed=True).count()
    pending_count = total_guests - confirmed_count
    
    # Pagination
    paginator = Paginator(guests, 20)  # Show 20 guests per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'event': event,
        'guests': page_obj,
        'page_obj': page_obj,
        'is_paginated': paginator.num_pages > 1,
        'total_guests': total_guests,
        'confirmed_count': confirmed_count,
        'pending_count': pending_count,
        'search_query': search_query,
        'current_status': status,
    }
    
    return render(request, 'events/event_guests.html', context)

from django.shortcuts import render, get_object_or_404
from django.conf import settings
import urllib.parse

def generate_whatsapp_link(guest):
    message = f"""
Invitation: {guest.event.title}

Dear {guest.full_name}
Date: {guest.event.date.strftime('%d %B %Y')}
Venue: {guest.event.venue}

View your invitation card: https://{settings.DOMAIN}{guest.invitation_card.url}
Confirm attendance: https://{settings.DOMAIN}/confirm/{guest.qr_code}/
"""
    encoded_message = urllib.parse.quote(message)
    phone = guest.phone.replace("+", "").replace(" ", "")
    return f"https://wa.me/{phone}?text={encoded_message}"


@login_required
def guest_detail_view(request, guest_id):
    """View to show guest details"""
    try:
        guest = Guest.objects.get(id=guest_id, event__organizer=request.user)
    except Guest.DoesNotExist:
        # If not organizer, check if officer
        if request.user.groups.filter(name="Officer").exists():
            guest = get_object_or_404(Guest, id=guest_id)
        else:
            raise Http404("Guest not found")
    
    # Get invitation history
    invitation_history = InvitationHistory.objects.filter(guest=guest).order_by('-sent_at')

    # Generate WhatsApp link for this guest
    whatsapp_link = generate_whatsapp_link(guest) if guest.phone else None
    
    context = {
        'guest': guest,
        'event': guest.event,
        'invitation_history': invitation_history,
        'whatsapp_link': whatsapp_link,   # <-- pass to template
    }
    
    return render(request, 'events/guest_detail.html', context)


@login_required
def guest_check_in_view(request, guest_id):
    """Check in a guest manually"""
    guest = get_object_or_404(Guest, id=guest_id, event__organizer=request.user)
    
    if request.method == 'POST':
        guest.confirmed = True
        guest.checked_in_at = timezone.now()
        guest.save()
        
        messages.success(request, f'{guest.full_name} has been checked in successfully!')
        return redirect('guest_detail', guest_id=guest.id)
    
    return render(request, 'events/guest_check_in.html', {'guest': guest})

@login_required
def download_invitation_view(request, guest_id):
    """Download invitation card for a guest"""
    guest = get_object_or_404(Guest, id=guest_id, event__organizer=request.user)
    
    # Check if invitation card exists
    if not guest.invitation_card:
        # Generate if not exists
        generate_invitation_card(guest)
        guest.refresh_from_db()
    
    # Serve the file
    file_path = guest.invitation_card.path
    with open(file_path, 'rb') as f:
        response = HttpResponse(f.read(), content_type='image/png')
        response['Content-Disposition'] = f'attachment; filename="invitation_{guest.full_name}.png"'
        return response

@login_required
def export_guests_view(request, event_id):
    """Export guests to CSV"""
    event = get_object_or_404(Event, id=event_id, organizer=request.user)
    guests = event.guests.all()
    
    # Create CSV response
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="guests_{event.title}.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Name', 'Email', 'Phone', 'Confirmed', 'Invitation Sent', 'Checked In At'])
    
    for guest in guests:
        writer.writerow([
            guest.full_name,
            guest.email,
            guest.phone or '',
            'Yes' if guest.confirmed else 'No',
            'Yes' if guest.invitation_sent else 'No',
            guest.checked_in_at.strftime('%Y-%m-%d %H:%M') if guest.checked_in_at else ''
        ])
    
    return response


# ======================
# BATCH OPERATIONS
# ======================

@login_required
def batch_add_guests(request):
    """Batch add guests view"""
    if request.method == 'POST':
        form = BatchGuestForm(request.user, request.POST, request.FILES)
        if form.is_valid():
            try:
                event = form.cleaned_data['event']
                input_method = form.cleaned_data['input_method']
                parsed_guests = form.cleaned_data.get('parsed_guests', [])
                
                if not parsed_guests:
                    messages.error(request, 'No guest data found. Please check your input.')
                    return render(request, 'events/batch_add_guests.html', {'form': form})
                
                success_count = 0
                error_count = 0
                errors = []
                
                for i, guest_data in enumerate(parsed_guests, start=1):
                    try:
                        # Create guest
                        guest = Guest(
                            event=event,
                            title=guest_data.get('title', 'Mr'),
                            full_name=guest_data.get('full_name', '').strip(),
                            email=guest_data.get('email', '').strip() or None,
                            phone=guest_data.get('phone', '').strip() or None,
                            notes=guest_data.get('notes', '').strip() or None,
                        )
                        guest.save()
                        success_count += 1
                        
                        # Generate invitation card
                        generate_invitation_card(guest)
                        
                    except Exception as e:
                        error_count += 1
                        errors.append(f"Guest {i} ({guest_data.get('full_name', 'Unknown')}): {str(e)}")
                
                # Show results
                if success_count > 0:
                    messages.success(request, 
                        f'Successfully added {success_count} guest(s) to "{event.title}"'
                    )
                
                if error_count > 0:
                    messages.warning(request, 
                        f'{error_count} guest(s) could not be added'
                    )
                    # Show first 3 errors
                    for error in errors[:3]:
                        messages.error(request, error)
                    if len(errors) > 3:
                        messages.info(request, f'... and {len(errors) - 3} more errors')
                
                return redirect('event_guests', event_id=event.id)
                
            except Exception as e:
                messages.error(request, f'Error processing guests: {str(e)}')
        else:
            # Form has errors
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        form = BatchGuestForm(request.user)
    
    return render(request, 'events/batch_add_guests.html', {'form': form})

@staff_member_required(login_url='login')
def send_event_invitations(request, event_id):
    """Send invitations for an event"""
    event = get_object_or_404(Event, id=event_id)
    guests = event.guests.all()

    if request.method == 'POST':
        via = request.POST.get('via', 'email')  # email or whatsapp

        # trigger celery task in background
        batch_send_invitations(event.id, via)

        # update flag for all guests immediately (optional)
        for guest in guests:
            guest.invitation_sent = True
            guest.save()

        messages.success(request, f"Invitations are being sent via {via.capitalize()} in the background.")
        return redirect('event_detail', pk=event.id)

    return render(request, 'events/send_invitations.html', {
        'event': event,
        'guests': guests
    })



def generate_whatsapp_link(guest):
    message = f"""
Invitation: {guest.event.title}

Dear {guest.full_name}
Date: {guest.event.date.strftime('%d %B %Y')}
Venue: {guest.event.venue}

View your invitation card: https://{settings.DOMAIN}{guest.invitation_card.url}
Confirm attendance: https://{settings.DOMAIN}/confirm/{guest.qr_code}/
"""
    encoded_message = urllib.parse.quote(message)
    phone = guest.phone.replace("+", "").replace(" ", "")
    return f"https://wa.me/{phone}?text={encoded_message}"


def send_whatsapp_invitations_view(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    
    # Tengeneza links kwa kila guest
    links = []
    all_links_text = ""
    for guest in event.guests.all():
        if guest.phone:
            link = generate_whatsapp_link(guest)
            links.append({"guest": guest.full_name, "link": link})
            all_links_text += f"{guest.full_name}: {link}\n"

    return render(request, "events/send_whatsapp.html", {
        "event": event,
        "links": links,
        "all_links_text": all_links_text
    })
