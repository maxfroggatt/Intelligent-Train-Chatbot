import sys
from chatbot.chatbot_logic import Chatbot

# Start chatbot in CLI mode
def run_cli():
    bot = Chatbot()
    print("Bot: Hello! How can I help you today?")
    while True:
        try:
            user = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not user:
            continue
        # Allow exit
        if user.lower() in ("exit", "quit"):
            print("Bot: Goodbye!")
            break

        reply = bot.respond(user)
        print(f"Bot: {reply}")

def run_gui():
    # gui.py already does root.mainloop()
    import gui

if __name__ == "__main__":
    if "--gui" in sys.argv:
        run_gui()
    else:
        run_cli()