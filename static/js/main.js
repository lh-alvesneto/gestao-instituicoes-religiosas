/**
 * IPVP — main.js  (v2.0 — Refatoração DRY)
 *
 * Módulo central unificado. Todos os comportamentos são ativados por
 * data-attributes nos elementos HTML, sem lógica inline nos templates.
 *
 * Inicialização: evento `turbo:load` (compatível com @hotwired/turbo 8.x)
 *
 * ÍNDICE DE MÓDULOS:
 *  0. Utilitários base
 *  1. Sistema de Toasts
 *  2. Auto-submit de busca  (.js-search)
 *  3. Contador de caracteres  (maxlength + #counter-{id})
 *  4. Seletor de linhas por página  ([data-action="per-page-change"])
 *  5. Bloqueio de formulário no submit  ([data-lock-submit])
 *  6. Modal de confirmação genérico + Fetch DELETE/PATCH
 *  7. Autocomplete  ([data-autocomplete-url])
 *  8. Visor de status (dropdown)  ([data-status-visor])
 *  9. Controle de quantidade +/-  ([data-qty-delta])
 * 10. Upload e preview de imagens  ([data-image-upload])
 * 11. Força e correspondência de senha
 */

(() => {
  'use strict';

  // ==========================================================================
  // 0. UTILITÁRIOS BASE
  // ==========================================================================

  /** Lê o CSRF token injetado no <meta> pelo base.html */
  const getCsrf = () =>
    document.querySelector('meta[name="csrf-token"]')?.content ?? '';

  /** Atrasa a execução de `fn` por `ms` milissegundos */
  const debounce = (fn, ms = 500) => {
    let timer;
    return (...args) => { clearTimeout(timer); timer = setTimeout(() => fn(...args), ms); };
  };

  const $  = (sel, ctx = document) => ctx.querySelector(sel);
  const $$ = (sel, ctx = document) => [...ctx.querySelectorAll(sel)];

  /**
   * Faz uma requisição JSON com CSRF token e retorna { ok, data }.
   * Centraliza o tratamento de erros de rede para todos os módulos.
   */
  const fetchJSON = async (url, method = 'GET', body = null) => {
    try {
      const opts = {
        method,
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrf() },
      };
      if (body) opts.body = JSON.stringify(body);
      const res = await fetch(url, opts);
      const data = res.headers.get('content-type')?.includes('application/json')
        ? await res.json()
        : {};
      return { ok: res.ok, status: res.status, data };
    } catch (err) {
      console.error('[IPVP] fetchJSON error:', err);
      return { ok: false, status: 0, data: {} };
    }
  };


  // ==========================================================================
  // 1. SISTEMA DE TOASTS
  //
  // Uso programático em qualquer lugar: window.IPVP.toast('Salvo!', 'success')
  // Tipos: 'success' | 'danger' | 'warning' | 'info'
  //
  // Substitui os `alert()` nativos e futuros flash messages inline.
  // Requer o <div class="toast-container ..."> já presente no base.html.
  // ==========================================================================

  function initToasts() {
    const container = $('.toast-container');
    if (!container) return;

    window.IPVP = window.IPVP || {};
    window.IPVP.toast = (message, type = 'info') => {
      const icons = {
        success: 'check-circle-fill',
        danger:  'exclamation-triangle-fill',
        warning: 'exclamation-circle-fill',
        info:    'info-circle-fill',
      };
      const el = document.createElement('div');
      el.className = `toast align-items-center text-bg-${type} border-0 shadow-lg`;
      el.setAttribute('role', 'alert');
      el.setAttribute('aria-live', 'assertive');
      el.innerHTML = `
        <div class="d-flex">
          <div class="toast-body d-flex align-items-center gap-2">
            <i class="bi bi-${icons[type] ?? 'info-circle-fill'} flex-shrink-0"></i>
            <span>${message}</span>
          </div>
          <button type="button" class="btn-close btn-close-white me-2 m-auto"
                  data-bs-dismiss="toast" aria-label="Fechar"></button>
        </div>`;
      container.appendChild(el);
      const toast = new bootstrap.Toast(el, { delay: 4500 });
      toast.show();
      el.addEventListener('hidden.bs.toast', () => el.remove());
    };
  }


  // ==========================================================================
  // 2. AUTO-SUBMIT DE BUSCA (debounced)
  //
  // Aplica-se a: <input class="js-search" form="searchForm">
  //   ou qualquer <input class="js-search"> dentro de um <form>.
  //
  // Também restaura o cursor ao final do texto após reload do Turbo.
  //
  // Substitui blocos idênticos em:
  //   materiais.html, manutencao.html, usuarios.html, auditoria.html
  // ==========================================================================

  function initAutoSearch() {
    $$('input.js-search').forEach(input => {
      // Restaura cursor ao final (evita cursor no início após Turbo reload)
      if (input.value) {
        const val = input.value;
        input.value = '';
        input.value = val;
      }

      const form = input.form ?? input.closest('form');
      if (!form) return;

      input.addEventListener(
        'input',
        debounce(() => form.submit(), 500)
      );
    });
  }


  // ==========================================================================
  // 3. CONTADOR DE CARACTERES
  //
  // Aplica-se a qualquer campo com maxlength="" que tenha um elemento irmão
  // (ou próximo) com id="counter-{campo_id}".
  //
  // O macro `render_campo` em components.html já gera essa estrutura.
  // Substitui o bloco `querySelectorAll('[maxlength]')` em 3 arquivos de form.
  // ==========================================================================

  function initCharCounters() {
    $$('input[maxlength], textarea[maxlength]').forEach(field => {
      const max     = parseInt(field.getAttribute('maxlength'), 10);
      const counter = $(`#counter-${field.id}`);
      if (!counter) return;

      const update = () => {
        const len = field.value.length;
        counter.textContent = `${len}/${max}`;
        const isNearLimit = len >= max * 0.9;
        counter.classList.toggle('char-counter--warning', isNearLimit);
      };

      field.addEventListener('input', update);
      update(); // estado inicial (importante para campos pré-preenchidos)
    });
  }


  // ==========================================================================
  // 4. SELETOR DE LINHAS POR PÁGINA
  //
  // Aplica-se a: <select data-action="per-page-change" data-form-target="formId">
  // Ao mudar, atualiza o <input id="perPageHidden"> e submete o form.
  //
  // O macro `render_per_page_selector` em components.html já gera essa estrutura.
  // Substitui listeners idênticos em: materiais.html, manutencao.html,
  //   usuarios.html, auditoria.html
  // ==========================================================================

  function initPerPageSelector() {
    $$('[data-action="per-page-change"]').forEach(select => {
      select.addEventListener('change', function () {
        const formId  = this.dataset.formTarget ?? 'searchForm';
        const form    = $(`#${formId}`);
        const hidden  = $(`#perPageHidden`);
        if (hidden) hidden.value = this.value;
        if (form)   form.submit();
      });
    });
  }


  // ==========================================================================
  // 5. BLOQUEIO DE FORMULÁRIO NO SUBMIT (anti double-submit)
  //
  // Aplica-se a: <form data-lock-submit>
  // No submit, o botão [type=submit] exibe um spinner e fica desabilitado.
  //
  // Substitui blocos idênticos em:
  //   form_manutencao.html, form_material.html, form_usuario.html
  // ==========================================================================

  function initFormLock() {
    $$('form[data-lock-submit]').forEach(form => {
      form.addEventListener('submit', function () {
        if (!this.checkValidity()) return;
        const btn = this.querySelector('[type="submit"]');
        if (!btn) return;
        btn.innerHTML =
          '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>Processando...';
        btn.style.pointerEvents = 'none';
        btn.style.opacity = '0.7';
      });
    });
  }


  // ==========================================================================
  // 6. MODAL DE CONFIRMAÇÃO GENÉRICO + FETCH DELETE / PATCH
  //
  // Requer em base.html: <div id="modal-confirmacao"> (ver instruções abaixo)
  //
  // ── DELETE ──────────────────────────────────────────────────────────────
  // <button data-action="confirm-delete"
  //         data-url="/api/materiais/5"
  //         data-title="Excluir Solicitação"
  //         data-message="Remover <strong>Papel A4</strong>?"
  //         data-confirm-label="Excluir"
  //         data-confirm-class="btn-danger"
  //         data-redirect="/materiais">   ← opcional; se omitido: reload
  //
  // ── PATCH (mudança de status) ────────────────────────────────────────────
  // <button data-action="confirm-patch"
  //         data-url="/api/materiais/5/status"
  //         data-body='{"novo_status":"cancelado"}'
  //         data-title="Cancelar Pedido"
  //         data-message="Deseja realmente cancelar?"
  //         data-confirm-label="Cancelar"
  //         data-confirm-class="btn-danger">
  //
  // Substitui todos os modais e confirm() específicos espalhados em:
  //   materiais.html, manutencao.html, detalhe_material.html, detalhe_chamado.html
  // ==========================================================================

  function initConfirmModal() {
    const modal = $('#modal-confirmacao');
    if (!modal) return;

    const bsModal     = new bootstrap.Modal(modal);
    const titleEl     = $('#mc-title',   modal);
    const bodyEl      = $('#mc-body',    modal);
    const confirmBtn  = $('#mc-confirm', modal);

    // Abre o modal ao clicar em botões com data-action="confirm-delete|patch"
    document.addEventListener('click', e => {
      const btn = e.target.closest('[data-action="confirm-delete"],[data-action="confirm-patch"]');
      if (!btn) return;

      const { action, url, body, title, message, confirmLabel, confirmClass, redirect } = btn.dataset;

      titleEl.textContent   = title   ?? 'Confirmar ação';
      bodyEl.innerHTML      = message ?? 'Deseja continuar?';
      confirmBtn.textContent = confirmLabel ?? 'Confirmar';
      confirmBtn.className  = `btn ${confirmClass ?? 'btn-primary'} px-4 fw-bold`;

      // Remove listener anterior para não acumular
      const newBtn = confirmBtn.cloneNode(true);
      confirmBtn.replaceWith(newBtn);

      newBtn.addEventListener('click', async () => {
        newBtn.disabled = true;
        newBtn.innerHTML =
          '<span class="spinner-border spinner-border-sm me-2"></span>Processando...';

        const method  = action === 'confirm-delete' ? 'DELETE' : 'PATCH';
        const payload = body ? JSON.parse(body) : null;
        const result  = await fetchJSON(url, method, payload);

        if (result.ok) {
          bsModal.hide();
          if (redirect) window.location.href = redirect;
          else          window.location.reload();
        } else {
          const msg = result.data?.erro ?? 'Ocorreu um erro. Tente novamente.';
          window.IPVP?.toast(msg, 'danger');
          newBtn.disabled  = false;
          newBtn.textContent = confirmLabel ?? 'Confirmar';
        }
      });

      bsModal.show();
    });
  }


  // ==========================================================================
  // 7. AUTOCOMPLETE
  //
  // Aplica-se a: <input data-autocomplete-url="/api/..."
  //                     data-autocomplete-icon="geo-alt">
  //
  // O container pai deve ter `position: relative` para o dropdown posicionar.
  // Substitui a lógica duplicada em: form_manutencao.html, form_material.html
  // ==========================================================================

  function initAutocomplete() {
    $$('[data-autocomplete-url]').forEach(input => {
      const apiUrl  = input.dataset.autocompleteUrl;
      const icon    = input.dataset.autocompleteIcon ?? 'search';
      const box     = $(`#${input.id}-suggestions`);
      const spinner = $(`#${input.id}-loading`);
      if (!box) return;

      const showBox = items => {
        box.innerHTML = '';
        if (!items.length) { box.classList.remove('show'); return; }
        items.forEach(item => {
          const div = document.createElement('div');
          div.className = 'autocomplete-item text-truncate';
          div.innerHTML = `<i class="bi bi-${icon} me-2" style="opacity:0.6"></i>${item}`;
          div.addEventListener('mousedown', e => {
            e.preventDefault(); // evita blur do input antes do clique registrar
            input.value = item;
            box.classList.remove('show');
            input.dispatchEvent(new Event('input'));
          });
          box.appendChild(div);
        });
        box.classList.add('show');
      };

      const fetchSuggestions = debounce(async val => {
        spinner?.classList.remove('d-none');
        try {
          const res = await fetch(`${apiUrl}?q=${encodeURIComponent(val)}`);
          if (res.ok) showBox(await res.json());
        } catch { /* silencioso */ } finally {
          spinner?.classList.add('d-none');
        }
      }, 300);

      input.addEventListener('input', () => {
        if (input.value.trim().length < 2) { box.classList.remove('show'); return; }
        fetchSuggestions(input.value.trim());
      });

      input.addEventListener('focus', () => {
        if (input.value.trim().length >= 2 && box.children.length) {
          box.classList.add('show');
        }
      });

      document.addEventListener('click', e => {
        if (!input.contains(e.target) && !box.contains(e.target)) {
          box.classList.remove('show');
        }
      });
    });
  }


  // ==========================================================================
  // 8. VISOR DE STATUS (dropdown de mudança de estado)
  //
  // Aplica-se a: <a data-action="status-option"
  //                 data-value="concluido"
  //                 data-html="<span...>● Concluído</span>"
  //                 data-target-visor="statusVisor"
  //                 data-target-input="novo_status">
  //
  // Substitui o `querySelectorAll('.opt-status')` em:
  //   detalhe_chamado.html, detalhe_material.html
  // ==========================================================================

  function initStatusVisor() {
    document.addEventListener('click', e => {
      const opt = e.target.closest('[data-action="status-option"]');
      if (!opt) return;
      e.preventDefault();

      const visor = $(`#${opt.dataset.targetVisor}`);
      const input = $(`#${opt.dataset.targetInput}`);
      if (visor) visor.innerHTML = opt.dataset.html;
      if (input) input.value     = opt.dataset.value;
    });
  }


  // ==========================================================================
  // 9. CONTROLE DE QUANTIDADE +/-
  //
  // Aplica-se a: <button data-action="qty-change"
  //                      data-target="qtdInput"
  //                      data-delta="1">
  //
  // Substitui a função `window.mudarQtd` de form_material.html.
  // ==========================================================================

  function initQtyControl() {
    document.addEventListener('click', e => {
      const btn = e.target.closest('[data-action="qty-change"]');
      if (!btn) return;
      const input = $(`#${btn.dataset.target}`);
      if (!input) return;
      const delta = parseInt(btn.dataset.delta, 10) || 0;
      input.value = Math.max(1, (parseInt(input.value, 10) || 1) + delta);
    });
  }


  // ==========================================================================
  // 10. UPLOAD E PREVIEW DE IMAGENS (drag & drop)
  //
  // Aplica-se a: <div data-image-upload
  //                   data-input="imagens"
  //                   data-preview="preview-container"
  //                   data-max-files="4"
  //                   data-max-size-mb="10">
  //
  // Substitui o bloco de ~80 linhas do final de form_manutencao.html.
  // ==========================================================================

  function initImageUpload() {
    $$('[data-image-upload]').forEach(zone => {
      const inputId    = zone.dataset.input ?? 'imagens';
      const previewId  = zone.dataset.preview ?? 'preview-container';
      const maxFiles   = parseInt(zone.dataset.maxFiles  ?? '4',  10);
      const maxSizeMb  = parseInt(zone.dataset.maxSizeMb ?? '10', 10);
      const maxBytes   = maxSizeMb * 1024 * 1024;

      const fileInput = $(`#${inputId}`);
      const preview   = $(`#${previewId}`);
      if (!fileInput || !preview) return;

      const dt = new DataTransfer();

      const toast = msg => window.IPVP?.toast(msg, 'danger') ?? alert(msg);

      const addFiles = newFiles => {
        const valid = [...newFiles].filter(f =>
          f.type.startsWith('image/') &&
          ![...dt.files].some(x => x.name === f.name && x.size === f.size)
        );
        if (!valid.length) return;

        const totalCount = dt.files.length + valid.length;
        const totalSize  = [...dt.files, ...valid].reduce((s, f) => s + f.size, 0);

        if (totalCount > maxFiles) {
          toast(`Limite de ${maxFiles} fotos atingido. Nenhuma nova foto adicionada.`);
          fileInput.files = dt.files;
          return;
        }
        if (totalSize > maxBytes) {
          toast(`Tamanho total excede ${maxSizeMb} MB. Tente imagens com menor resolução.`);
          fileInput.files = dt.files;
          return;
        }
        valid.forEach(f => dt.items.add(f));
        fileInput.files = dt.files;
        renderPreviews();
      };

      const renderPreviews = () => {
        preview.innerHTML = '';
        [...fileInput.files].forEach((file, idx) => {
          const reader = new FileReader();
          reader.onload = ({ target }) => {
            const wrap = document.createElement('div');
            wrap.className = 'position-relative d-inline-block mt-2';
            wrap.innerHTML = `
              <img src="${target.result}"
                   class="img-thumbnail shadow-sm"
                   style="width:90px;height:90px;object-fit:cover;border-radius:8px;">
              <button type="button"
                      class="btn btn-danger btn-sm position-absolute shadow d-flex
                             align-items-center justify-content-center"
                      style="top:-8px;right:-8px;width:24px;height:24px;
                             border-radius:50%;padding:0;"
                      aria-label="Remover foto">
                <i class="bi bi-x" style="font-size:1.1rem;line-height:1;"></i>
              </button>`;
            wrap.querySelector('button').addEventListener('click', e => {
              e.stopPropagation();
              dt.items.remove(idx);
              fileInput.files = dt.files;
              renderPreviews();
            });
            preview.appendChild(wrap);
          };
          reader.readAsDataURL(file);
        });
      };

      zone.addEventListener('click', () => fileInput.click());
      zone.addEventListener('dragover', e => {
        e.preventDefault();
        zone.style.borderColor     = 'var(--color-primary-800)';
        zone.style.backgroundColor = '#ECFDF5';
      });
      zone.addEventListener('dragleave', e => {
        e.preventDefault();
        zone.style.borderColor     = 'var(--color-neutral-300)';
        zone.style.backgroundColor = 'var(--color-neutral-50)';
      });
      zone.addEventListener('drop', e => {
        e.preventDefault();
        zone.style.borderColor     = 'var(--color-neutral-300)';
        zone.style.backgroundColor = 'var(--color-neutral-50)';
        if (e.dataTransfer.files.length) addFiles(e.dataTransfer.files);
      });
      fileInput.addEventListener('change', () => addFiles(fileInput.files));
    });
  }


  // ==========================================================================
  // 11. FORÇA E CORRESPONDÊNCIA DE SENHA
  //
  // Aplica-se a:
  //   <input id="nova_senha"      data-password-strength>
  //   <input id="confirma_senha"  data-password-match="nova_senha">
  //
  // Substitui o bloco no final de perfil.html.
  // ==========================================================================

  function initPasswordUI() {
    const novaSenha = $('[data-password-strength]');
    if (novaSenha) {
      const strengthEl = $(`#${novaSenha.dataset.passwordStrength || 'senha-strength'}`);
      if (strengthEl) {
        novaSenha.addEventListener('input', () => {
          const v = novaSenha.value;
          if (!v) { strengthEl.textContent = ''; return; }
          let score = 0;
          if (v.length >= 8)         score++;
          if (/[A-Z]/.test(v))       score++;
          if (/[0-9]/.test(v))       score++;
          if (/[^A-Za-z0-9]/.test(v)) score++;
          const labels = ['Muito fraca', 'Fraca', 'Média', 'Forte', 'Excelente'];
          const colors = ['#DC2626', '#EA580C', '#D97706', '#059669', '#0284C7'];
          strengthEl.textContent  = labels[score];
          strengthEl.style.color  = colors[score];
        });
      }
    }

    const confirmaSenha = $('[data-password-match]');
    if (confirmaSenha) {
      const targetId = confirmaSenha.dataset.passwordMatch;
      const matchEl  = $(`#${confirmaSenha.dataset.passwordMatchOutput || 'senha-match'}`);
      const target   = $(`#${targetId}`);
      if (matchEl && target) {
        confirmaSenha.addEventListener('input', () => {
          if (!confirmaSenha.value) { matchEl.textContent = ''; return; }
          const match = confirmaSenha.value === target.value;
          matchEl.textContent = match ? 'As senhas coincidem' : 'As senhas não coincidem';
          matchEl.style.color = match ? '#059669' : '#DC2626';
        });
      }
    }
  }


  // ==========================================================================
  // INICIALIZAÇÃO CENTRAL
  // Executada em cada navegação do Turbo (substitui DOMContentLoaded simples)
  // ==========================================================================

  const init = () => {
    initToasts();
    initAutoSearch();
    initCharCounters();
    initPerPageSelector();
    initFormLock();
    initConfirmModal();
    initAutocomplete();
    initStatusVisor();
    initQtyControl();
    initImageUpload();
    initPasswordUI();
  };

  // Turbo dispara 'turbo:load' em cada visita (initial + navegação SPA)
  document.addEventListener('turbo:load', init);

  // Fallback para páginas sem Turbo (ex: login.html que não extends base.html)
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();
