from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.utils import timezone

from .models import Address, Order, Product, Profile, Review, ServiceArea, Store

User = get_user_model()


class StyledFormMixin:
    def apply_styles(self):
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs['class'] = 'form-check-input'
            else:
                field.widget.attrs['class'] = 'form-control' if not isinstance(field.widget, forms.Select) else 'form-select'


class RegistrationForm(StyledFormMixin, UserCreationForm):
    first_name = forms.CharField(label='Nome')
    last_name = forms.CharField(label='Sobrenome')
    email = forms.EmailField(label='E-mail')

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('first_name', 'last_name', 'email', 'password1', 'password2')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_styles()

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if User.objects.filter(username__iexact=email).exists():
            raise forms.ValidationError('Já existe uma conta com este e-mail.')
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = self.cleaned_data['email']
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
            Profile.objects.create(user=user, role=Profile.Role.CLIENT)
        return user


class ProfileForm(StyledFormMixin, forms.ModelForm):
    first_name = forms.CharField(label='Nome')
    last_name = forms.CharField(label='Sobrenome')
    email = forms.EmailField(label='E-mail', disabled=True)

    class Meta:
        model = Profile
        fields = ('first_name', 'last_name', 'email', 'phone')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['first_name'].initial = self.instance.user.first_name
        self.fields['last_name'].initial = self.instance.user.last_name
        self.fields['email'].initial = self.instance.user.email
        self.apply_styles()

    def save(self, commit=True):
        profile = super().save(commit=False)
        profile.user.first_name = self.cleaned_data['first_name']
        profile.user.last_name = self.cleaned_data['last_name']
        if commit:
            profile.user.save(update_fields=['first_name', 'last_name'])
            profile.save()
        return profile


class AddressForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Address
        exclude = ('user',)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_styles()
        self.fields['postal_code'].widget.attrs.update({
            'autocomplete': 'postal-code',
            'inputmode': 'numeric',
            'placeholder': '00000-000',
            'maxlength': '9',
        })
        self.fields['street'].widget.attrs['autocomplete'] = 'address-line1'
        self.fields['number'].widget.attrs['autocomplete'] = 'address-line2'
        self.fields['city'].widget.attrs['autocomplete'] = 'address-level2'
        self.fields['state'].widget.attrs.update({'autocomplete': 'address-level1', 'maxlength': '2'})


class CheckoutForm(StyledFormMixin, forms.Form):
    address = forms.ModelChoiceField(queryset=Address.objects.none(), label='Endereço de entrega')
    recipient_name = forms.CharField(label='Nome do destinatário', max_length=120)
    recipient_phone = forms.CharField(label='Telefone do destinatário', max_length=20)
    delivery_date = forms.DateField(label='Data da entrega', widget=forms.DateInput(attrs={'type': 'date'}))
    delivery_period = forms.ChoiceField(label='Período', choices=Order.DeliveryPeriod.choices)
    card_message = forms.CharField(label='Mensagem do cartão', required=False, widget=forms.Textarea(attrs={'rows': 3}))
    is_anonymous = forms.BooleanField(label='Não revelar meu nome', required=False)
    notes = forms.CharField(label='Observações', required=False, widget=forms.Textarea(attrs={'rows': 2}))
    payment_method = forms.ChoiceField(label='Forma de pagamento', choices=Order.PaymentMethod.choices)

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['address'].queryset = user.addresses.all()
        self.fields['delivery_date'].widget.attrs['min'] = timezone.localdate().isoformat()
        primary = user.addresses.filter(is_primary=True).first()
        if primary:
            self.fields['address'].initial = primary
            self.fields['recipient_name'].initial = primary.recipient_name
            self.fields['recipient_phone'].initial = primary.recipient_phone
        self.apply_styles()

    def clean_delivery_date(self):
        value = self.cleaned_data['delivery_date']
        if value < timezone.localdate():
            raise forms.ValidationError('Escolha hoje ou uma data futura.')
        return value


class ReviewForm(StyledFormMixin, forms.ModelForm):
    rating = forms.TypedChoiceField(label='Nota', choices=[(i, f'{i} estrela' if i == 1 else f'{i} estrelas') for i in range(5, 0, -1)], coerce=int)

    class Meta:
        model = Review
        fields = ('rating', 'comment')
        widgets = {'comment': forms.Textarea(attrs={'rows': 4})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_styles()


class ProductForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Product
        exclude = ('store', 'slug', 'created_at', 'updated_at')
        widgets = {'description': forms.Textarea(attrs={'rows': 4})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_styles()


class StoreForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Store
        exclude = ('owner', 'slug', 'average_rating', 'review_count', 'is_active', 'is_featured', 'created_at')
        widgets = {'description': forms.Textarea(attrs={'rows': 5})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_styles()


class ServiceAreaForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = ServiceArea
        exclude = ('store',)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_styles()
