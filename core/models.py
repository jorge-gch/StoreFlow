from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

class UserProfile(models.Model):
    """
    Extensión del modelo User para control de roles y permisos en StoreFlow.
    """
    ROLE_ADMIN = 'admin'
    ROLE_EMPLOYEE = 'employee'
    
    ROLE_CHOICES = [
        (ROLE_ADMIN, 'Administrador'),
        (ROLE_EMPLOYEE, 'Empleado'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_EMPLOYEE, verbose_name='Rol')
    phone = models.CharField(max_length=20, blank=True, verbose_name='Teléfono')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de creación')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Fecha de actualización')

    class Meta:
        verbose_name = 'Perfil de Usuario'
        verbose_name_plural = 'Perfiles de Usuarios'
        ordering = ['user__username']

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} ({self.get_role_display()})"

    @property
    def is_admin(self):
        return self.role == self.ROLE_ADMIN or self.user.is_superuser

    @property
    def is_employee(self):
        return self.role == self.ROLE_EMPLOYEE


@receiver(post_save, sender=User)
def create_or_save_user_profile(sender, instance, created, **kwargs):
    """
    Crea automáticamente el perfil asociado cuando se registra un nuevo usuario.
    Si el usuario es superuser, se le asigna rol de Administrador por defecto.
    """
    if created:
        role = UserProfile.ROLE_ADMIN if instance.is_superuser else UserProfile.ROLE_EMPLOYEE
        UserProfile.objects.create(user=instance, role=role)
    else:
        if hasattr(instance, 'profile'):
            instance.profile.save()
        else:
            role = UserProfile.ROLE_ADMIN if instance.is_superuser else UserProfile.ROLE_EMPLOYEE
            UserProfile.objects.create(user=instance, role=role)
