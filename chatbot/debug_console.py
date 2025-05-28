from chatbot.chatbot_logic import get_bot_response, get_bot_state

# Simple chatbot debug console with state display
def main():
    print("Chatbot Debug Console")
    print("Type your message and press Enter. Type 'exit' to quit.\n")
    while True:
        user_input = input("You: ")
        if user_input.lower() in ('exit', 'quit'):
            print("Exiting debug console.")
            break
        # Get bot response
        bot_response = get_bot_response(user_input)
        print(f"Bot: {bot_response}")
        # Retrieve and display internal state
        state = get_bot_state()
        print("State:")
        print(f"  Intent:       {state['intent']}")
        print(f"  Slots:        {state['slots']}")
        print(f"  Confirm flag: {state['confirm_done']}\n")

if __name__ == '__main__':
    main()