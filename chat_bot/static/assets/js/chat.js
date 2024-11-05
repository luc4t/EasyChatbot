class ChatManager {
    constructor() {
        this.submitBtn = document.getElementById("chatSubmitBtn");
        this.chatTextBox = document.getElementById("chatTextBox");
        this.chatBubblesContainer = document.getElementById("chatBubblesContainer");
        this.chatMessages = [];

        this.chatTextBox.addEventListener("keydown", (event) => {
            if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                this.submitMessage();
            }
        });

        this.submitBtn.addEventListener("click", () => {
            this.submitMessage();
        });
    }

    addMessageToUI(message, role) {
        const messageElement = document.createElement("div");
        messageElement.classList.add("chat-message", role);
        messageElement.textContent = message;
        this.chatBubblesContainer.appendChild(messageElement);
        this.chatBubblesContainer.scrollTop = this.chatBubblesContainer.scrollHeight;
    }

    async submitMessage() {
        const message = this.chatTextBox.value.trim();
        if (!message) return;

        // Display user's message
        this.addMessageToUI(message, "user");
        this.chatTextBox.value = '';
        this.chatTextBox.focus();

        // Add loading indicator
        const loadingMessage = document.createElement("div");
        loadingMessage.classList.add("chat-message", "assistant");
        loadingMessage.textContent = "Typing...";
        this.chatBubblesContainer.appendChild(loadingMessage);
        this.chatBubblesContainer.scrollTop = this.chatBubblesContainer.scrollHeight;

        try {
            const response = await fetch("/api/chat", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    messages: this.chatMessages.concat({ role: "user", content: message })
                })
            });

            if (response.ok) {
                const data = await response.json();
                const assistantMessage = data.choices[0].message.content;

                // Update chat history
                this.chatMessages.push({ role: "user", content: message });
                this.chatMessages.push({ role: "assistant", content: assistantMessage });

                // Remove loading indicator and display assistant's message
                this.chatBubblesContainer.removeChild(loadingMessage);
                this.addMessageToUI(assistantMessage, "assistant");
            } else {
                throw new Error("Network response was not ok");
            }
        } catch (error) {
            this.chatBubblesContainer.removeChild(loadingMessage);
            this.addMessageToUI("Sorry, there was an error processing your request.", "assistant");
            console.error("Error submitting message:", error);
        }
    }
}

document.addEventListener("DOMContentLoaded", () => {
    new ChatManager();
});