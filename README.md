
---

## **ShereheZetu – Event & Guest Management System Documentation**

### **1. Project Overview**

**ShereheZetu** ni mfumo wa kusimamia matukio (events) na wageni (guests). Unalenga kurahisisha:

* Usimamizi wa events na guests
* Kutuma invitations kwa email na WhatsApp
* Kuzalisha invitation cards zilizo na QR codes  
* Ku-track attendance na check-ins kwa QR code
* API endpoints kwa Flutter mobile app

**Technology Stack:**

* Backend: Django + Django REST Framework
* Frontend Web: Django templates (HTML/CSS/JS)
* Mobile: Flutter app kutumia API
* Database: SQLite / PostgreSQL
* Tasks & Emails: Celery + Redis

---

### **2. Features**

1. **Web Dashboard (Officer View)**

   * Jumla ya events, guests, confirmed guests
   * Recent activity & invitation statistics
   * Upcoming events, daily stats chart

2. **Event Management**

   * Create, Update, Delete events
   * Event details view with guest statistics

3. **Guest Management**

   * Add individual guests or batch upload via CSV/Excel/JSON
   * Track confirmation & check-ins
   * Resend invitations via Email or WhatsApp

4. **Invitation Cards & QR Codes**

   * Auto-generate invitation card with event info & QR
   * QR code scan for attendance confirmation

5. **API Endpoints (For Mobile)**

   * `/api/events/` – List, create, update events
   * `/api/events/{id}/add_guests_batch/` – Batch guest addition
   * `/api/events/{id}/send_invitations/` – Send invitations
   * `/api/events/{id}/export_guests/` – Export guest list
   * `/api/guests/` – Guest list, check-in, resend invitation
   * `/api/guests/by_qr/?code=` – Get guest by QR code
   * `/api/confirm_attendance/{qr_code}/` – Public attendance confirmation

---

### **3. Models**

1. **Event**

   * title, description, date, venue
   * theme_color, background_color, text_color
   * template_svg (optional for invitation card)
   * organizer (User FK)

2. **Guest**

   * title, full_name, email, phone
   * qr_code, qr_code_image, invitation_card
   * confirmed (Boolean), checked_in_at (DateTime)
   * status (pending/confirmed)

3. **InvitationHistory**

   * guest (FK), sent_via (email/whatsapp), sent_at

---

### **4. Serializers**

* `EventSerializer` – includes nested `GuestSerializer`
* `GuestSerializer` – handles guest info, QR, card info

---

### **5. Views**

* Web: Dashboard, EventListView, EventDetailView, GuestListView, EventCreateView
* API: EventViewSet, GuestViewSet, confirm_attendance endpoint

---

### **6. Forms**

* `EventForm` – create/update events
* `GuestForm` – add individual guest
* `BatchGuestForm` – batch guest upload

---

### **7. Utilities**

* `generate_qr_code(data)` – generate QR image
* `generate_invitation_card(guest)` – create invitation card with QR
* `process_batch_guests(event, guests_data)` – create multiple guests
* `export_guest_list(event, format='csv')` – export guest list

---

### **8. Tasks**

* `send_invitation_email` – async email
* `send_whatsapp_invitation` – async WhatsApp
* `batch_send_invitations` – async batch sending

---

### **9. Setup Instructions**

1. Create virtual environment & install requirements:

   ```bash
   python -m venv venv
   pip install -r requirements.txt
   ```
2. Apply migrations:

   ```bash
   python manage.py makemigrations
   python manage.py migrate
   ```
3. Create superuser:

   ```bash
   python manage.py createsuperuser
   ```
4. Run server:

   ```bash
   python manage.py runserver
   ```
5. Start Celery for async tasks (if used):

   ```bash
   celery -A sherehezetu worker -l info
   ```

---

### **10. Notes / Challenges**

* CairoSVG dependency required for invitation cards
* Initial QR generation may require PIL and qrcode packages
* Batch upload needs correct CSV/Excel formatting
* Flutter app integration consumes API endpoints


from events.models import Event, Guest
from events.utils import process_batch_guests
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()
organizer = User.objects.first()

event = Event.objects.create(
    organizer=organizer,
    title="Tech Conference 2026",
    description="Digital invitation cards demo",
    date=timezone.now() + timezone.timedelta(days=7),
    venue="Dar es Salaam Conference Center",
)

guests_data = [
    {'full_name': 'Alice Johnson', 'email': 'alice@example.com'},
    {'full_name': 'Bob Smith', 'email': 'bob@example.com'},
    {'full_name': 'Carol Mbowe', 'email': 'carol@example.com'}
]

created = process_batch_guests(event, guests_data)
print(f"Created / updated {len(created)} guests with invitation cards!")
