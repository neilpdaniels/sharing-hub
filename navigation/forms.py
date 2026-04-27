from django import forms

from .models import CategorySuggestion


class CategorySuggestionForm(forms.ModelForm):
    class Meta:
        model = CategorySuggestion
        fields = ['name', 'description', 'photo']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'maxlength': 120}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 5}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['photo'].widget.attrs.update({'class': 'form-control-file'})
