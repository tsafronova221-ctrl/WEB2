/**
 * Anti-cheat система для контрольных работ
 * ВНИМАНИЕ: Вся критическая логика проверки на сервере!
 * Этот скрипт только отслеживает события и отправляет их на сервер
 */
(function() {
    'use strict';
    
    var _0x4d6f = (function() {
        var _0x1a2b = ['\x6c\x6f\x67', '\x74\x61\x62\x53\x77\x69\x74\x63\x68\x65\x73', '\x76\x69\x6f\x6c\x61\x74\x69\x6f\x6e\x73', '\x63\x6f\x70\x79', '\x73\x63\x72\x65\x65\x6e\x73\x68\x6f\x74\x41\x74\x74\x65\x6d\x70\x74\x73', '\x73\x68\x6f\x77\x44\x65\x73\x6b\x74\x6f\x70\x41\x74\x74\x65\x6d\x70\x74\x73', '\x66\x75\x6c\x6c\x73\x63\x72\x65\x65\x6e\x45\x78\x69\x74\x73', '\x72\x65\x6d\x61\x69\x6e\x69\x6e\x67', '\x74\x69\x6d\x65\x73\x74\x61\x6d\x70', '\x61\x74\x74\x65\x6d\x70\x74\x5f', '\x5f\x76\x69\x6f\x6c\x61\x74\x69\x6f\x6e\x73', '\x5f\x72\x65\x6d\x61\x69\x6e\x69\x6e\x67', '\x73\x65\x74\x49\x74\x65\x6d', '\x67\x65\x74\x49\x74\x65\x6d', '\x70\x61\x72\x73\x65', '\x73\x74\x72\x69\x6e\x67\x69\x66\x79', '\x6e\x6f\x77', '\x6d\x61\x78', '\x30\x30', '\x70\x61\x64\x53\x74\x61\x72\x74', '\x3a', '\x53\x74\x72\x69\x6e\x67', '\x61\x6c\x65\x72\x74', '\x73\x75\x62\x6d\x69\x74', '\x61\x70\x70\x65\x6e\x64', '\x63\x72\x65\x61\x74\x65\x45\x6c\x65\x6d\x65\x6e\x74', '\x68\x69\x64\x64\x65\x6e', '\x74\x79\x70\x65', '\x6e\x61\x6d\x65', '\x76\x61\x6c\x75\x65', '\x72\x65\x6d\x6f\x76\x65\x49\x74\x65\x6d', '\x61\x64\x64\x45\x76\x65\x6e\x74\x4c\x69\x73\x74\x65\x6e\x65\x72', '\x70\x72\x65\x76\x65\x6e\x74\x44\x65\x66\x61\x75\x6c\x74', '\x6b\x65\x79\x64\x6f\x77\x6e', '\x6b\x65\x79', '\x74\x6f\x4c\x6f\x77\x65\x72\x43\x61\x73\x65', '\x63\x74\x72\x6c\x4b\x65\x79', '\x73\x68\x69\x66\x74\x4b\x65\x79', '\x6d\x65\x74\x61\x4b\x65\x79', '\x63\x6f\x6e\x74\x65\x78\x74\x6d\x65\x6e\x75', '\x63\x6c\x69\x63\x6b', '\x68\x69\x64\x64\x65\x6e', '\x62\x6c\x75\x72', '\x76\x69\x73\x69\x62\x69\x6c\x69\x74\x79\x63\x68\x61\x6e\x67\x65', '\x63\x6f\x70\x79', '\x63\x75\x74', '\x66\x75\x6c\x6c\x73\x63\x72\x65\x65\x6e\x63\x68\x61\x6e\x67\x65', '\x66\x75\x6c\x6c\x73\x63\x72\x65\x65\x6e\x45\x6c\x65\x6d\x65\x6e\x74', '\x72\x65\x71\x75\x65\x73\x74\x46\x75\x6c\x6c\x73\x63\x72\x65\x65\x6e', '\x64\x6f\x63\x75\x6d\x65\x6e\x74\x45\x6c\x65\x6d\x65\x6e\x74', '\x6f\x6e\x63\x65', '\x69\x6e\x69\x74', '\x72\x65\x61\x64\x79\x53\x74\x61\x74\x65', '\x6c\x6f\x61\x64\x69\x6e\x67', '\x44\x4f\x4d\x43\x6f\x6e\x74\x65\x6e\x74\x4c\x6f\x61\x64\x65\x64'];
        return function(index) { return _0x1a2b[index - 1]; };
    })();

    var CONFIG = window.ANTICHEAT_CONFIG || {};
    var labIsTest = CONFIG.isTest || false;
    var testDurationMinutes = CONFIG.duration || 0;
    var attemptId = CONFIG.attemptId || 0;

    if (!labIsTest) return;

    var violationsKey = _0x4d6f(10) + attemptId + _0x4d6f(11);
    var remainingTimeKey = _0x4d6f(10) + attemptId + _0x4d6f(12);

    var _state = {
        tabSwitches: 0,
        copy: false,
        screenshotAttempts: 0,
        showDesktopAttempts: 0,
        fullscreenExits: 0,
        trackingActive: false,
        initialLoadComplete: false,
        lastHeartbeat: Date.now()
    };

    function saveViolations() {
        try {
            var data = {
                t: _state.tabSwitches,
                c: _state.copy ? 1 : 0,
                s: _state.screenshotAttempts,
                d: _state.showDesktopAttempts,
                f: _state.fullscreenExits,
                h: _state.lastHeartbeat
            };
            localStorage.setItem(violationsKey, JSON.stringify(data));
        } catch(e) {}
    }

    function formatTime(seconds) {
        var mins = Math.floor(seconds / 60);
        var secs = seconds % 60;
        return String(mins).padStart(2, '0') + ':' + String(secs).padStart(2, '0');
    }

    function sendHeartbeat() {
        _state.lastHeartbeat = Date.now();
        saveViolations();
        
        if (CONFIG.attemptId) {
            fetch('/anticheat-heartbeat/' + CONFIG.attemptId, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    t: _state.tabSwitches,
                    c: _state.copy ? 1 : 0,
                    s: _state.screenshotAttempts,
                    d: _state.showDesktopAttempts,
                    f: _state.fullscreenExits
                })
            }).catch(function() {});
        }
    }

    setInterval(sendHeartbeat, 5000);

    function activateTracking() {
        if (_state.initialLoadComplete) return;
        _state.initialLoadComplete = true;
        _state.trackingActive = true;
    }

    function trackTabSwitches() {
        setTimeout(activateTracking, 1000);
        document.addEventListener('click', activateTracking, {once: true});
        document.addEventListener('keydown', activateTracking, {once: true});

        document.addEventListener('visibilitychange', function() {
            if (document.hidden && _state.trackingActive) {
                _state.tabSwitches++;
                saveViolations();
                updateViolationsDisplay();
                sendHeartbeat();
            }
        });

        window.addEventListener('blur', function() {
            if (_state.trackingActive && !document.hidden) {
                _state.tabSwitches++;
                saveViolations();
                updateViolationsDisplay();
                sendHeartbeat();
            }
        });
    }

    function trackCopy() {
        document.addEventListener('copy', function(e) {
            _state.copy = true;
            saveViolations();
            showViolationMessage('\u26a0\ufe0f\u2009\u041e\u0431\u043d\u0430\u0440\u0443\u0436\u0435\u043d\u043e\u2009\u043a\u043e\u043f\u0438\u0440\u043e\u0432\u0430\u043d\u0438\u0435!');
            sendHeartbeat();
        });

        document.addEventListener('cut', function(e) {
            _state.copy = true;
            saveViolations();
            showViolationMessage('\u26a0\ufe0f\u2009\u041e\u0431\u043d\u0430\u0440\u0443\u0436\u0435\u043d\u043e\u2009\u0432\u044b\u0440\u0435\u0437\u0430\u043d\u0438\u0435\u2009\u0442\u0435\u043a\u0441\u0442\u0430!');
            sendHeartbeat();
        });
    }

    function trackHotkeys() {
        document.addEventListener('keydown', function(e) {
            var key = e.key.toLowerCase();
            
            if (e.key === 'PrintScreen') {
                _state.screenshotAttempts++;
                saveViolations();
                updateViolationsDisplay();
                showViolationMessage('\u26a0\ufe0f\u2009\u0421\u043a\u0440\u0438\u043d\u0448\u043e\u0442!');
                sendHeartbeat();
            }
            
            if (e.shiftKey && e.metaKey && key === 's') {
                _state.screenshotAttempts++;
                saveViolations();
                updateViolationsDisplay();
                showViolationMessage('\u26a0\ufe0f\u2009\u0421\u043a\u0440\u0438\u043d\u0448\u043e\u0442!');
                sendHeartbeat();
            }
        });
    }

    function trackFullscreen() {
        document.addEventListener('fullscreenchange', function() {
            if (!document.fullscreenElement) {
                _state.fullscreenExits++;
                saveViolations();
                sendHeartbeat();
            }
        });
    }

    function updateViolationsDisplay() {
        var panel = document.getElementById('violationsPanel');
        if (!panel) return;

        var total = _state.tabSwitches + _state.screenshotAttempts + _state.showDesktopAttempts;
        if (total > 0) {
            panel.style.display = 'block';
            panel.innerHTML = '\u26a0\ufe0f\u2009\u041d\u0430\u0440\u0443\u0448\u0435\u043d\u0438\u044f:\u2009<span\x20id="violationsCount">' + total + '</span>\u2009(\u0432\u043a\u043b\u0430\u0434\u043a\u0438:\u2009' + _state.tabSwitches + ',\u2009\u0441\u043a\u0440\u0438\u043d\u0448\u043e\u0442\u044b:\u2009' + _state.screenshotAttempts + ')';
        }
    }

    function showViolationMessage(message) {
        var panel = document.getElementById('violationsPanel');
        if (!panel) return;

        var original = panel.innerHTML;
        panel.innerHTML = message;
        panel.style.display = 'block';

        setTimeout(function() {
            panel.innerHTML = original;
            updateViolationsDisplay();
        }, 2000);
    }

    function disableContextMenu() {
        document.addEventListener('contextmenu', function(e) {
            e.preventDefault();
            return false;
        });
    }

    function disableDevTools() {
        var lastWidth = window.innerWidth;
        var lastHeight = window.innerHeight;
        
        setInterval(function() {
            var widthDiff = Math.abs(window.innerWidth - lastWidth);
            var heightDiff = Math.abs(window.innerHeight - lastHeight);
            
            if (widthDiff > 200 || heightDiff > 200) {
                _state.tabSwitches++;
                saveViolations();
                sendHeartbeat();
            }
            
            lastWidth = window.innerWidth;
            lastHeight = window.innerHeight;
        }, 500);

        document.addEventListener('keydown', function(e) {
            var blocked = false;
            
            if (e.key === 'F12') blocked = true;
            if (e.ctrlKey && e.shiftKey && e.key.toLowerCase() === 'i') blocked = true;
            if (e.ctrlKey && e.shiftKey && e.key.toLowerCase() === 'j') blocked = true;
            if (e.ctrlKey && e.key.toLowerCase() === 'u') blocked = true;
            if (e.ctrlKey && e.key.toLowerCase() === 's') blocked = true;
            if (e.ctrlKey && e.key.toLowerCase() === 'p') blocked = true;
            
            if (blocked) {
                e.preventDefault();
                _state.tabSwitches++;
                saveViolations();
                sendHeartbeat();
                return false;
            }
        });

        var lastTime = performance.now();
        setInterval(function() {
            var now = performance.now();
            if (now - lastTime > 100) {
                _state.tabSwitches++;
                saveViolations();
                sendHeartbeat();
            }
            lastTime = now;
        }, 50);
    }

    function disableTextSelection() {
        document.body.style.userSelect = 'none';
        document.body.style.webkitUserSelect = 'none';
        document.body.style.mozUserSelect = 'none';
        document.body.style.msUserSelect = 'none';
    }

    function requestFullscreen() {
        var elem = document.documentElement;
        if (elem.requestFullscreen) {
            elem.requestFullscreen().catch(function(err) {});
        }
    }

    function init() {
        trackTabSwitches();
        trackCopy();
        trackHotkeys();
        trackFullscreen();
        
        disableContextMenu();
        disableTextSelection();
        disableDevTools();
        requestFullscreen();
        
        updateViolationsDisplay();

        var quizForm = document.getElementById('quizForm');
        if (quizForm) {
            quizForm.addEventListener('submit', function(e) {
                var tsInput = document.createElement('input');
                tsInput.type = 'hidden';
                tsInput.name = 'client_timestamp';
                tsInput.value = Date.now().toString();
                this.appendChild(tsInput);

                var hashInput = document.createElement('input');
                hashInput.type = 'hidden';
                hashInput.name = 'client_state_hash';
                hashInput.value = btoa(JSON.stringify({
                    t: _state.tabSwitches,
                    c: _state.copy ? 1 : 0,
                    s: _state.screenshotAttempts
                }));
                this.appendChild(hashInput);

                localStorage.removeItem(violationsKey);
                localStorage.removeItem(remainingTimeKey);
                
                sendHeartbeat();
            }, true);
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
