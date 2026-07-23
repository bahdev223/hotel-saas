# apps/restaurant/views/dashboard.py
from django.shortcuts import render
from django.contrib.auth.decorators import login_required


@login_required
def dashboard(request):
    """Dashboard restaurant - Vue d'ensemble"""
    return render(request, 'restaurant/dashboard.html')


