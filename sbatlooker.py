import tkinter as tk
from tkinter import ttk, scrolledtext
from threading import Thread, Event
import time
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
import telebot
import io
from PIL import Image, ImageTk
import requests
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

class SBATExamChecker(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("SBAT Exam Availability Checker")
        self.configure(bg='#F5F5F7')
        self.geometry("600x800")

        self.setup_icon()
        self.setup_styles()
        self.create_widgets()

        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.running = False
        self.search_thread = None
        self.driver = None
        self.search_interval = 15  # Default search interval in minutes
        self.stop_event = Event()

    def setup_icon(self):
        """Set up the application icon."""
        try:
            icon_url = "https://www.sbat.be/assets/images/logo@2x.png"
            icon_data = requests.get(icon_url).content
            icon_image = Image.open(io.BytesIO(icon_data))
            icon_photo = ImageTk.PhotoImage(icon_image)
            self.iconphoto(False, icon_photo)
        except Exception as e:
            print(f"Failed to load icon: {e}")

    def setup_styles(self):
        """Configure the styling for the widgets."""
        self.style = ttk.Style(self)
        self.style.theme_use('clam')
        self.style.configure('Card.TFrame', background='#FFFFFF', relief='flat', borderwidth=0)
        self.style.configure('TLabel', background='#FFFFFF', font=('SF Pro Text', 12))
        self.style.configure('TEntry', font=('SF Pro Text', 12))
        self.style.configure('TButton', font=('SF Pro Text', 12), background='#007AFF', foreground='white')
        self.style.map('TButton', background=[('active', '#0051CB')])
        self.style.configure('TRadiobutton', background='#FFFFFF', font=('SF Pro Text', 12))

    def create_rounded_entry(self, parent, **kwargs):
        """Create a rounded entry widget."""
        entry = tk.Entry(parent, bg='#F2F2F7', relief=tk.FLAT, highlightthickness=1,
                         highlightbackground="#E5E5EA", highlightcolor="#007AFF", **kwargs)
        entry.config(font=('SF Pro Text', 12))
        return entry

    def create_widgets(self):
        """Create and layout widgets in the main window."""
        self.main_frame = ttk.Frame(self, style='Card.TFrame', padding="20")
        self.main_frame.pack(padx=20, pady=20, fill=tk.BOTH, expand=True)

        # Creating label and entry widgets
        labels = ['Email:', 'Password:', 'Search Interval (minutes):']
        entries = ['email_entry', 'password_entry', 'interval_entry']

        for i, (label, entry) in enumerate(zip(labels, entries)):
            ttk.Label(self.main_frame, text=label).grid(row=i, column=0, sticky=tk.W, padx=5, pady=10)
            setattr(self, entry, self.create_rounded_entry(self.main_frame, show='*' if 'password' in entry else ''))
            getattr(self, entry).grid(row=i, column=1, padx=5, pady=10, sticky='ew')

        # Notification type
        self.notification_type_var = tk.StringVar(value="Telegram")
        ttk.Label(self.main_frame, text="Notification Type:").grid(row=3, column=0, sticky=tk.W, padx=5, pady=10)
        notification_frame = ttk.Frame(self.main_frame, style='Card.TFrame')
        notification_frame.grid(row=3, column=1, sticky='ew', padx=5, pady=10)
        for value in ["Telegram", "Email", "Both"]:
            rb = ttk.Radiobutton(notification_frame, text=value, variable=self.notification_type_var,
                                 value=value, command=self.toggle_notification_fields)
            rb.pack(side=tk.LEFT, padx=5, pady=5)

        # Telegram configuration
        self.telegram_frame = ttk.Frame(self.main_frame, style='Card.TFrame')
        self.telegram_frame.grid(row=4, column=0, columnspan=2, sticky='ew', padx=5, pady=10)
        ttk.Label(self.telegram_frame, text="Telegram Bot Token:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.bot_token_entry = self.create_rounded_entry(self.telegram_frame)
        self.bot_token_entry.grid(row=0, column=1, padx=5, pady=5, sticky='ew')
        ttk.Label(self.telegram_frame, text="Telegram Chat ID:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.chat_id_entry = self.create_rounded_entry(self.telegram_frame)
        self.chat_id_entry.grid(row=1, column=1, padx=5, pady=5, sticky='ew')

        # Email configuration
        self.email_frame = ttk.Frame(self.main_frame, style='Card.TFrame')
        self.email_frame.grid(row=5, column=0, columnspan=2, sticky='ew', padx=5, pady=10)
        self.create_email_widgets()

        # Exam centers
        ttk.Label(self.main_frame, text="Exam Centers:").grid(row=6, column=0, sticky=tk.W, padx=5, pady=10)
        self.exam_center_var = tk.StringVar(value="Sint-Denijs-Westrem")
        self.exam_centers_list = ["Brakel", "Eeklo", "Erembodegem", "Sint-Denijs-Westrem", "Sint-Niklaas"]
        self.exam_center_menu = ttk.Combobox(self.main_frame, textvariable=self.exam_center_var, values=self.exam_centers_list)
        self.exam_center_menu.grid(row=6, column=1, padx=5, pady=10, sticky='ew')

        # Start and Stop buttons
        button_frame = ttk.Frame(self.main_frame, style='Card.TFrame')
        button_frame.grid(row=7, column=0, columnspan=2, pady=20)
        self.start_button = ttk.Button(button_frame, text="Start", command=self.start_search)
        self.start_button.pack(side=tk.LEFT, padx=5)
        self.stop_button = ttk.Button(button_frame, text="Stop", command=self.stop_search, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, padx=5)

        # Status text area
        self.status_text = scrolledtext.ScrolledText(self.main_frame, wrap=tk.WORD, height=10, state=tk.DISABLED)
        self.status_text.grid(row=8, column=0, columnspan=2, sticky='ew', padx=5, pady=10)

    def create_email_widgets(self):
        """Create and layout email-related widgets."""
        email_fields = [
            ('Sender Email:', 'sender_email_entry'),
            ('Sender Password:', 'sender_password_entry', True),
            ('Recipient Email:', 'recipient_email_entry'),
            ('SMTP Server:', 'smtp_server_entry'),
            ('SMTP Port:', 'smtp_port_entry'),
            ('Use SSL (Yes/No):', 'ssl_entry', False, ["Yes", "No"])
        ]

        for i, (label, attr, *rest) in enumerate(email_fields):
            is_password = rest[0] if rest else False
            values = rest[1] if len(rest) > 1 else None
            ttk.Label(self.email_frame, text=label).grid(row=i, column=0, sticky=tk.W, padx=5, pady=5)
            if values:
                widget = ttk.Combobox(self.email_frame, values=values, textvariable=tk.StringVar(value="Yes"))
            else:
                widget = self.create_rounded_entry(self.email_frame, show='*' if is_password else '')
            setattr(self, attr, widget)
            widget.grid(row=i, column=1, padx=5, pady=5, sticky='ew')

    def toggle_notification_fields(self):
        """Toggle visibility of notification configuration frames."""
        choice = self.notification_type_var.get()
        if choice == "Telegram":
            self.telegram_frame.grid(row=4, column=0, columnspan=2, sticky='ew', padx=5, pady=10)
            self.email_frame.grid_forget()
        elif choice == "Email":
            self.email_frame.grid(row=5, column=0, columnspan=2, sticky='ew', padx=5, pady=10)
            self.telegram_frame.grid_forget()
        else:  # Both
            self.telegram_frame.grid(row=4, column=0, columnspan=2, sticky='ew', padx=5, pady=10)
            self.email_frame.grid(row=5, column=0, columnspan=2, sticky='ew', padx=5, pady=10)

    def start_search(self):
        """Start the search thread."""
        self.stop_event.clear()
        if self.search_thread is not None and self.search_thread.is_alive():
            self.log_status("Search is already running.")
            return
        self.running = True
        self.search_thread = Thread(target=self.search_exam_availability, daemon=True)
        self.search_thread.start()
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)

    def stop_search(self):
        """Stop the search thread."""
        if not self.running:
            self.log_status("Search is not running.")
            return
        self.running = False
        self.stop_event.set()
        if self.search_thread:
            self.search_thread.join()
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)

    def search_exam_availability(self):
        """Main search function to check exam availability."""
        email = self.email_entry.get()
        password = self.password_entry.get()
        self.search_interval = int(self.interval_entry.get() or 15)

        try:
            self.setup_web_driver()
            while self.running:
                if self.stop_event.is_set():
                    break
                self.log_status("Logging in...")
                self.login(email, password)
                self.log_status("Filling exam details...")
                self.fill_exam_details()
                self.log_status(f"Checking availability at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}...")
                available_dates = self.check_available_dates()
                message = "Available dates found:\n" + "\n".join(available_dates) if available_dates else "No available dates found."
                self.log_status(message)
                self.notify_user(message)
                self.log_status("Restarting the process...")
                time.sleep(self.search_interval * 60)
        except Exception as e:
            error_message = f"An error occurred: {e}"
            self.log_status(error_message)
            self.notify_user(error_message)
        finally:
            if self.driver:
                self.driver.quit()

    def setup_web_driver(self):
        """Set up the web driver for Chrome."""
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--disable-gpu")
        self.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

    def login(self, email, password):
        """Perform login to the exam site."""
        self.driver.get('https://rijbewijs.sbat.be/praktijk/examen/login')
        WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, 'input[placeholder="E-mail"]'))).send_keys(email)
        WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, 'input[placeholder="Wachtwoord"]'))).send_keys(password)
        WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, 'button.v-btn.primary'))).click()
        WebDriverWait(self.driver, 20).until(EC.url_changes('https://rijbewijs.sbat.be/praktijk/examen/login'))
        self.log_status("Login successful")

    def fill_exam_details(self):
        """Fill in the exam details."""
        self.driver.get('https://rijbewijs.sbat.be/praktijk/examen/exam')
        time.sleep(5)
        exam_center = self.exam_center_var.get()
        self.select_dropdown_option("Examencentrum", exam_center)
        self.select_dropdown_option("Type rijbewijs", "B - Personenauto")
        self.select_dropdown_option("Voertuig", "Eigen voertuig")
        WebDriverWait(self.driver, 10).until(EC.element_to_be_clickable(
            (By.XPATH, "//button[contains(@class, 'v-btn') and contains(., 'Volgende')]"))).click()
        self.log_status(f"Exam details filled for {exam_center}")

    def select_dropdown_option(self, label, option):
        """Select an option from a dropdown menu."""
        dropdown = WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.XPATH, f"//label[contains(text(), '{label}')]/ancestor::div[contains(@class, 'v-input')]"))
        )
        dropdown.click()
        time.sleep(1)
        option_element = WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.XPATH, f"//div[@class='v-list-item__title' and contains(text(), '{option}')]"))
        )
        self.driver.execute_script("arguments[0].scrollIntoView(true);", option_element)
        option_element.click()
        time.sleep(1)
        self.log_status(f"Selected {option} for {label}")

    def check_available_dates(self, months_to_check=4):
        """Check for available dates in the calendar."""
        WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.CLASS_NAME, 'v-date-picker-table')))
        all_available_dates = []
        for _ in range(months_to_check):
            month_year = WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.CLASS_NAME, 'v-date-picker-header__value'))).text
            self.log_status(f"Checking dates for: {month_year}")
            date_buttons = self.driver.find_elements(By.CSS_SELECTOR, '.v-date-picker-table button')
            for button in date_buttons:
                if not button.get_attribute('disabled'):
                    all_available_dates.append(f"{button.text} {month_year}")
            try:
                next_month_button = self.driver.find_element(By.CSS_SELECTOR, '.v-date-picker-header button[aria-label="Next month"]')
                if next_month_button.is_enabled():
                    next_month_button.click()
                    time.sleep(2)
                else:
                    self.log_status("Next month button is disabled")
                    break
            except NoSuchElementException:
                self.log_status("Next month button not found")
                break
        return all_available_dates

    def notify_user(self, message):
        """Notify the user via the selected method(s)."""
        choice = self.notification_type_var.get()
        if choice in ["Telegram", "Both"]:
            self.send_telegram_notification(message)
        if choice in ["Email", "Both"]:
            self.send_email_notification(message)

    def send_telegram_notification(self, message):
        """Send a Telegram notification."""
        token = self.bot_token_entry.get()
        chat_id = self.chat_id_entry.get()
        bot = telebot.TeleBot(token)
        try:
            bot.send_message(chat_id, message)
            self.log_status("Telegram notification sent successfully")
        except Exception as e:
            self.log_status(f"Failed to send Telegram notification: {e}")

    def send_email_notification(self, message):
        """Send an email notification."""
        sender_email = self.sender_email_entry.get()
        sender_password = self.sender_password_entry.get()
        recipient_email = self.recipient_email_entry.get()
        smtp_server = self.smtp_server_entry.get()
        smtp_port = int(self.smtp_port_entry.get())
        use_ssl = self.ssl_entry.get() == "Yes"

        try:
            msg = MIMEMultipart()
            msg['From'] = sender_email
            msg['To'] = recipient_email
            msg['Subject'] = "Exam Availability Notification"
            msg.attach(MIMEText(message, 'plain'))

            if use_ssl:
                server = smtplib.SMTP_SSL(smtp_server, smtp_port)
            else:
                server = smtplib.SMTP(smtp_server, smtp_port)
                server.starttls()  # Use STARTTLS for encryption

            server.login(sender_email, sender_password)
            server.send_message(msg)
            server.quit()
            self.log_status("Email notification sent.")
        except Exception as e:
            self.log_status(f"Failed to send email: {e}")

    def log_status(self, message):
        """Log messages to the status text area."""
        self.status_text.config(state=tk.NORMAL)
        self.status_text.insert(tk.END, f"{datetime.now()}: {message}\n")
        self.status_text.config(state=tk.DISABLED)
        self.status_text.yview(tk.END)

    def on_closing(self):
        """Handle the window close event."""
        if self.running:
            self.stop_search()
        self.destroy()

if __name__ == "__main__":
    app = SBATExamChecker()
    app.mainloop()
