from django.contrib import messages
from django.shortcuts import render, redirect
from django.urls import reverse

from webapp.forms import AccountsForm
from webapp.tasks import auto_signup_accounts


def index_view(request):
    form = AccountsForm(request.POST or None)
    if form.is_valid():
        auto_signup_accounts.delay(form.cleaned_data)
        messages.success(request, 'Аккаунты будут добавлены в ближайшее время')
        return redirect(reverse('webapp:index'))
    return render(request, 'webapp/index.html', {'form': form})
