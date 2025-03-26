// Enhanced chat functionality
document.addEventListener('DOMContentLoaded', () => {
    const chatHistory = document.getElementById("chat-history");
    const userInput = document.getElementById("user-input");
    const sendButton = document.getElementById("send-button");

    // Clear session history on page load
    fetch('/api/clear_session', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
    }).catch(error => console.log("Session clear attempt:", error));

    // Improved addMessage function
    const addMessage = (role, content) => {
        const messageDiv = document.createElement("div");
        messageDiv.className = `message ${role}-message`;
        
        const messageContent = document.createElement("div");
        messageContent.className = "message-content";
        messageContent.innerHTML = content;
        
        messageDiv.appendChild(messageContent);
        chatHistory.appendChild(messageDiv);
        chatHistory.scrollTo({
            top: chatHistory.scrollHeight,
            behavior: 'smooth'
        });
    };

    // Optimized sendMessage function
    const sendMessage = async () => {
        const message = userInput.value.trim();
        if (!message) return;

        // UI Feedback
        userInput.disabled = true;
        sendButton.disabled = true;
        addMessage("user", `<p>${message}</p>`);
        userInput.value = "";

        // Better typing indicator
        const typingIndicator = document.createElement("div");
        typingIndicator.id = "typing-indicator";
        typingIndicator.innerHTML = `
            <div class="typing-indicator">
                <span class="typing-dot"></span>
                <span class="typing-dot"></span>
                <span class="typing-dot"></span>
            </div>`;
        chatHistory.appendChild(typingIndicator);
        chatHistory.scrollTo({ top: chatHistory.scrollHeight, behavior: 'smooth' });

        try {
            const startTime = Date.now();
            const response = await fetch("/api/chat", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ message })
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || "Network response was not ok");
            }
            
            const data = await response.json();
            const responseTime = (Date.now() - startTime) / 1000;
            console.log(`Response received in ${responseTime} seconds`);
            
            typingIndicator.remove();
            addMessage("bot", data.response || "<p>I couldn't generate a response. Please try again.</p>");

        } catch (error) {
            console.error("Chat error:", error);
            typingIndicator.remove();
            addMessage("bot", `<p>Error: ${error.message || "Please try again later"}</p>`);
        } finally {
            userInput.disabled = false;
            sendButton.disabled = false;
            userInput.focus();
        }
    };

    // Event listeners with debounce
    sendButton.addEventListener("click", sendMessage);
    userInput.addEventListener("keypress", (e) => {
        if (e.key === "Enter") sendMessage();
    });
});