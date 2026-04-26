from django.shortcuts import render
from django.http import JsonResponse
from .models import MoodEntry

def mood_dashboard(request):
    moods = MoodEntry.objects.all()
    return render(request, 'dashboard.html', {'moods': moods})

def add_mood_entry(request):
    if request.method == 'POST':
        mood = request.POST.get('mood')
        new_entry = MoodEntry(mood=mood)
        new_entry.save()
        return JsonResponse({'status': 'success', 'mood': mood})
    return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=400)