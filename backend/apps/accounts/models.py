"""
사용자 모델 — Django AbstractUser 기반
비밀번호 인증, 세션 로그인 지원
"""
import uuid
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """사용자"""
    ROLE_CHOICES = [
        ('admin', '관리자'),
        ('member', '멤버'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(max_length=255, unique=True)
    name = models.CharField(max_length=100, blank=True, default='')
    department = models.CharField(max_length=100, blank=True, default='')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='admin')

    # AbstractUser의 username 대신 email을 로그인 식별자로 사용
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'name']

    class Meta:
        db_table = 'users'
        ordering = ['-date_joined']
        verbose_name = '사용자'
        verbose_name_plural = '사용자'

    def __str__(self):
        return f'{self.name} ({self.email})'
