'use strict';
(function () {
  const el = id => document.getElementById(id);
  const form = el('ai-form');
  const input = el('ai-question');
  const thread = el('ai-thread');
  const send = el('ai-send');
  const suggestions = el('ai-suggestions');

  function message(role, text, footer) {
    const bubble = document.createElement('div');
    bubble.className = 'ai-bubble ' + role;
    const speaker = document.createElement('div');
    speaker.className = 'ai-speaker';
    speaker.textContent = role === 'user' ? 'RESEARCHER' : 'AXOVAR INTELLIGENCE';
    const body = document.createElement('div');
    body.className = 'ai-body';
    body.textContent = text;
    bubble.append(speaker, body);
    if (footer) {
      const meta = document.createElement('div');
      meta.className = 'ai-meta';
      meta.textContent = footer;
      bubble.append(meta);
    }
    thread.append(bubble);
    thread.scrollTop = thread.scrollHeight;
    return bubble;
  }

  async function jsonRequest(path, body) {
    const response = await fetch(path, body === undefined ? undefined : {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Request failed');
    return data;
  }

  async function initialize() {
    try {
      const status = await jsonRequest('/api/intelligence/status');
      el('ai-mode').textContent = status.available ? 'LOCAL MODEL READY' : 'EVIDENCE ONLY';
      el('ai-model-name').textContent = status.available ? status.model : 'Deterministic evidence explanation';
      el('ai-model-help').textContent = status.available
        ? 'Local ' + status.model + ' is available through Ollama. Model answers are unverified commentary.'
        : 'Ollama model not found. Questions about the current replay work in evidence-only mode. For broader Q&A install Ollama and run: ollama pull gemma3:4b';
      for (const example of status.examples) {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'ai-suggestion';
        button.textContent = example;
        button.addEventListener('click', () => { input.value = example; input.focus(); });
        suggestions.append(button);
      }
    } catch (error) {
      el('ai-mode').textContent = 'UNAVAILABLE';
      el('ai-model-help').textContent = 'Unable to check the local research service.';
    }
  }

  form.addEventListener('submit', async event => {
    event.preventDefault();
    if (send.disabled) return;
    const question = input.value.trim();
    if (question.length < 2 || question.length > 1000) return;
    message('user', question);
    input.value = '';
    send.disabled = true;
    send.textContent = 'Analyzing...';
    try {
      const answer = await jsonRequest('/api/intelligence/ask', {
        question, use_model: el('ai-use-model').checked
      });
      const sourceLabel = answer.evidence_ids.length
        ? 'Evidence: ' + answer.evidence_ids.join(', ')
        : 'No supporting event IDs available at this replay step';
      message('assistant', answer.answer,
        (answer.mode === 'local-model' ? 'Local model ' + answer.model : 'Deterministic evidence explanation') +
        ' · ' + answer.scenario + ' · Step ' + answer.step + ' · ' + sourceLabel);
    } catch (error) {
      message('assistant', 'Unable to answer: ' + error.message, 'No financial decision was changed');
    } finally {
      send.disabled = false;
      send.textContent = 'Analyze question →';
    }
  });

  initialize();
})();
