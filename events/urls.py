from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'api/events', views.EventViewSet, basename='event')
router.register(r'api/guests', views.GuestViewSet, basename='guest')

urlpatterns = [
    # ======================
    # WEB PAGES (HTML)
    # ======================
    path('', views.home_view, name='home'),
    
    # Authentication
    path('signup/', views.signup_view, name='signup'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    
    # Dashboard
    path('dashboard/', views.dashboard, name='dashboard'),
    
    # Officer Views
    path('officer/', views.officer_dashboard, name='officer_dashboard'),
    path('officer/event/<int:event_id>/', views.officer_event_detail, name='officer_event_detail'),
    path('officer/event/<int:event_id>/add-guest/', views.officer_add_guest, name='officer_add_guest'),
    path('officer/guest/<int:guest_id>/send/', views.officer_send_invite, name='officer_send_invite'),
    
    # Event Views
    path('events/', views.EventListView.as_view(), name='event_list'),
    path('events/create/', views.EventCreateView.as_view(), name='event_create'),
    path('events/<int:pk>/', views.EventDetailView.as_view(), name='event_detail'),
    path('events/<int:event_id>/guests/', views.event_guests_view, name='event_guests'),
    path('events/<int:event_id>/send-invitations/', views.send_event_invitations, name='send_event_invitations'),
    
    # Guest Views
    path('guest/<int:guest_id>/', views.guest_detail_view, name='guest_detail'),
    path('guest/<int:guest_id>/check-in/', views.guest_check_in_view, name='check_in'),
    path('guest/<int:guest_id>/download/', views.download_invitation_view, name='download_invitation'),
    
    # Batch Operations
    path('guests/batch-add/', views.batch_add_guests, name='batch_add_guests'),
    path('events/<int:event_id>/export/', views.export_guests_view, name='export_guests'),
    
    # ======================
    # API ENDPOINTS (JSON)
    # ======================
    # Include API router
    path('', include(router.urls)),
    
    # Public API
    path('api/confirm/<str:qr_code>/', views.confirm_attendance, name='confirm_attendance'),
    path('api/events/<int:event_id>/public/', views.public_event_info, name='public_event_info'),
    
    # User API
    path('api/user/stats/', views.user_statistics, name='user_statistics'),
]