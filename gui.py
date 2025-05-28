import tkinter as tk
import webbrowser
import re
import threading
import logging
import traceback
from chatbot.chatbot_logic import Chatbot
from tkinter import scrolledtext

#Logs for chatbot
logging.basicConfig(
    filename='logs/chatbot.log',
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s'
)
logger = logging.getLogger(__name__)
bot = Chatbot()

# Gui Functions
def send_message(event=None):
    user_message = entry_var.get().strip()
    # Basic input validation
    if not user_message:
        return
    if len(user_message) > 500:
        status_label.config(text="Message too long, please limit to 500 characters.")
        return

    # Display user text and log
    display_message("You", user_message)
    logger.info(f"User: {user_message}")

    # Disable input and show loading
    entry_var.set("")
    send_button.config(state=tk.DISABLED)
    entry_box.config(state=tk.DISABLED)
    status_label.config(text="Loading...")

    # Process response in background thread
    threading.Thread(target=_process_user_message, args=(user_message,)).start()

# Handle user message and update UI
def _process_user_message(user_message):
    try:
        response = bot.respond(user_message)
    except Exception:

        traceback.print_exc()

        response = "Sorry, something went wrong. Please try again."
    # Schedule UI update on main thread
    root.after(0, lambda: _display_bot_response(response))

# Show bot response and re-enable input
def _display_bot_response(response):
    # Clear loading indicator
    status_label.config(text="")
    send_button.config(state=tk.NORMAL)
    entry_box.config(state=tk.NORMAL)

    # Display bot response and log
    display_message("Bot", response)
    logger.info(f"Bot: {response}")

# Display message with clickable URLs
def display_message(sender, message):
    chat_area.config(state='normal')
    chat_area.insert(tk.END, f"{sender}: ")

    # Detect and hyperlink URLs
    url_pattern = re.compile(r"(https?://\S+)")
    last_end = 0
    for match in url_pattern.finditer(message):
        chat_area.insert(tk.END, message[last_end:match.start()])
        url = match.group(1)
        start = chat_area.index(tk.END)
        chat_area.insert(tk.END, url)
        end = chat_area.index(tk.END)
        chat_area.tag_add(url, start, end)
        chat_area.tag_bind(url, "<Button-1>", lambda e, url=url: webbrowser.open(url))
        chat_area.tag_config(url, foreground="blue", underline=True)
        last_end = match.end()
    chat_area.insert(tk.END, message[last_end:] + "\n\n")
    chat_area.config(state='disabled')
    chat_area.see(tk.END)

# Reset chatbot state and UI
def reset_conversation():
    global bot
    bot = Chatbot()  # reinstantiate to clear state
    logger.info("Conversation reset by user.")
    chat_area.config(state='normal')
    chat_area.delete("1.0", tk.END)
    chat_area.config(state='disabled')
    status_label.config(text="")
    display_message("Bot", "Hello! How can I help you today?")

#Tkinter ui
root = tk.Tk()
root.title("TrainFinder Chatbot")
root.geometry("800x600")

# Chat display area
chat_area = scrolledtext.ScrolledText(root, state='disabled', wrap=tk.WORD, font=("Aptos Display", 14))
chat_area.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

# Status label for slot-filling prompts and loading
status_label = tk.Label(root, text="", fg="darkgreen")
status_label.pack(padx=10, pady=(0,5))

# Entry box and Send button
entry_var = tk.StringVar()

# Enable/disable send button based on input
def _on_entry_change(*args):
    send_button.config(state=tk.NORMAL if entry_var.get().strip() else tk.DISABLED)
entry_var.trace_add("write", _on_entry_change)
entry_box = tk.Entry(root, textvariable=entry_var, width=70)
entry_box.pack(padx=5, pady=(0,1), side=tk.LEFT, fill=tk.X, expand=True)
entry_box.bind("<Return>", send_message)
send_button = tk.Button(root, text="Send", command=send_message, state=tk.DISABLED)
send_button.pack(padx=(0,1), pady=(0,1), side=tk.LEFT)

# Reset button
reset_button = tk.Button(root, text="Reset", command=reset_conversation)
reset_button.pack(padx=5, pady=(0,1), side=tk.RIGHT)

# Initial greeting
display_message("Bot", "Hello! How can I help you today?")
entry_box.focus()

# Clean shutdown
def on_close():
    logger.info("Application closed by user.")
    root.destroy()
root.protocol("WM_DELETE_WINDOW", on_close)

root.mainloop()