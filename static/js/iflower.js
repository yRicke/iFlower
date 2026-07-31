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

  document.querySelectorAll('[data-image-upload]').forEach(setupImagePreview);
});

function setupImagePreview(container) {
  const input = container.querySelector('[data-image-input]');
  const preview = container.querySelector('[data-image-preview]');
  const placeholder = container.querySelector('[data-image-placeholder]');
  const badge = container.querySelector('[data-image-badge]');
  const filename = container.querySelector('[data-image-filename]');
  const feedback = container.querySelector('[data-image-feedback]');
  const clear = container.querySelector('[data-image-clear]');
  const originalSrc = preview.dataset.originalSrc;
  let objectUrl = '';

  const showImage = (src, label) => {
    preview.src = src;
    preview.hidden = false;
    placeholder.hidden = true;
    badge.textContent = label;
  };

  const showEmpty = (label = 'Sem imagem') => {
    preview.removeAttribute('src');
    preview.hidden = true;
    placeholder.hidden = false;
    badge.textContent = label;
  };

  const restoreOriginal = () => {
    if (originalSrc) showImage(originalSrc, 'Imagem atual');
    else showEmpty();
    filename.textContent = 'Nenhum arquivo novo selecionado';
    feedback.textContent = '';
  };

  input.addEventListener('change', () => {
    const file = input.files && input.files[0];
    if (!file) {
      restoreOriginal();
      return;
    }
    if (!file.type.startsWith('image/')) {
      input.value = '';
      restoreOriginal();
      feedback.textContent = 'Escolha um arquivo de imagem válido.';
      feedback.dataset.state = 'error';
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      input.value = '';
      restoreOriginal();
      feedback.textContent = 'A imagem deve ter no máximo 5 MB.';
      feedback.dataset.state = 'error';
      return;
    }
    if (objectUrl) URL.revokeObjectURL(objectUrl);
    objectUrl = URL.createObjectURL(file);
    showImage(objectUrl, 'Nova imagem');
    filename.textContent = file.name;
    feedback.textContent = `${(file.size / 1024 / 1024).toFixed(2)} MB • prévia pronta para salvar`;
    feedback.dataset.state = 'success';
    if (clear) clear.checked = false;
  });

  if (clear) {
    clear.addEventListener('change', () => {
      if (clear.checked) {
        input.value = '';
        showEmpty('Será removida');
        filename.textContent = 'A imagem atual será removida';
        feedback.textContent = 'Salve o formulário para confirmar a remoção.';
        feedback.dataset.state = 'warning';
      } else {
        restoreOriginal();
      }
    });
  }
}

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
