import tkinter as tk
import ttkbootstrap as tb
from ttkbootstrap.constants import *
from ttkbootstrap.widgets.scrolled import ScrolledText
from tkinter import filedialog, messagebox
import requests
import json
import webbrowser
import os
import sys

class ZenodoRDMApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Zenodo Duplicator")
        self.root.geometry("800x650")
        
        # Configuration
        self.API_URL = "https://zenodo.org/api/records"
        self.TOKEN = self.load_token()
        self.payload = None

        # --- UI LAYOUT ---
        container = tb.Frame(self.root, padding=20)
        container.pack(fill=BOTH, expand=YES)

        # Header
        header = tb.Label(container, text="Zenodo Duplicator", font=("Helvetica", 18, "bold"), bootstyle=DEFAULT)
        header.pack(pady=(0, 10))

        # Token Status
        token_style = SUCCESS if self.TOKEN else DANGER
        token_text = f"Token Status: {'Active' if self.TOKEN else 'Not Found (token.txt)'}"
        self.lbl_token = tb.Label(container, text=token_text, bootstyle=token_style)
        self.lbl_token.pack(pady=5)

        # Action Buttons
        btn_group = tb.Frame(container)
        btn_group.pack(pady=20)

        self.btn_file = tb.Button(btn_group, text="📁 Load JSON", bootstyle=OUTLINE, command=self.process_file)
        self.btn_file.pack(side=LEFT, padx=5)

        self.btn_clip = tb.Button(btn_group, text="📋 From Clipboard", bootstyle=OUTLINE, command=self.process_clipboard)
        self.btn_clip.pack(side=LEFT, padx=5)

        self.btn_save_txt = tb.Button(btn_group, text="💾 Save Payload", bootstyle=(OUTLINE, INFO), 
                                      command=self.save_to_file, state=DISABLED)
        self.btn_save_txt.pack(side=LEFT, padx=5)

        self.btn_clear = tb.Button(btn_group, text="🗑️ Clear All", bootstyle=(OUTLINE, SECONDARY), command=self.clear_all)
        self.btn_clear.pack(side=LEFT, padx=5)
    
        # Frame for button – ALWAYS at the bottom
        button_frame = tb.Frame(container)
        button_frame.pack(side=BOTTOM, fill=X)

        # Frame for scrollable content – takes remaining space
        content_frame = tb.Frame(container)
        content_frame.pack(side=TOP, fill=BOTH, expand=YES)

        # Text Preview
        preview_label = tb.Label(content_frame, text="Payload Preview:", font=("Helvetica", 10, "bold"))
        preview_label.pack(anchor=W, padx=5)
        
        self.text_preview = ScrolledText(content_frame, height=25, font=("Consolas", 9))
        self.text_preview.pack(fill=BOTH, expand=YES, pady=10)

        # Submit Button
        self.btn_send = tb.Button(button_frame, text="🚀 CREATE RECORD ON ZENODO", 
                                 bootstyle=SUCCESS, command=self.create_draft, state=DISABLED)
        self.btn_send.pack(fill=X, pady=20)

    def load_token(self):
        """Loads token from token.txt in the app directory"""
        if getattr(sys, 'frozen', False):
            application_path = os.path.dirname(sys.executable)
        else:
            application_path = os.path.dirname(os.path.abspath(__file__))

        token_path = os.path.join(application_path, "token.txt")
        try:
            if os.path.exists(token_path):
                with open(token_path, "r", encoding="utf-8") as f:
                    return f.read().strip()
            return None
        except Exception as e:
            print(f"Error reading token: {e}")
            return None

    def clear_all(self):
        """Resets the application state"""
        self.text_preview.delete(1.0, END)
        self.payload = None
        self.btn_send.config(state=DISABLED)
        self.btn_save_txt.config(state=DISABLED)

    def prepare_payload(self, data):
        """Transforms input JSON into Zenodo RDM structure"""
        try:
            src_meta = data.get('metadata', {})
            
            # Metadata cleanup for RDM API
            clean_meta = {
                "title": src_meta.get("title"),
                "publication_date": src_meta.get("publication_date"),
                "resource_type": src_meta.get("resource_type"),
                "creators": src_meta.get("creators", []),
                "description": src_meta.get("description"),
                "publisher": "Zenodo",
            }
            if "funding" in src_meta: 
                clean_meta["funding"] = src_meta["funding"]

            self.payload = {
                "metadata": clean_meta,
                "access": data.get("access", {"record": "public", "files": "public"}),
                "files": {"enabled": True}
            }
            
            # Update Preview
            self.text_preview.delete(1.0, END)
            self.text_preview.insert(END, json.dumps(self.payload, indent=2, ensure_ascii=False))
            
            # Enable actions
            self.btn_send.config(state=NORMAL)
            self.btn_save_txt.config(state=NORMAL) 
            
        except Exception as e:
            messagebox.showerror("Format Error", f"Invalid JSON structure: {e}")

    def save_to_file(self):
        """Exports the prepared payload to a TXT file for inspection"""
        if not self.payload:
            return

        file_path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("JSON files", "*.json")],
            initialfile="zenodo_payload_debug.txt",
            title="Save payload for inspection"
        )
        
        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(json.dumps(self.payload, indent=4, ensure_ascii=False))
                messagebox.showinfo("Success", f"Data saved to:\n{file_path}")
            except Exception as e:
                messagebox.showerror("Save Error", f"Could not save file: {e}")

    def process_file(self):
        """Handles file selection and loading"""
        path = filedialog.askopenfilename(filetypes=[("JSON files", "*.json")])
        if path:
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    self.prepare_payload(json.load(f))
            except Exception as e:
                messagebox.showerror("File Error", f"Could not read file: {e}")

    def process_clipboard(self):
        """Handles JSON processing from clipboard"""
        try:
            raw_data = self.root.clipboard_get()
            self.prepare_payload(json.loads(raw_data))
        except Exception:
            messagebox.showerror("Clipboard Error", "Clipboard does not contain valid JSON data.")

    def create_draft(self):
        """Sends the payload to Zenodo API to create a new draft"""
        if not self.TOKEN:
            messagebox.showerror("Missing Token", "Please provide a valid API token in token.txt")
            return

        headers = {
            "Authorization": f"Bearer {self.TOKEN}", 
            "Content-Type": "application/json"
        }
        
        try:
            r = requests.post(self.API_URL, json=self.payload, headers=headers)
            if r.status_code == 201:
                response_data = r.json()
                webbrowser.open(response_data['links']['self_html'])
                messagebox.showinfo("Success", "Draft successfully created on Zenodo!")
            else:
                messagebox.showerror("API Error", f"Status: {r.status_code}\n{r.text}")
        except Exception as e:
            messagebox.showerror("Connection Error", str(e))

if __name__ == "__main__":
    # Initialize the app with a modern theme
    app_root = tb.Window(themename="litera") 
    ZenodoRDMApp(app_root)
    app_root.mainloop()
