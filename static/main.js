// Czekamy, aż cała strona (HTML) się załaduje
document.addEventListener('DOMContentLoaded', () => {

    // Inicjalizacja ikon Lucide
    lucide.createIcons();

    // --- LOGIKA PRZEŁĄCZNIKA MOTYWU (THEME TOGGLER) ---
    const themeToggleBtn = document.getElementById('theme-toggle-btn');
    
    if (themeToggleBtn) {
        themeToggleBtn.addEventListener('click', () => {
            document.documentElement.classList.toggle('dark-mode');
            const isDarkMode = document.documentElement.classList.contains('dark-mode');
            localStorage.setItem('theme', isDarkMode ? 'dark' : 'light');
        });
    }
    // --- KONIEC LOGIKI MOTYWU ---


    // --- Obsługa UI (Sidebar) ---
    const sidebar = document.getElementById('sidebar');
    const sidebarToggle = document.getElementById('sidebar-toggle');
    const mainContent = document.getElementById('main-content');

    if (sidebarToggle) {
        sidebarToggle.addEventListener('click', () => {
            sidebar.classList.toggle('open');
        });
    }

    if (mainContent) {
        mainContent.addEventListener('click', () => {
            if (window.innerWidth < 768 && sidebar.classList.contains('open')) {
                sidebar.classList.remove('open');
            }
        });
    }

    const historyList = document.getElementById('history-list');

    // --- Logika usuwania raportów z historii ---
    if (historyList) {
        historyList.addEventListener('click', async (e) => {
            
            const deleteButton = e.target.closest('.delete-history-btn');

            if (deleteButton) {
                e.preventDefault();
                e.stopPropagation();

                const historyItem = deleteButton.closest('.history-item');
                const reportId = historyItem.dataset.id;

                // USUNIĘTO OKNO POTWIERDZENIA (confirm)
                // Usunięcie nastąpi natychmiast po kliknięciu.

                try {
                    const response = await fetch(`/api/report/delete/${reportId}`, {
                        method: 'DELETE',
                        headers: {
                            'Content-Type': 'application/json'
                        }
                    });

                    if (response.ok) {
                        historyItem.remove();
                    } else {
                        const data = await response.json();
                        console.error('Błąd podczas usuwania raportu:', data.error || 'Nieznany błąd');
                        alert('Nie udało się usunąć raportu.');
                    }
                } catch (error) {
                    console.error('Błąd sieci:', error);
                    alert('Wystąpił błąd sieci. Nie można usunąć raportu.');
                }
            }
        });
    }


    // --- Obsługa formularza (AJAX/Fetch) ---
    const promptForm = document.getElementById('prompt-form');
    const promptInput = document.getElementById('prompt-input');
    const sendButton = document.getElementById('send-btn');
    const messageList = document.getElementById('message-list');
    const welcomeMessage = document.getElementById('welcome-message');

    if (!promptForm) return;

    // Automatyczne dostosowanie wysokości pola textarea
    promptInput.addEventListener('input', () => {
        promptInput.style.height = 'auto';
        promptInput.style.height = (promptInput.scrollHeight) + 'px';
        sendButton.disabled = !promptInput.value.trim();
    });
    sendButton.disabled = true; 

    // --- Obsługa sugerowanych promptów ---
    document.querySelectorAll('.prompt-suggestion').forEach(button => {
        button.addEventListener('click', () => {
            const promptText = button.textContent;
            promptInput.value = promptText;
            promptInput.dispatchEvent(new Event('input')); 
            sendButton.disabled = false;
            promptInput.focus();
        });
    });


    // --- Główna funkcja wysyłania promptu ---
    promptForm.addEventListener('submit', async (e) => {
        e.preventDefault(); 
        
        const promptText = promptInput.value.trim();
        if (!promptText) return;

        if (welcomeMessage) {
            welcomeMessage.style.display = 'none';
        }

        addMessageToUI('user', promptText);

        const originalHeight = promptInput.style.height;
        promptInput.value = '';
        promptInput.style.height = originalHeight;
        sendButton.disabled = true;

        const loadingElement = addMessageToUI('ai', null); 

        try {
            const response = await fetch('/api/prompt', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ prompt: promptText }),
            });

            if (!response.ok) {
                throw new Error(`Błąd serwera: ${response.statusText}`);
            }

            const data = await response.json();

            loadingElement.innerHTML = marked.parse(data.response);
            
            const newHistoryItem = document.createElement('a');
            newHistoryItem.href = '#';
            newHistoryItem.className = 'history-item';
            newHistoryItem.dataset.id = data.new_history_item.id;
            
            newHistoryItem.innerHTML = `
                <i data-lucide="message-square"></i>
                <span>${data.new_history_item.title}</span>
                <button class="delete-history-btn" title="Usuń raport">
                    <i data-lucide="trash-2"></i>
                </button>
            `;

            if (historyList) {
                historyList.prepend(newHistoryItem);
            }
            lucide.createIcons();

        } catch (error) {
            console.error('Błąd:', error);
            loadingElement.innerHTML = `<span class="error">Wystąpił błąd. Spróbuj ponownie.</span>`;
        }
    });

    // Funkcja pomocnicza do dodawania wiadomości
    function addMessageToUI(role, content) {
        const messageElement = document.createElement('div');
        messageElement.classList.add('message', `role-${role}`);
        
        let htmlContent = '';
        
        if (role === 'user') {
            htmlContent = `
                <div class="message-avatar user-avatar">
                    <i data-lucide="user"></i>
                </div>
                <div class="message-content">${content.replace(/\n/g, '<br>')}</div>
            `;
        } else if (role === 'ai' && content) {
            htmlContent = `
                <div class="message-avatar ai-avatar">
                    <i data-lucide="bar-chart-3"></i>
                </div>
                <div class="message-content">${marked.parse(content)}</div>
            `;
        } else if (role === 'ai' && !content) {
            htmlContent = `
                <div class="message-avatar ai-avatar">
                    <i data-lucide="bar-chart-3"></i>
                </div>
                <div class="message-content">
                    <div class="loading-spinner"></div>
                </div>
            `;
        }
        
        messageElement.innerHTML = htmlContent;
        messageList.appendChild(messageElement);
        lucide.createIcons(); 
        
        messageList.scrollTop = messageList.scrollHeight;
        
        if (role === 'ai') {
            return messageElement.querySelector('.message-content');
        }
    }

    // Obsługa naciśnięcia Enter (bez Shift) do wysyłania
    promptInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            promptForm.dispatchEvent(new Event('submit'));
        }
    });

});