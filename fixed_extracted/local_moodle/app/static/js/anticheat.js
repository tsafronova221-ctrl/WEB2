/**
 * Anti-cheat система для контрольных работ
 * Отслеживает нарушения и отправляет данные на сервер
 */

(function() {
    'use strict';

    // Конфигурация (передается из шаблона)
    const CONFIG = window.ANTICHEAT_CONFIG || {};
    const labIsTest = CONFIG.isTest || false;
    const testDurationMinutes = CONFIG.duration || 0;
    const attemptId = CONFIG.attemptId || 0;

    if (!labIsTest) return;

    // Ключи для localStorage
    const violationsKey = 'attempt_' + attemptId + '_violations';
    const remainingTimeKey = 'attempt_' + attemptId + '_remaining';
    const sessionStartKey = 'attempt_' + attemptId + '_session_start';

    // Состояние
    let tabSwitchCount = 0;
    let copyDetected = false;
    let screenshotAttemptCount = 0;
    let showDesktopAttemptCount = 0;
    let fullscreenExitCount = 0;
    let remainingSeconds = testDurationMinutes * 60;
    let trackingActive = false;
    let initialLoadComplete = false;
    let serverStartTime = Date.now();

    // Инициализация времени
    function initTime() {
        if (CONFIG.serverStartTime) {
            serverStartTime = CONFIG.serverStartTime;
        }
        
        // Проверяем сохраненное время
        const saved = localStorage.getItem(remainingTimeKey);
        if (saved && !CONFIG.remainingTime) {
            const data = JSON.parse(saved);
            const elapsedSinceSave = Math.floor((Date.now() - data.timestamp) / 1000);
            remainingSeconds = Math.max(0, data.value - elapsedSinceSave);
        } else if (CONFIG.remainingTime) {
            remainingSeconds = CONFIG.remainingTime;
        }
    }

    // Форматирование времени
    function formatTime(seconds) {
        const mins = Math.floor(seconds / 60);
        const secs = seconds % 60;
        return String(mins).padStart(2, '0') + ':' + String(secs).padStart(2, '0');
    }

    // Сохранение нарушений
    function saveViolations() {
        localStorage.setItem(violationsKey, JSON.stringify({
            tabSwitches: tabSwitchCount,
            copy: copyDetected,
            screenshotAttempts: screenshotAttemptCount,
            showDesktopAttempts: showDesktopAttemptCount,
            fullscreenExits: fullscreenExitCount
        }));
    }

    // Сохранение оставшегося времени
    function saveRemainingTime() {
        localStorage.setItem(remainingTimeKey, JSON.stringify({
            value: remainingSeconds,
            timestamp: Date.now()
        }));
    }

    // Обновление таймера
    function updateTimer() {
        if (testDurationMinutes <= 0) return;

        if (remainingSeconds > 0) {
            remainingSeconds--;
        }

        saveRemainingTime();

        const timerBox = document.getElementById('timerBox');
        const timeDisplay = document.getElementById('timeRemaining');

        if (timerBox && timeDisplay) {
            if (remainingSeconds <= 0) {
                timerBox.classList.add('warning');
                timeDisplay.textContent = '00:00';
                alert('Время вышло! Работа будет автоматически завершена.');
                submitViolationsAndFinish(true);
                return;
            }

            timerBox.style.display = 'block';
            timeDisplay.textContent = formatTime(remainingSeconds);

            if (remainingSeconds <= 300) {
                timerBox.classList.add('warning');
            }
        }
    }

    // Активация отслеживания
    function activateTracking() {
        if (initialLoadComplete) return;
        initialLoadComplete = true;
        trackingActive = true;
        console.log('Anti-cheat tracking activated');
    }

    // Отслеживание переключений вкладок
    function trackTabSwitches() {
        setTimeout(activateTracking, 2000);
        document.addEventListener('click', activateTracking, { once: true });
        document.addEventListener('keydown', activateTracking, { once: true });

        document.addEventListener('visibilitychange', function() {
            if (!trackingActive || document.hidden) {
                if (document.hidden && trackingActive) {
                    tabSwitchCount++;
                    saveViolations();
                    updateViolationsDisplay();
                }
            }
        });

        window.addEventListener('blur', function() {
            if (!trackingActive || document.hidden) return;
            tabSwitchCount++;
            saveViolations();
            updateViolationsDisplay();
        });
    }

    // Отслеживание копирования
    function trackCopy() {
        document.addEventListener('copy', function(e) {
            copyDetected = true;
            saveViolations();
            showViolationMessage('⚠️ Обнаружено копирование!');
        });

        document.addEventListener('cut', function(e) {
            copyDetected = true;
            saveViolations();
            showViolationMessage('⚠️ Обнаружено вырезание текста!');
        });
    }

    // Отслеживание горячих клавиш
    function trackHotkeys() {
        document.addEventListener('keydown', function(e) {
            // Shift+Win+S (скриншот)
            if (e.shiftKey && e.metaKey && e.key.toLowerCase() === 's') {
                screenshotAttemptCount++;
                saveViolations();
                updateViolationsDisplay();
                showViolationMessage('⚠️ Обнаружена попытка скриншота!');
            }

            // PrintScreen
            if (e.key === 'PrintScreen') {
                screenshotAttemptCount++;
                saveViolations();
                updateViolationsDisplay();
                showViolationMessage('⚠️ Обнаружена попытка скриншота (PrintScreen)!');
            }
        });

        // Отслеживание потери фокуса после Win-комбинаций
        let lastKeyWasWinCombo = false;

        document.addEventListener('keydown', function(e) {
            if (e.metaKey && (e.ctrlKey || e.shiftKey || e.altKey)) {
                lastKeyWasWinCombo = true;
                setTimeout(() => { lastKeyWasWinCombo = false; }, 500);
            }
        });

        window.addEventListener('blur', function() {
            if (!trackingActive || document.hidden) return;
            if (lastKeyWasWinCombo) {
                showDesktopAttemptCount++;
                saveViolations();
                updateViolationsDisplay();
                showViolationMessage('⚠️ Обнаружено переключение рабочего стола!');
            }
        });
    }

    // Отслеживание полноэкранного режима
    function trackFullscreen() {
        document.addEventListener('fullscreenchange', function() {
            if (!document.fullscreenElement) {
                fullscreenExitCount++;
                saveViolations();
            }
        });
    }

    // Отображение нарушений
    function updateViolationsDisplay() {
        const violationsPanel = document.getElementById('violationsPanel');
        if (!violationsPanel) return;

        const totalCount = tabSwitchCount + screenshotAttemptCount + showDesktopAttemptCount;

        if (totalCount > 0) {
            violationsPanel.style.display = 'block';
            violationsPanel.innerHTML = `⚠️ Нарушения: <span id="violationsCount">${totalCount}</span> (вкладки: ${tabSwitchCount}, скриншоты: ${screenshotAttemptCount})`;
        }
    }

    // Показ сообщения о нарушении
    function showViolationMessage(message) {
        const violationsPanel = document.getElementById('violationsPanel');
        if (!violationsPanel) return;

        const originalContent = violationsPanel.innerHTML;
        violationsPanel.innerHTML = message;
        violationsPanel.style.display = 'block';

        setTimeout(() => {
            violationsPanel.innerHTML = originalContent;
            updateViolationsDisplay();
        }, 3000);
    }

    // Отправка данных о нарушениях
    function submitViolationsAndFinish(isAutoFinish) {
        if (!labIsTest) return true;

        const formData = new FormData();
        formData.append('violation_tab_switch', tabSwitchCount);
        formData.append('violation_copy', copyDetected ? '1' : '0');
        formData.append('violation_screenshot', screenshotAttemptCount);
        formData.append('violation_show_desktop', showDesktopAttemptCount);
        formData.append('violation_fullscreen_exit', fullscreenExitCount);

        const finishUrl = isAutoFinish ? '/auto-finish/' + attemptId : '/finish/' + attemptId;

        if (isAutoFinish) {
            return fetch(finishUrl, {
                method: 'POST',
                body: formData
            }).then(response => response.json())
              .then(data => {
                  console.log('Auto-finish result:', data);
                  localStorage.removeItem(violationsKey);
                  localStorage.removeItem(remainingTimeKey);
                  localStorage.removeItem(sessionStartKey);
                  window.location.href = '/finish/' + attemptId;
              })
              .catch(error => {
                  console.error('Error during auto-finish:', error);
                  window.location.href = '/finish/' + attemptId;
              });
        }

        return true;
    }

    // Блокировка контекстного меню
    function disableContextMenu() {
        document.addEventListener('contextmenu', function(e) {
            e.preventDefault();
            return false;
        });
    }

    // Блокировка выделения текста
    function disableTextSelection() {
        document.body.style.userSelect = 'none';
        document.body.style.webkitUserSelect = 'none';
        document.body.style.mozUserSelect = 'none';
        document.body.style.msUserSelect = 'none';
    }

    // Блокировка клавиш F12, Ctrl+Shift+I, Ctrl+Shift+J, Ctrl+U
    function disableDevTools() {
        document.addEventListener('keydown', function(e) {
            // F12
            if (e.key === 'F12') {
                e.preventDefault();
                return false;
            }
            // Ctrl+Shift+I (DevTools)
            if (e.ctrlKey && e.shiftKey && e.key.toLowerCase() === 'i') {
                e.preventDefault();
                return false;
            }
            // Ctrl+Shift+J (Console)
            if (e.ctrlKey && e.shiftKey && e.key.toLowerCase() === 'j') {
                e.preventDefault();
                return false;
            }
            // Ctrl+U (View Source)
            if (e.ctrlKey && e.key.toLowerCase() === 'u') {
                e.preventDefault();
                return false;
            }
            // Ctrl+S (Save Page)
            if (e.ctrlKey && e.key.toLowerCase() === 's') {
                e.preventDefault();
                return false;
            }
            // Ctrl+P (Print)
            if (e.ctrlKey && e.key.toLowerCase() === 'p') {
                e.preventDefault();
                return false;
            }
        });
    }

    // Предотвращение drag & drop
    function disableDragDrop() {
        document.addEventListener('dragstart', function(e) {
            e.preventDefault();
            return false;
        });
    }

    // Инициализация
    function init() {
        initTime();
        
        // Запуск отслеживания
        trackTabSwitches();
        trackCopy();
        trackHotkeys();
        trackFullscreen();
        
        // Защитные меры
        disableContextMenu();
        disableTextSelection();
        disableDevTools();
        disableDragDrop();
        
        // Попытка полного экрана
        const elem = document.documentElement;
        if (elem.requestFullscreen) {
            elem.requestFullscreen().catch(err => {
                console.log('Fullscreen request blocked:', err);
            });
        }

        // Таймер
        updateTimer();
        setInterval(updateTimer, 1000);

        // Обновление отображения
        updateViolationsDisplay();

        // Обработчик отправки формы
        const quizForm = document.getElementById('quizForm');
        if (quizForm) {
            quizForm.addEventListener('submit', function(e) {
                // Добавляем скрытые поля с данными о нарушениях
                const addHiddenField = (name, value) => {
                    const input = document.createElement('input');
                    input.type = 'hidden';
                    input.name = name;
                    input.value = value;
                    this.appendChild(input);
                };

                addHiddenField('violation_tab_switch', tabSwitchCount);
                addHiddenField('violation_copy', copyDetected ? '1' : '0');
                addHiddenField('violation_screenshot', screenshotAttemptCount);
                addHiddenField('violation_show_desktop', showDesktopAttemptCount);
                addHiddenField('violation_fullscreen_exit', fullscreenExitCount);

                // Очищаем localStorage
                localStorage.removeItem(violationsKey);
                localStorage.removeItem(remainingTimeKey);
                localStorage.removeItem(sessionStartKey);
            });
        }
    }

    // Запуск после загрузки DOM
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
