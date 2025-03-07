document.addEventListener('DOMContentLoaded', function() {
    // Handle filter changes
    const filterSelects = document.querySelectorAll('.filter-group select');
    filterSelects.forEach(select => {
        select.addEventListener('change', applyFilters);
    });

    // Apply filters function
    function applyFilters() {
        const params = new URLSearchParams();
        
        filterSelects.forEach(select => {
            if (select.value) {
                params.append(select.getAttribute('data-filter'), select.value);
            }
        });
        
        // Update URL and reload page with new filters
        window.location.href = `${window.location.pathname}?${params.toString()}`;
    }

    // Chat functionality
    const chatForm = document.getElementById('chat-form');
    const chatInput = document.getElementById('chat-input');
    const chatMessages = document.getElementById('chat-messages');
    const projectId = chatForm?.dataset.projectId;

    if (chatForm) {
        chatForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const message = chatInput.value.trim();
            if (!message) return;
            
            // Add user message to chat
            appendMessage('user', message);
            chatInput.value = '';
            
            // Show typing indicator
            const typingIndicator = appendTypingIndicator();
            
            try {
                // Send message to server
                const response = await fetch('/api/chat', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        project_id: projectId,
                        message: message
                    })
                });
                
                const data = await response.json();
                
                // Remove typing indicator
                typingIndicator.remove();
                
                if (response.ok) {
                    // Add AI response to chat
                    appendMessage('assistant', data.response);
                } else {
                    throw new Error(data.error || 'Failed to get response');
                }
                
            } catch (error) {
                console.error('Chat error:', error);
                typingIndicator?.remove();
                appendErrorMessage('Failed to get response. Please try again.');
            }
            
            // Scroll to bottom
            chatMessages.scrollTop = chatMessages.scrollHeight;
        });
    }

    // Helper functions for chat UI
    function appendMessage(role, content) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `chat-message ${role}-message`;
        
        const iconDiv = document.createElement('div');
        iconDiv.className = 'message-icon';
        iconDiv.innerHTML = role === 'user' ? 
            '<i class="fas fa-user"></i>' : 
            '<i class="fas fa-robot"></i>';
        
        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        contentDiv.textContent = content;
        
        messageDiv.appendChild(iconDiv);
        messageDiv.appendChild(contentDiv);
        chatMessages.appendChild(messageDiv);
        
        return messageDiv;
    }

    function appendTypingIndicator() {
        const indicatorDiv = document.createElement('div');
        indicatorDiv.className = 'chat-message assistant-message typing-indicator';
        indicatorDiv.innerHTML = `
            <div class="message-icon">
                <i class="fas fa-robot"></i>
            </div>
            <div class="message-content">
                <div class="typing-dots">
                    <span></span>
                    <span></span>
                    <span></span>
                </div>
            </div>
        `;
        chatMessages.appendChild(indicatorDiv);
        return indicatorDiv;
    }

    function appendErrorMessage(message) {
        const errorDiv = document.createElement('div');
        errorDiv.className = 'chat-message error-message';
        errorDiv.innerHTML = `
            <div class="message-icon">
                <i class="fas fa-exclamation-circle"></i>
            </div>
            <div class="message-content">
                ${message}
            </div>
        `;
        chatMessages.appendChild(errorDiv);
        return errorDiv;
    }
}); 