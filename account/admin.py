from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django import forms
from .models import Profile, RegistrationVerification


class UserCreationWithEmailForm(UserCreationForm):
    email = forms.EmailField(required=True, label='Email address')

    class Meta(UserCreationForm.Meta):
        fields = ('username', 'email')

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
        return user


class UserAdmin(BaseUserAdmin):
    add_form = UserCreationWithEmailForm
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'password1', 'password2'),
        }),
    )


admin.site.unregister(User)
admin.site.register(User, UserAdmin)


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'mobile_number', 'date_of_birth', 'postcode', 'image']


@admin.register(RegistrationVerification)
class RegistrationVerificationAdmin(admin.ModelAdmin):
    list_display = ['email', 'verification_code', 'is_used', 'expires_at', 'created_at']
    list_filter = ['is_used', 'created_at']
    search_fields = ['email', 'verification_code']
