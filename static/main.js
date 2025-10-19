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
            // TODO: Zaktualizuj istniejące wykresy, jeśli są widoczne
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
                
                // Możesz przywrócić confirm, jeśli chcesz
                // if (!confirm("Czy na pewno chcesz usunąć ten raport?")) {
                //     return;
                // }

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
            // Automatyczne wysłanie
            promptForm.dispatchEvent(new Event('submit'));
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

            // Nawet jeśli jest błąd 500, serwer zwróci JSON z HTML-em błędu
            const data = await response.json();

            // 1. Wstrzyknij surowy HTML z serwera
            loadingElement.innerHTML = data.response;
            
            // 2. Znajdź i wyrenderuj wykresy wewnątrz wstrzykniętego HTML
            renderChartsInResponse(loadingElement);

            // 3. Znajdź bloki .markdown-content i sparsuj je
            loadingElement.querySelectorAll('.markdown-content').forEach(el => {
                // Pobieramy treść z <pre> w środku, aby zachować formatowanie
                const preElement = el.querySelector('pre');
                const content = preElement ? preElement.textContent : el.textContent;
                el.innerHTML = marked.parse(content || '');
            });

            // 4. Zaktualizuj ikony Lucide w nowej wiadomości
            lucide.createIcons({ context: loadingElement });
            
            // 5. Dodaj nowy element do historii
            if (data.new_history_item) {
                const newHistoryItem = document.createElement('a');
                newHistoryItem.href = '#'; // TODO: Zaimplementuj ładowanie historii
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
                lucide.createIcons({ context: newHistoryItem });
            }

        } catch (error) {
            console.error('Błąd:', error);
            loadingElement.innerHTML = `<div class="report-error"><p>Wystąpił krytyczny błąd: ${error.message}. Spróbuj ponownie.</p></div>`;
        }
    });

    // --- NOWA FUNKCJA: Renderowanie wykresów ---
    function renderChartsInResponse(containerElement) {
        const chartCanvases = containerElement.querySelectorAll('canvas[data-chart-config]');
        
        chartCanvases.forEach(canvas => {
            try {
                const configString = canvas.dataset.chartConfig;
                if (!configString) return;

                const config = JSON.parse(configString);
                
                // Pobierz opcje motywu
                const themeOptions = getChartThemeOptions();
                
                // Zastosuj kolory motywu do konfiguracji wykresu
                // Używamy "głębokiego" łączenia, aby nie nadpisać istniejących opcji
                config.options = {
                    ...config.options,
                    plugins: {
                        ...config.options.plugins,
                        title: { ...config.options.plugins.title, ...themeOptions.plugins.title },
                        legend: { ...config.options.plugins.legend, ...themeOptions.plugins.legend }
                    },
                    scales: {
                        x: { ...config.options.scales.x, ...themeOptions.scales.axis },
                        y: { ...config.options.scales.y, ...themeOptions.scales.axis }
                    }
                };

                new Chart(canvas, config);

            } catch (e) {
                console.error("Błąd renderowania wykresu:", e);
                canvas.parentElement.innerHTML = `<p class="report-error">Nie udało się załadować wykresu.</p>`;
            }
        });
    }

    // --- NOWA FUNKCJA: Helper do kolorów motywu ---
    function getChartThemeOptions() {
        const isDarkMode = document.documentElement.classList.contains('dark-mode');
        const gridColor = isDarkMode ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)';
        const textColor = isDarkMode ? '#E3E3E3' : '#202124';
        const secondaryTextColor = isDarkMode ? '#9B9B9B' : '#5F6368';

        return {
            plugins: {
                title: {
                    color: textColor
                },
                legend: {
                    labels: {
                        color: textColor
                    }
                }
            },
            scales: {
                axis: {
                    grid: {
                        color: gridColor
                    },
                    ticks: {
                        color: secondaryTextColor
                    },
                    title: {
                        color: secondaryTextColor
                    }
                }
            }
        };
    }


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
            // Ten scenariusz jest teraz obsługiwany przez 'submit'
            // Ale zostawiamy dla ewentualnych przyszłych zastosowań
            htmlContent = `
                <div class="message-avatar ai-avatar">
                    <i data-lucide="bar-chart-3"></i>
                </div>
                <div class="message-content">${content}</div>
            `;
        } else if (role === 'ai' && !content) {
            // Loader
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
        lucide.createIcons({ context: messageElement }); 
        
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