from django.db import models


class AvitoUser(models.Model):
    email = models.EmailField(verbose_name='Email')
    login = models.CharField(max_length=50, verbose_name='Логин')
    password = models.CharField(max_length=10, verbose_name='Паорль')
    phone = models.CharField(max_length=11, verbose_name='Телефон')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')

    def __str__(self):
        return self.login

    class Meta:
        verbose_name_plural = 'Авито пользователи'
        verbose_name = 'Авито пользователь'


class YaMail(models.Model):
    index = models.PositiveIntegerField()
    email = models.EmailField()

    def __str__(self):
        return self.email

    class Meta:
        ordering = ['index']
