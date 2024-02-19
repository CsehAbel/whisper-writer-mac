import json
import os
import queue
import threading
import time
import tkinter as tk

from pynput import keyboard as pynput_keyboard
from pynput.keyboard import Controller
from transcription import record_and_transcribe

# Define the StatusWindow class using Tkinter
class StatusWindow(tk.Tk):
    def __init__(self, status_queue):
        super().__init__()
        self.status_queue = status_queue
        self.label = tk.Label(self, text="Status")
        self.label.pack()
        self.after(100, self.check_queue)

    def check_queue(self):
        try:
            status, message = self.status_queue.get_nowait()
            self.label.config(text=message)
            if status == 'cancel':
                self.destroy()
        except queue.Empty:
            pass
        self.after(100, self.check_queue)

class ResultThread(threading.Thread):
    def __init__(self, *args, **kwargs):
        super(ResultThread, self).__init__(*args, **kwargs)
        self.result = None
        self.stop_transcription = False

    def run(self):
        self.result = self._target(*self._args, cancel_flag=lambda: self.stop_transcription, **self._kwargs)

    def stop(self):
        self.stop_transcription = True

def load_config_with_defaults():
    default_config = {
        'use_api': True,
        'api_options': {
            'model': 'whisper-1',
            'language': None,
            'temperature': 0.0,
            'initial_prompt': None
        },
        'local_model_options': {
            'model': 'base',
            'device': None,
            'language': None,
            'temperature': 0.0,
            'initial_prompt': None,
            'condition_on_previous_text': True,
            'verbose': False
        },
        'activation_key': 'ctrl+alt+space',
        'silence_duration': 900,
        'writing_key_press_delay': 0.008,
        'remove_trailing_period': True,
        'add_trailing_space': False,
        'remove_capitalization': False,
        'print_to_terminal': True,
    }

    config_path = os.path.join('src', 'config.json')
    if os.path.isfile(config_path):
        with open(config_path, 'r') as config_file:
            user_config = json.load(config_file)
            for key, value in user_config.items():
                if key in default_config and value is not None:
                    default_config[key] = value

    return default_config

def clear_status_queue():
    while not status_queue.empty():
        try:
            status_queue.get_nowait()
        except queue.Empty:
            break

def on_shortcut():
    global status_queue, status_window
    clear_status_queue()

    status_queue.put(('recording', 'Recording...'))
    recording_thread = ResultThread(target=record_and_transcribe, args=(status_queue,), kwargs={'config': config})
    recording_thread.start()

    recording_thread.join()

    if status_window:
        status_queue.put(('cancel', ''))

    transcribed_text = recording_thread.result

    if transcribed_text:
        typewrite(transcribed_text, interval=config['writing_key_press_delay'])

def format_keystrokes(key_string):
    return '+'.join(word.capitalize() for word in key_string.split('+'))

def typewrite(text, interval):
    for letter in text:
        pyinput_keyboard_controller.press(letter)
        pyinput_keyboard_controller.release(letter)
        time.sleep(interval)


# Main script

config = load_config_with_defaults()
method = 'OpenAI\'s API' if config['use_api'] else 'a local model'
status_queue = queue.Queue()

special_keys = {
    'cmd': pynput_keyboard.Key.cmd,
    'ctrl': pynput_keyboard.Key.ctrl,
    'shift': pynput_keyboard.Key.shift,
    'alt': pynput_keyboard.Key.alt,
    # Add other special keys as needed
}

# Define the hotkey combination
hotkey = config['activation_key'].split('+')
# Convert to the format used by pynput
hotkey = [special_keys[k.lower()] if k.lower() in special_keys else k for k in hotkey]
# The set of keys currently pressed
current_keys = set()
pyinput_keyboard_controller = Controller()

print(f'Script activated. Whisper is set to run using {method}. To change this, modify the "use_api" value in the src\\config.json file.')
print(f'Press {format_keystrokes(config["activation_key"])} to start recording and transcribing. Press Ctrl+C on the terminal window to quit.')

# Create the StatusWindow on the main thread
status_window = StatusWindow(status_queue)

def on_press(key):
    # Add the pressed key to the set
    if hasattr(key, 'char') and key.char:
        current_keys.add(key.char)
    else:
        current_keys.add(key)

    # Check if all hotkey keys are currently pressed
    if all(k in current_keys for k in hotkey):
        on_shortcut()

def on_release(key):
    # Remove the released key from the set
    if hasattr(key, 'char') and key.char:
        current_keys.discard(key.char)
    else:
        current_keys.discard(key)


# Run the status window and listener on the main thread
if __name__ == "__main__":
    try:
        # Start the keyboard listener
        listener = pynput_keyboard.Listener(on_press=on_press, on_release=on_release)
        listener.start()

        print(f'Script activated. Whisper is set to run using {method}.')
        print(f'Press {format_keystrokes(config["activation_key"])} to start recording and transcribing.')
        print(f"Listener is trusted: {listener.IS_TRUSTED}")

        # Start the Tkinter main loop
        status_window.mainloop()

        # Wait for the listener thread to finish
        listener.join()
    except KeyboardInterrupt:
        print('\nExiting the script...')
        os._exit(0)  # Use os._exit to exit immediately without cleanup
        