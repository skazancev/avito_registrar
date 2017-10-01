from django import forms


class AccountsForm(forms.Form):
    quantity = forms.IntegerField(min_value=1)
    email = forms.EmailField()
