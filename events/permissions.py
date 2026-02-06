# events/permissions.py
from django.contrib.auth.decorators import user_passes_test

def is_officer(user):
    return user.groups.filter(name="Officer").exists()
