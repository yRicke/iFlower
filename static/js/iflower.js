document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('[data-cart-select]').forEach((checkbox) => {
    checkbox.addEventListener('change', () => checkbox.form.requestSubmit());
  });

  document.querySelectorAll('[data-cart-store-select]').forEach((checkbox) => {
    const selectedLines = Number(checkbox.dataset.selectedLines);
    const totalLines = Number(checkbox.dataset.totalLines);
    checkbox.indeterminate = selectedLines > 0 && selectedLines < totalLines;
    checkbox.addEventListener('change', () => checkbox.form.requestSubmit());
  });

  document.querySelectorAll('input[type="password"]').forEach((input) => {
    const wrapper = document.createElement('div');
    wrapper.className = 'password-field';
    input.parentNode.insertBefore(wrapper, input);
    wrapper.appendChild(input);

    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'password-toggle';
    button.setAttribute('aria-label', 'Mostrar senha');
    button.setAttribute('aria-pressed', 'false');
    button.textContent = '👁';
    button.addEventListener('click', () => {
      const showing = input.type === 'text';
      input.type = showing ? 'password' : 'text';
      button.setAttribute('aria-label', showing ? 'Mostrar senha' : 'Ocultar senha');
      button.setAttribute('aria-pressed', String(!showing));
      button.classList.toggle('is-visible', !showing);
    });
    wrapper.appendChild(button);
  });

  const addressForm = document.querySelector('[data-address-form]');
  if (addressForm) setupPostalCodeLookup(addressForm);
});

function setupPostalCodeLookup(form) {
  const postalCode = form.querySelector('[name="postal_code"]');
  const feedback = form.querySelector('[data-cep-feedback]');
  const fields = {
    street: form.querySelector('[name="street"]'),
    neighborhood: form.querySelector('[name="neighborhood"]'),
    city: form.querySelector('[name="city"]'),
    state: form.querySelector('[name="state"]'),
  };

  const setFeedback = (message, state = '') => {
    if (!feedback) return;
    feedback.textContent = message;
    feedback.dataset.state = state;
  };

  postalCode.addEventListener('input', () => {
    const digits = postalCode.value.replace(/\D/g, '').slice(0, 8);
    postalCode.value = digits.length > 5 ? `${digits.slice(0, 5)}-${digits.slice(5)}` : digits;
  });

  postalCode.addEventListener('blur', async () => {
    const digits = postalCode.value.replace(/\D/g, '');
    if (digits.length !== 8) {
      setFeedback('Informe um CEP com 8 dígitos.', 'error');
      return;
    }

    setFeedback('Buscando endereço…', 'loading');
    postalCode.setAttribute('aria-busy', 'true');
    try {
      const response = await fetch(`https://viacep.com.br/ws/${digits}/json/`, {
        headers: { Accept: 'application/json' },
      });
      if (!response.ok) throw new Error('Falha na consulta');
      const data = await response.json();
      if (data.erro) throw new Error('CEP não encontrado');

      fields.street.value = data.logradouro || '';
      fields.neighborhood.value = data.bairro || '';
      fields.city.value = data.localidade || '';
      fields.state.value = data.uf || '';
      Object.values(fields).forEach((field) => field.dispatchEvent(new Event('change', { bubbles: true })));
      setFeedback('Endereço preenchido. Confira o número e os demais dados.', 'success');
      if (fields.street.value) form.querySelector('[name="number"]').focus();
    } catch (error) {
      setFeedback('Não foi possível consultar o CEP. Preencha o endereço manualmente.', 'error');
    } finally {
      postalCode.removeAttribute('aria-busy');
    }
  });
}
