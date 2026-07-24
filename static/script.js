document.addEventListener("DOMContentLoaded", function () {
    // DOM Elements
    const chatContainer = document.getElementById("chatbot");
    const userInput = document.getElementById("user-input");
    const sendButton = document.getElementById("send-button");
    const historyContainer = document.getElementById("history-container");
    const clearHistoryBtn = document.getElementById("clear-history");
    const sidebarToggle = document.getElementById("sidebar-toggle");
    const sidebar = document.getElementById("sidebar");
    const newChatBtn = document.getElementById("new-chat-btn");
    const helpBtn = document.getElementById("help-btn");
    const logoutBtn = document.getElementById("logout-btn");
    const helpModal = document.getElementById("help-modal");
    const closeHelpModal = document.getElementById("close-help-modal");
    const voiceToggleBtn = document.getElementById("voice-toggle");
    const languageSelector = document.getElementById("language-selector");

    // Quick tools buttons
    const vegetarianBtn = document.getElementById("vegetarian-btn");
    const quickMealsBtn = document.getElementById("quick-meals-btn");
    const dessertsBtn = document.getElementById("desserts-btn");
    const popularBtn = document.getElementById("popular-btn");
    const ingredientsBtn = document.getElementById("ingredients-btn");

    // Current conversation state
    let isWaitingForResponse = false;
    let currentAudio = null;
    let lastAudioData = null;
    let currentConversationId = null;

    // Language translations
    const translations = {
        en: {
            conversation_history: "Conversation History",
            clear_history: "Clear History",
            recipe_assistant: "Recipe Document Assistant",
            logout: "Logout",
            new_chat: "New Chat",
            help: "Help",
            play_audio: "Play Audio Response",
            input_placeholder: "Ask me about Middle Eastern recipes...",
            quick_tools: "Quick Recipe Tools",
            vegetarian: "Vegetarian",
            quick_meals: "Quick Meals",
            desserts: "Desserts",
            popular: "Popular",
            by_ingredients: "By Ingredients",
            help_instructions: "Help & Instructions",
            how_to_use: "How to use the Recipe Document Assistant",
            help_description: "Ask questions about Middle Eastern recipes from our collection of authentic cookbooks.",
            example_queries: "Example queries:",
            example1: "How do I make hummus?",
            example2: "Show me vegetarian recipes",
            example3: "What's a traditional dessert from Lebanon?",
            example4: "Find recipes with eggplant",
            quick_tools_title: "Quick Tools:",
            quick_tools_desc: "Use the buttons at the bottom to quickly find recipes by category.",
            note: "Note:",
            note_desc: "The assistant only answers based on the available recipe documents. If a recipe isn't in our collection, it won't be able to help.",
            initial_message: "Hello! I'm your recipe assistant. Ask me anything about Middle Eastern cuisine!"
        },
        ar: {
            conversation_history: "سجل المحادثات",
            clear_history: "مسح السجل",
            recipe_assistant: "مساعد وصفات الطعام",
            logout: "تسجيل خروج",
            new_chat: "محادثة جديدة",
            help: "مساعدة",
            play_audio: "تشغيل الرد الصوتي",
            input_placeholder: "اسألني عن وصفات الشرق الأوسط...",
            quick_tools: "أدوات سريعة",
            vegetarian: "نباتي",
            quick_meals: "وجبات سريعة",
            desserts: "حلويات",
            popular: "الأكثر شيوعاً",
            by_ingredients: "حسب المكونات",
            help_instructions: "مساعدة وتعليمات",
            how_to_use: "كيفية استخدام مساعد الوصفات",
            help_description: "اطرح أسئلة حول وصفات الشرق الأوسط من مجموعتنا من كتب الطبخ الأصيلة.",
            example_queries: "استفسارات مثاليه:",
            example1: "كيف أصنع الحمص؟",
            example2: "أرني وصفات نباتية",
            example3: "ما هي الحلوى التقليدية من لبنان؟",
            example4: "ابحث عن وصفات تحتوي على الباذنجان",
            quick_tools_title: "أدوات سريعة:",
            quick_tools_desc: "استخدم الأزرار في الأسفل للعثور على الوصفات حسب الفئة بسرعة.",
            note: "ملاحظة:",
            note_desc: "يجيب المساعد فقط بناءً على وثائق الوصفات المتاحة. إذا لم تكن الوصفة في مجموعتنا، فلن يتمكن من المساعدة.",
            initial_message: "مرحبًا! أنا مساعد الوصفات الخاص بك. اسألني أي شيء عن مطبخ الشرق الأوسط!"
        }
    };

    // Set initial language from localStorage or default to English
    let currentLanguage = localStorage.getItem('language') || 'en';
    languageSelector.value = currentLanguage;
    updateLanguage(currentLanguage);

    // Language selector change event
    languageSelector.addEventListener('change', function () {
        currentLanguage = this.value;
        localStorage.setItem('language', currentLanguage);
        updateLanguage(currentLanguage);
    });

    // Update language function
    function updateLanguage(lang) {
        // Set document direction
        document.body.dir = lang === 'ar' ? 'rtl' : 'ltr';

        // Update all elements with data-i18n attribute
        document.querySelectorAll('[data-i18n]').forEach(element => {
            const key = element.getAttribute('data-i18n');
            if (translations[lang] && translations[lang][key]) {
                element.textContent = translations[lang][key];
            }
        });

        // Update placeholders and titles
        document.querySelectorAll('[data-i18n-placeholder]').forEach(element => {
            const key = element.getAttribute('data-i18n-placeholder');
            if (translations[lang] && translations[lang][key]) {
                element.placeholder = translations[lang][key];
            }
        });

        document.querySelectorAll('[data-i18n-title]').forEach(element => {
            const key = element.getAttribute('data-i18n-title');
            if (translations[lang] && translations[lang][key]) {
                element.title = translations[lang][key];
            }
        });
    }

    // Check for conversation ID in URL
    const urlParams = new URLSearchParams(window.location.search);
    const conversationId = urlParams.get('conversation_id');
    if (conversationId) {
        loadConversation(conversationId);
    } else {
        // Initialize with current time
        const now = new Date();
        const timeString = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        document.querySelector('.message-time').textContent = timeString;
    }

    // Load history on page load
    loadHistory();

    // Toggle sidebar on mobile
    sidebarToggle.addEventListener('click', () => {
        sidebar.classList.toggle('collapsed');
    });

    // Logout button
    logoutBtn.addEventListener('click', () => {
        if (confirm(currentLanguage === 'ar' ? 'هل أنت متأكد أنك تريد تسجيل الخروج؟' : 'Are you sure you want to logout?')) {
            window.location.href = '/logout';
        }
    });

    // Play audio when voice button is clicked
    voiceToggleBtn.addEventListener('click', () => {
        if (lastAudioData) {
            // Stop any currently playing audio
            if (currentAudio) {
                currentAudio.pause();
                currentAudio = null;
            }

            // Play the audio
            currentAudio = new Audio(`data:audio/wav;base64,${lastAudioData}`);
            currentAudio.play();

            // Change button appearance while playing
            voiceToggleBtn.classList.add('has-audio');
            voiceToggleBtn.innerHTML = '<i class="fas fa-volume-up"></i>';

            // When audio finishes, reset button
            currentAudio.onended = () => {
                voiceToggleBtn.classList.remove('has-audio');
            };
        }
    });

    // Clear history
    clearHistoryBtn.addEventListener('click', () => {
        if (confirm(currentLanguage === 'ar' ? 'هل أنت متأكد أنك تريد مسح سجل المحادثات بالكامل؟' : 'Are you sure you want to clear all conversation history?')) {
            fetch('/clear-history', {
                method: 'POST'
            })
                .then(response => {
                    if (response.ok) {
                        historyContainer.innerHTML = currentLanguage === 'ar' ? '<p>لا يوجد سجل محادثات حتى الآن</p>' : '<p>No conversation history yet</p>';
                        // Clear current chat if not in a specific conversation
                        if (!conversationId) {
                            chatContainer.innerHTML = `
                                    <div class="message bot-message">
                                        <div class="message-content" data-i18n="initial_message">${translations[currentLanguage].initial_message}</div>
                                        <div class="message-time">${new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</div>
                                    </div>
                                `;
                        }
                    }
                })
                .catch(error => console.error('Error clearing history:', error));
        }
    });

    // New chat button
    newChatBtn.addEventListener('click', () => {
        if (confirm(currentLanguage === 'ar' ? 'بدء محادثة جديدة؟ سيتم مسح الدردشة الحالية.' : 'Start a new conversation? This will clear the current chat.')) {
            chatContainer.innerHTML = `
                    <div class="message bot-message">
                        <div class="message-content" data-i18n="initial_message">${translations[currentLanguage].initial_message}</div>
                        <div class="message-time">${new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</div>
                    </div>
                `;
            // Stop any currently playing audio
            if (currentAudio) {
                currentAudio.pause();
                currentAudio = null;
            }
            lastAudioData = null;
            voiceToggleBtn.classList.remove('has-audio');
            currentConversationId = null;
            window.history.pushState({}, '', '/');
        }
    });

    // Help button
    helpBtn.addEventListener('click', () => {
        helpModal.classList.add('active');
    });

    // Close modals
    closeHelpModal.addEventListener('click', () => {
        helpModal.classList.remove('active');
    });

    // Close modals when clicking outside
    helpModal.addEventListener('click', (e) => {
        if (e.target === helpModal) {
            helpModal.classList.remove('active');
        }
    });

    // Quick tools buttons
    vegetarianBtn.addEventListener('click', () => {
        sendQuery(currentLanguage === 'ar' ? 'أرني وصفات الشرق الأوسط النباتية' : 'Show me vegetarian Middle Eastern recipes');
    });

    quickMealsBtn.addEventListener('click', () => {
        sendQuery(currentLanguage === 'ar' ? 'أرني وجبات الشرق الأوسط السريعة التي تستغرق أقل من 30 دقيقة' : 'Show me quick Middle Eastern meals that take less than 30 minutes');
    });

    dessertsBtn.addEventListener('click', () => {
        sendQuery(currentLanguage === 'ar' ? 'أرني الحلويات التقليدية للشرق الأوسط' : 'Show me traditional Middle Eastern desserts');
    });

    popularBtn.addEventListener('click', () => {
        sendQuery(currentLanguage === 'ar' ? 'ما هي أكثر وصفات الشرق الأوسط شيوعًا؟' : 'What are the most popular Middle Eastern recipes?');
    });

    ingredientsBtn.addEventListener('click', () => {
        const ingredient = prompt(currentLanguage === 'ar' ? 'أدخل مكونًا للعثور على الوصفات:' : 'Enter an ingredient to find recipes:');
        if (ingredient) {
            sendQuery(currentLanguage === 'ar' ? `أرني وصفات الشرق الأوسط التي تستخدم ${ingredient}` : `Show me Middle Eastern recipes that use ${ingredient}`);
        }
    });

    // Load a specific conversation
    function loadConversation(conversationId) {
        fetch(`/conversations/${conversationId}`)
            .then(response => response.json())
            .then(data => {
                chatContainer.innerHTML = '';
                data.messages.forEach(msg => {
                    addMessage(msg.content, msg.is_user);
                });
                currentConversationId = conversationId;
            })
            .catch(error => {
                console.error('Error loading conversation:', error);
            });
    }

    // Load search history
    function loadHistory() {
        fetch("/history")
            .then((response) => response.json())
            .then((history) => {
                if (history.length > 0) {
                    historyContainer.innerHTML = history
                        .map(
                            (item) => `
                                <div class="history-item" data-id="${item.id}">
                                    <div class="history-time">${item.timestamp}</div>
                                    <div class="history-query">${item.title}</div>
                                </div>
                            `
                        )
                        .reverse()
                        .join("");

                    // Add click event to history items
                    document.querySelectorAll('.history-item').forEach(item => {
                        item.addEventListener('click', () => {
                            const conversationId = item.getAttribute('data-id');
                            loadConversation(conversationId);
                            window.history.pushState({}, '', `?conversation_id=${conversationId}`);
                        });
                    });
                } else {
                    historyContainer.innerHTML = currentLanguage === 'ar' ? "<p>لا يوجد سجل محادثات حتى الآن</p>" : "<p>No conversation history yet</p>";
                }
            });
    }

    // Add a message to the chat
    function addMessage(content, isUser, audioData = null) {
        const messageDiv = document.createElement("div");
        messageDiv.className = `message ${isUser ? "user-message" : "bot-message"}`;

        const contentDiv = document.createElement("div");
        contentDiv.className = "message-content";
        contentDiv.innerHTML = content.replace(/\n/g, "<br>");

        const timeDiv = document.createElement("div");
        timeDiv.className = "message-time";
        timeDiv.textContent = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

        messageDiv.appendChild(contentDiv);
        messageDiv.appendChild(timeDiv);

        // Add audio player for bot messages with audio
        if (!isUser && audioData) {
            lastAudioData = audioData;
            voiceToggleBtn.classList.add('has-audio');

            const actionsDiv = document.createElement("div");
            actionsDiv.className = "message-actions";

            const audioPlayer = document.createElement("audio");
            audioPlayer.className = "audio-player";
            audioPlayer.controls = true;
            audioPlayer.src = `data:audio/wav;base64,${audioData}`;


            actionsDiv.appendChild(audioPlayer);
            messageDiv.appendChild(actionsDiv);
        } else if (!isUser) {
            lastAudioData = null;
            voiceToggleBtn.classList.remove('has-audio');
        }

        chatContainer.appendChild(messageDiv);
        chatContainer.scrollTop = chatContainer.scrollHeight;
    }

    // Show typing indicator
    function showTypingIndicator() {
        const typingDiv = document.createElement("div");
        typingDiv.className = "typing-indicator";
        typingDiv.innerHTML = `
        <div class="typing-dot"></div>
        <div class="typing-dot"></div>
        <div class="typing-dot"></div>
        `;
        typingDiv.id = "typing-indicator";
        chatContainer.appendChild(typingDiv);
        chatContainer.scrollTop = chatContainer.scrollHeight;
    }

    // Hide typing indicator
    function hideTypingIndicator() {
        const indicator = document.getElementById("typing-indicator");
        if (indicator) {
            indicator.remove();
        }
    }

    // Send a query to the server
    function sendQuery(query) {
        if (isWaitingForResponse) return;

        userInput.value = query;
        sendMessage();
    }

    // Send message to server
    function sendMessage() {
        const message = userInput.value.trim();
        if (message === "" || isWaitingForResponse) return;

        addMessage(message, true);
        userInput.value = "";
        isWaitingForResponse = true;
        showTypingIndicator();

        // Stop any currently playing audio
        if (currentAudio) {
            currentAudio.pause();
            currentAudio = null;
        }

        // Get conversation ID from URL if it exists
        const urlParams = new URLSearchParams(window.location.search);
        const conversationId = urlParams.get('conversation_id');

        fetch("/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                message: message,
                conversation_id: conversationId
            }),
        })
            .then((response) => response.json())
            .then((data) => {
                hideTypingIndicator();
                isWaitingForResponse = false;

                if (data.response) {
                    addMessage(data.response, false, data.audio);

                    // If this is a new conversation, update the URL
                    if (!conversationId && data.conversation_id) {
                        window.history.pushState({}, '', `?conversation_id=${data.conversation_id}`);
                        currentConversationId = data.conversation_id;
                    }
                } else {
                    addMessage("Error: " + (data.error || "Unknown issue"), false);
                }
                loadHistory();
            })
            .catch((error) => {
                hideTypingIndicator();
                isWaitingForResponse = false;
                console.error("Chat error:", error);
                addMessage("Sorry, I encountered an error. Please try again.", false);
            });
    }

    // Event listeners
    sendButton.addEventListener("click", sendMessage);
    userInput.addEventListener("keypress", function (e) {
        if (e.key === "Enter") sendMessage();
    });
});