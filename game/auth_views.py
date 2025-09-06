import json

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST


@ensure_csrf_cookie
def csrf(request):
    return JsonResponse({"csrfToken": get_token(request)})


@require_POST
@csrf_protect
def login_view(request):
    data = json.loads(request.body or "{}")
    username = data.get("username")
    password = data.get("password")
    user = authenticate(request, username=username, password=password)
    if user is None:
        return JsonResponse({"detail": "Invalid credentials"}, status=400)
    login(request, user)  # sets session cookie (HttpOnly)
    return JsonResponse({"id": user.id, "username": user.username})


@require_POST
@csrf_protect
def register_view(request):
    data = json.loads(request.body or "{}")
    username = data.get("username")
    password = data.get("password")
    if not username or not password:
        return JsonResponse({"detail": "Username and password are required"}, status=400)
    if User.objects.filter(username=username).exists():
        return JsonResponse({"detail": "Username already taken"}, status=400)
    user = User.objects.create_user(username=username, password=password)
    login(request, user)
    return JsonResponse({"id": user.id, "username": user.username}, status=201)

@require_POST
def logout_view(request):
    logout(request)
    return JsonResponse({"detail": "Logged out"})


@require_GET
def me_view(request):
    if request.user.is_authenticated:
        u = request.user
        return JsonResponse({"id": u.id, "username": u.username})
    return JsonResponse({"detail": "Not authenticated"}, status=401)

