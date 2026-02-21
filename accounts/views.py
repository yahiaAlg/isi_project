"""
Views for accounts app - function-based views.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.db import transaction

from .forms import LoginForm, UserForm, UserProfileForm
from .models import UserProfile


def login_view(request):
    """Login view - handles GET and POST."""
    if request.user.is_authenticated:
        return redirect('reporting:dashboard')
    
    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            next_url = request.GET.get('next', 'reporting:dashboard')
            return redirect(next_url)
        else:
            messages.error(request, "Nom d'utilisateur ou mot de passe incorrect.")
    else:
        form = LoginForm()
    
    return render(request, 'accounts/login.html', {'form': form})


@login_required
def logout_view(request):
    """Logout view - POST only for security."""
    if request.method == 'POST':
        logout(request)
        messages.success(request, "Vous avez été déconnecté avec succès.")
        return redirect('accounts:login')
    return redirect('reporting:dashboard')


@login_required
def user_list(request):
    """List all users - admin only."""
    # Check if user is admin
    if not request.user.profile.is_admin:
        messages.error(request, "Vous n'avez pas la permission d'accéder à cette page.")
        return redirect('reporting:dashboard')
    
    users = User.objects.select_related('profile').all()
    return render(request, 'accounts/user_list.html', {'users': users})


@login_required
def user_create(request):
    """Create a new user - admin only."""
    if not request.user.profile.is_admin:
        messages.error(request, "Vous n'avez pas la permission d'effectuer cette action.")
        return redirect('reporting:dashboard')
    
    if request.method == 'POST':
        user_form = UserForm(request.POST)
        profile_form = UserProfileForm(request.POST)
        
        if user_form.is_valid() and profile_form.is_valid():
            with transaction.atomic():
                # Create user
                user = user_form.save(commit=False)
                password = user_form.cleaned_data.get('password')
                if password:
                    user.set_password(password)
                user.save()
                
                # Create/update profile
                profile = profile_form.save(commit=False)
                profile.user = user
                profile.save()
                
                messages.success(request, f"L'utilisateur '{user.username}' a été créé avec succès.")
                return redirect('accounts:user_list')
        else:
            messages.error(request, "Veuillez corriger les erreurs ci-dessous.")
    else:
        user_form = UserForm()
        profile_form = UserProfileForm()
    
    return render(request, 'accounts/user_form.html', {
        'user_form': user_form,
        'profile_form': profile_form,
        'action': 'create'
    })


@login_required
def user_edit(request, user_id):
    """Edit an existing user - admin only."""
    if not request.user.profile.is_admin:
        messages.error(request, "Vous n'avez pas la permission d'effectuer cette action.")
        return redirect('reporting:dashboard')
    
    user = get_object_or_404(User, id=user_id)
    profile = get_object_or_404(UserProfile, user=user)
    
    if request.method == 'POST':
        user_form = UserForm(request.POST, instance=user)
        profile_form = UserProfileForm(request.POST, instance=profile)
        
        if user_form.is_valid() and profile_form.is_valid():
            with transaction.atomic():
                # Update user
                user = user_form.save(commit=False)
                password = user_form.cleaned_data.get('password')
                if password:
                    user.set_password(password)
                user.save()
                
                # Update profile
                profile_form.save()
                
                messages.success(request, f"L'utilisateur '{user.username}' a été mis à jour avec succès.")
                return redirect('accounts:user_list')
        else:
            messages.error(request, "Veuillez corriger les erreurs ci-dessous.")
    else:
        user_form = UserForm(instance=user)
        profile_form = UserProfileForm(instance=profile)
    
    return render(request, 'accounts/user_form.html', {
        'user_form': user_form,
        'profile_form': profile_form,
        'user_obj': user,
        'action': 'edit'
    })


@login_required
def user_delete(request, user_id):
    """Delete a user - admin only."""
    if not request.user.profile.is_admin:
        messages.error(request, "Vous n'avez pas la permission d'effectuer cette action.")
        return redirect('reporting:dashboard')
    
    user = get_object_or_404(User, id=user_id)
    
    # Prevent self-deletion
    if user == request.user:
        messages.error(request, "Vous ne pouvez pas supprimer votre propre compte.")
        return redirect('accounts:user_list')
    
    if request.method == 'POST':
        username = user.username
        user.delete()
        messages.success(request, f"L'utilisateur '{username}' a été supprimé avec succès.")
        return redirect('accounts:user_list')
    
    return render(request, 'accounts/user_confirm_delete.html', {'user_obj': user})
