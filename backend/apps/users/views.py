from django.shortcuts import render
from django.http import JsonResponse
from .models import UserProfile

def user_profile(request, user_id):
    try:
        user = UserProfile.objects.get(id=user_id)
        return JsonResponse({
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'mood': user.mood,
            'created_at': user.created_at.isoformat(),
        })
    except UserProfile.DoesNotExist:
        return JsonResponse({'error': 'User not found'}, status=404)

def update_user_mood(request, user_id):
    if request.method == 'POST':
        mood = request.POST.get('mood')
        try:
            user = UserProfile.objects.get(id=user_id)
            user.mood = mood
            user.save()
            return JsonResponse({'message': 'Mood updated successfully'})
        except UserProfile.DoesNotExist:
            return JsonResponse({'error': 'User not found'}, status=404)
    return JsonResponse({'error': 'Invalid request method'}, status=400)