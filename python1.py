"""
============================================================
PROJECT 16: SPORTS TICKETING MANAGEMENT SYSTEM
============================================================
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
from datetime import datetime
import mysql.connector
from mysql.connector import Error
import smtplib
import ssl
import os
import uuid
import threading
import io
from email.mime.multipart import MIMEMultipart
from email.mime.text    import MIMEText
from email.mime.image   import MIMEImage
from email.mime.base    import MIMEBase
from email              import encoders

# ── Thư viện bên ngoài (cài bằng: pip install qrcode pillow) ──
try:
    import qrcode
    from PIL import Image, ImageTk
    QR_AVAILABLE = True
except ImportError:
    QR_AVAILABLE = False

# ============================================================
# CẤU HÌNH KẾT NỐI DATABASE
# ============================================================
DB_CONFIG = {
    "host":     "localhost",
    "user":     "root",
    "password": "thuanbui1",
    "database": "sports_ticketing"
}

# Bảng giá theo loại vé
DEFAULT_PRICES = {
    "VIP":      500000,
    "Standard": 200000,
    "Economy":  100000,
}

# ============================================================
# CẤU HÌNH EMAIL (Gmail) — ĐỔI THÔNG TIN CỦA BẠN TẠI ĐÂY
# ============================================================
EMAIL_CONFIG = {
    "sender_email"   : "your_email@gmail.com",   # Gmail của bạn
    "sender_password": "your_app_password",       # App Password (16 ký tự)
    "smtp_host"      : "smtp.gmail.com",
    "smtp_port"      : 465,
}

# ============================================================
# THÔNG TIN THANH TOÁN MB BANK
# ============================================================
PAYMENT_INFO = {
    "bank_name"   : "MB Bank",
    "account_no"  : "123456789",
    "account_name": "NGUYEN VAN A",              # Tên chủ tài khoản
    "branch"      : "Chi nhánh Hà Nội",
}

# Thư mục lưu ảnh minh chứng & QR
PROOF_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "payment_proofs")
QR_DIR    = os.path.join(os.path.dirname(os.path.abspath(__file__)), "qr_tickets")
os.makedirs(PROOF_DIR, exist_ok=True)
os.makedirs(QR_DIR,    exist_ok=True)

# ============================================================
# HELPER: TẠO QR CODE VÉ
# ============================================================
def generate_ticket_qr(ticket_id: int, event_name: str,
                        seat_num: str, ticket_type: str,
                        customer_name: str) -> str | None:
    """Tạo QR Code chứa thông tin vé, lưu file PNG, trả về đường dẫn."""
    if not QR_AVAILABLE:
        return None
    content = (
        f"TICKET_ID:{ticket_id}\n"
        f"EVENT:{event_name}\n"
        f"SEAT:{seat_num}\n"
        f"TYPE:{ticket_type}\n"
        f"CUSTOMER:{customer_name}\n"
        f"ISSUED:{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    qr  = qrcode.QRCode(version=2, box_size=8, border=3,
                         error_correction=qrcode.constants.ERROR_CORRECT_H)
    qr.add_data(content)
    qr.make(fit=True)
    img  = qr.make_image(fill_color="#1a3a5c", back_color="white")
    path = os.path.join(QR_DIR, f"ticket_{ticket_id}.png")
    img.save(path)
    return path


# ============================================================
# HELPER: GỬI EMAIL XÁC NHẬN
# ============================================================
def send_confirmation_email(to_email: str, ticket_id: int,
                             event_name: str, event_date,
                             seat_num: str, ticket_type: str,
                             price: float, customer_name: str,
                             qr_path: str | None,
                             proof_path: str | None) -> bool:
    """Gửi email xác nhận đặt vé qua Gmail SMTP SSL.
    Trả về True nếu gửi thành công, False nếu lỗi."""
    try:
        msg = MIMEMultipart("related")
        msg["Subject"] = f"🎟️ Xác nhận đặt vé #{ticket_id} — {event_name}"
        msg["From"]    = EMAIL_CONFIG["sender_email"]
        msg["To"]      = to_email

        # ── HTML Body ──────────────────────────────────────────────
        qr_img_tag = '<img src="cid:qrcode" width="180" style="margin:8px 0;border-radius:8px;">' \
                     if qr_path else "<p><i>(QR Code không khả dụng)</i></p>"
        html = f"""
<html><body style="font-family:Arial,sans-serif;background:#f0f4f8;padding:0;margin:0;">
<table width="100%" cellpadding="0" cellspacing="0" bgcolor="#f0f4f8">
<tr><td align="center" style="padding:32px 16px;">
<table width="580" cellpadding="0" cellspacing="0"
       style="background:#ffffff;border-radius:12px;overflow:hidden;
              box-shadow:0 4px 20px rgba(0,0,0,.12);">
  <!-- Header -->
  <tr><td bgcolor="#1a3a5c" style="padding:28px 32px;">
    <h1 style="color:#ffffff;margin:0;font-size:22px;">🎟️ Xác nhận đặt vé thành công</h1>
    <p style="color:#a0c0e0;margin:4px 0 0;">Sports Ticketing Management System</p>
  </td></tr>
  <!-- Body -->
  <tr><td style="padding:28px 32px;">
    <p style="font-size:16px;color:#333;">Xin chào <strong>{customer_name}</strong>,</p>
    <p style="color:#555;">Vé của bạn đã được đặt thành công. Chi tiết bên dưới:</p>
    <table width="100%" cellpadding="10" cellspacing="0"
           style="background:#f8fafc;border-radius:8px;border:1px solid #dce4f0;margin:16px 0;">
      <tr><td width="40%" style="color:#666;font-weight:bold;">Mã vé</td>
          <td style="color:#1a3a5c;font-size:18px;font-weight:bold;">#{ticket_id}</td></tr>
      <tr bgcolor="#eef2f7">
          <td style="color:#666;font-weight:bold;">Sự kiện</td>
          <td style="color:#333;">{event_name}</td></tr>
      <tr><td style="color:#666;font-weight:bold;">Ngày tổ chức</td>
          <td style="color:#333;">{str(event_date)[:16]}</td></tr>
      <tr bgcolor="#eef2f7">
          <td style="color:#666;font-weight:bold;">Ghế</td>
          <td style="color:#333;">{seat_num}</td></tr>
      <tr><td style="color:#666;font-weight:bold;">Loại vé</td>
          <td style="color:#333;">{ticket_type}</td></tr>
      <tr bgcolor="#eef2f7">
          <td style="color:#666;font-weight:bold;">Giá vé</td>
          <td style="color:#27ae60;font-weight:bold;font-size:15px;">{price:,.0f} VNĐ</td></tr>
    </table>
    <!-- QR Code -->
    <div style="text-align:center;margin:24px 0;">
      <p style="font-weight:bold;color:#1a3a5c;font-size:15px;">
        📱 Mã QR vào cổng sự kiện</p>
      {qr_img_tag}
      <p style="color:#888;font-size:12px;">
        Xuất trình mã QR này tại cổng để vào sự kiện</p>
    </div>
    <!-- Payment note -->
    <div style="background:#fff8e1;border-left:4px solid #f39c12;
                padding:14px 18px;border-radius:6px;margin:16px 0;">
      <p style="margin:0;color:#856404;font-weight:bold;">💳 Thông tin thanh toán đã nhận</p>
      <p style="margin:6px 0 0;color:#665200;font-size:13px;">
        Ảnh minh chứng chuyển khoản của bạn đã được ghi nhận.
        Nếu có vấn đề, vui lòng liên hệ quầy bán vé.</p>
    </div>
  </td></tr>
  <!-- Footer -->
  <tr><td bgcolor="#1a3a5c" style="padding:18px 32px;text-align:center;">
    <p style="color:#a0c0e0;font-size:12px;margin:0;">
      © Sports Ticketing Management System — DATCOM Lab NEU</p>
  </td></tr>
</table></td></tr></table>
</body></html>
"""
        alt  = MIMEMultipart("alternative")
        alt.attach(MIMEText(html, "html", "utf-8"))
        msg.attach(alt)

        # ── Đính kèm QR inline ────────────────────────────────────
        if qr_path and os.path.exists(qr_path):
            with open(qr_path, "rb") as f:
                img_part = MIMEImage(f.read(), name=os.path.basename(qr_path))
            img_part.add_header("Content-ID", "<qrcode>")
            img_part.add_header("Content-Disposition", "inline",
                                filename=os.path.basename(qr_path))
            msg.attach(img_part)

        # ── Đính kèm ảnh minh chứng ───────────────────────────────
        if proof_path and os.path.exists(proof_path):
            ext  = os.path.splitext(proof_path)[1].lower()
            mime = "jpeg" if ext in (".jpg", ".jpeg") else ext.lstrip(".")
            with open(proof_path, "rb") as f:
                att = MIMEBase("application", "octet-stream")
                att.set_payload(f.read())
            encoders.encode_base64(att)
            att.add_header("Content-Disposition", "attachment",
                           filename=f"proof_ticket_{ticket_id}{ext}")
            msg.attach(att)

        # ── Gửi qua Gmail SSL ─────────────────────────────────────
        ctx = ssl.create_default_context()
        with smtplib.SMTP_SSL(EMAIL_CONFIG["smtp_host"],
                               EMAIL_CONFIG["smtp_port"], context=ctx) as server:
            server.login(EMAIL_CONFIG["sender_email"],
                         EMAIL_CONFIG["sender_password"])
            server.sendmail(EMAIL_CONFIG["sender_email"], to_email, msg.as_string())
        return True
    except Exception as exc:
        print(f"[EMAIL ERROR] {exc}")
        return False


# ============================================================
# LỚP KẾT NỐI DATABASE
# ============================================================
class Database:
    def __init__(self):
        self.conn = None
        self.connect()

    def connect(self):
        try:
            self.conn = mysql.connector.connect(**DB_CONFIG)
            if self.conn.is_connected():
                print("✅ Kết nối database thành công!")
        except Error as e:
            messagebox.showerror("Lỗi kết nối",
                f"Không thể kết nối database:\n{e}\n\nKiểm tra lại DB_CONFIG trong code.")

    def execute(self, query, params=None, fetch=False):
        try:
            cursor = self.conn.cursor(dictionary=True)
            cursor.execute(query, params or ())
            if fetch:
                result = cursor.fetchall()
                cursor.close()
                return result
            self.conn.commit()
            last_id = cursor.lastrowid
            cursor.close()
            return last_id
        except Error as e:
            self.conn.rollback()
            raise e

    def call_proc(self, proc_name, args):
        try:
            cursor = self.conn.cursor(dictionary=True)
            cursor.callproc(proc_name, args)
            results = []
            for result in cursor.stored_results():
                results.extend(result.fetchall())
            self.conn.commit()
            cursor.close()
            return results
        except Error as e:
            self.conn.rollback()
            raise e

    def close(self):
        if self.conn and self.conn.is_connected():
            self.conn.close()


# ============================================================
# ỨNG DỤNG CHÍNH
# ============================================================
class SportTicketingApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("🎟️ Sports Ticketing Management System")
        self.geometry("1100x680")
        self.resizable(True, True)
        self.configure(bg="#1a3a5c")

        self.db = Database()
        self._setup_style()
        self._build_sidebar()
        self._build_main_area()
        self.show_frame("dashboard")
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def _setup_style(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TFrame",         background="#f0f4f8")
        style.configure("TLabel",         background="#f0f4f8", font=("Arial", 11))
        style.configure("Title.TLabel",   background="#f0f4f8", font=("Arial", 16, "bold"), foreground="#1a3a5c")
        style.configure("TButton",        font=("Arial", 10, "bold"), padding=6)
        style.configure("Primary.TButton",background="#1a3a5c", foreground="white")
        style.configure("Danger.TButton", background="#c0392b", foreground="white")
        style.configure("Treeview",       font=("Arial", 10), rowheight=26)
        style.configure("Treeview.Heading", font=("Arial", 10, "bold"),
                        background="#1a3a5c", foreground="white")
        style.configure("TEntry",   font=("Arial", 11), padding=4)
        style.configure("TCombobox",font=("Arial", 11))

    def _build_sidebar(self):
        sidebar = tk.Frame(self, bg="#1a3a5c", width=200)
        sidebar.pack(side=tk.LEFT, fill=tk.Y)
        sidebar.pack_propagate(False)

        tk.Label(sidebar, text="🎟️", font=("Arial", 32),
                 bg="#1a3a5c", fg="white").pack(pady=(24, 4))
        tk.Label(sidebar, text="Sports Ticketing",
                 font=("Arial", 12, "bold"), bg="#1a3a5c", fg="white").pack()
        tk.Label(sidebar, text="Management System",
                 font=("Arial", 9), bg="#1a3a5c", fg="#a0c0e0").pack(pady=(0, 20))
        ttk.Separator(sidebar).pack(fill=tk.X, padx=16, pady=8)

        menus = [
            ("🏠  Dashboard",   "dashboard"),
            ("📅  Sự kiện",     "events"),
            ("💺  Ghế ngồi",    "seats"),
            ("👥  Khách hàng",  "customers"),
            ("🎫  Đặt vé",      "booking"),
            ("❌  Hủy vé",      "cancel"),
            ("📊  Báo cáo",     "report"),
        ]
        self.menu_buttons = {}
        for label, key in menus:
            btn = tk.Button(
                sidebar, text=label, font=("Arial", 11), anchor="w",
                bg="#1a3a5c", fg="white", activebackground="#2a5a8c",
                activeforeground="white", relief="flat", bd=0,
                padx=20, pady=10, cursor="hand2",
                command=lambda k=key: self.show_frame(k)
            )
            btn.pack(fill=tk.X)
            self.menu_buttons[key] = btn

    def _build_main_area(self):
        self.main = tk.Frame(self, bg="#f0f4f8")
        self.main.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.frames = {}
        for F, key in [
            (DashboardFrame,  "dashboard"),
            (EventsFrame,     "events"),
            (SeatsFrame,      "seats"),
            (CustomersFrame,  "customers"),
            (BookingFrame,    "booking"),
            (CancelFrame,     "cancel"),
            (ReportFrame,     "report"),
        ]:
            frame = F(self.main, self)
            self.frames[key] = frame
            frame.place(relwidth=1, relheight=1)

    def show_frame(self, key):
        for k, btn in self.menu_buttons.items():
            btn.config(bg="#1a3a5c" if k != key else "#2a5a8c")
        frame = self.frames[key]
        frame.tkraise()
        if hasattr(frame, "refresh"):
            frame.refresh()

    def on_close(self):
        self.db.close()
        self.destroy()


# ============================================================
# BASE FRAME
# ============================================================
class BaseFrame(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.configure(style="TFrame")

    def make_title(self, text, icon=""):
        bar = ttk.Frame(self)
        bar.pack(fill=tk.X)
        tk.Frame(bar, bg="#1a3a5c", height=4).pack(fill=tk.X)
        ttk.Label(bar, text=f"{icon}  {text}", style="Title.TLabel").pack(
            anchor="w", padx=24, pady=14)

    def make_table(self, parent, columns, heights=14):
        frame = ttk.Frame(parent)
        frame.pack(fill=tk.BOTH, expand=True)
        tree = ttk.Treeview(frame, columns=columns, show="headings", height=heights)
        vsb  = ttk.Scrollbar(frame, orient="vertical",   command=tree.yview)
        hsb  = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.pack(side=tk.RIGHT,  fill=tk.Y)
        hsb.pack(side=tk.BOTTOM, fill=tk.X)
        tree.pack(fill=tk.BOTH, expand=True)
        tree.tag_configure("oddrow",  background="#ffffff")
        tree.tag_configure("evenrow", background="#eaf1fb")
        return tree

    def fill_tree(self, tree, rows):
        tree.delete(*tree.get_children())
        for i, row in enumerate(rows):
            tag = "evenrow" if i % 2 == 0 else "oddrow"
            tree.insert("", tk.END, values=list(row.values()), tags=(tag,))

    def lbl_entry(self, parent, text, row, col=0, width=24):
        ttk.Label(parent, text=text).grid(row=row, column=col,
                                          sticky="w", padx=8, pady=6)
        var = tk.StringVar()
        ttk.Entry(parent, textvariable=var, width=width).grid(
            row=row, column=col+1, sticky="ew", padx=8, pady=6)
        return var

    def lbl_combo(self, parent, text, row, values, col=0, width=22):
        ttk.Label(parent, text=text).grid(row=row, column=col,
                                          sticky="w", padx=8, pady=6)
        var = tk.StringVar()
        cb  = ttk.Combobox(parent, textvariable=var, values=values,
                           width=width, state="readonly")
        cb.grid(row=row, column=col+1, sticky="ew", padx=8, pady=6)
        return var, cb


# ============================================================
# DASHBOARD
# ============================================================
class DashboardFrame(BaseFrame):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.make_title("Dashboard", "🏠")
        self._build()

    def _build(self):
        self.cards_frame = ttk.Frame(self)
        self.cards_frame.pack(fill=tk.X, padx=24, pady=16)

        self.recent_frame = ttk.Frame(self)
        self.recent_frame.pack(fill=tk.BOTH, expand=True, padx=24, pady=8)
        ttk.Label(self.recent_frame, text="🕒  Vé đặt gần đây",
                  style="Title.TLabel").pack(anchor="w", pady=(0, 8))

        cols = ("TicketID","Khách hàng","Sự kiện","Ghế","Loại vé","Giá","Trạng thái","Ngày mua")
        self.tree = self.make_table(self.recent_frame, cols, heights=10)
        for c in cols:
            self.tree.heading(c, text=c)
            self.tree.column(c, width=120, anchor="center")

    def refresh(self):
        for w in self.cards_frame.winfo_children():
            w.destroy()

        stats = [
            ("📅 Sự kiện",    "SELECT COUNT(*) AS n FROM Events"),
            ("👥 Khách hàng", "SELECT COUNT(*) AS n FROM Customers"),
            ("🎫 Vé Active",  "SELECT COUNT(*) AS n FROM Tickets WHERE Status='Active'"),
            ("💰 Doanh thu",  "SELECT COALESCE(SUM(Price),0) AS n FROM Tickets WHERE Status='Active'"),
        ]
        colors = ["#3a7bd5","#27ae60","#e67e22","#8e44ad"]
        for i, (label, q) in enumerate(stats):
            try:
                row   = self.app.db.execute(q, fetch=True)
                value = row[0]["n"] if row else 0
                display = f"{float(value):,.0f} VNĐ" if i == 3 else str(value)
            except:
                display = "N/A"
            card = tk.Frame(self.cards_frame, bg=colors[i], padx=20, pady=16)
            card.grid(row=0, column=i, padx=10, sticky="ew")
            self.cards_frame.columnconfigure(i, weight=1)
            tk.Label(card, text=label,   font=("Arial",11,"bold"),
                     bg=colors[i], fg="white").pack(anchor="w")
            tk.Label(card, text=display, font=("Arial",20,"bold"),
                     bg=colors[i], fg="white").pack(anchor="w")

        try:
            rows = self.app.db.execute("""
                SELECT t.TicketID, c.CustomerName, e.EventName,
                       s.SeatNumber, t.TicketType, t.Price, t.Status,
                       DATE_FORMAT(t.PurchaseDate,'%d/%m/%Y %H:%i') AS PurchaseDate
                FROM Tickets t
                JOIN Customers  c ON t.CustomerID  = c.CustomerID
                JOIN Events     e ON t.EventID     = e.EventID
                JOIN Seats      s ON t.SeatID      = s.SeatID
                ORDER BY t.PurchaseDate DESC LIMIT 15
            """, fetch=True)
            self.fill_tree(self.tree, rows)
        except:
            pass


# ============================================================
# QUẢN LÝ SỰ KIỆN
# ============================================================
class EventsFrame(BaseFrame):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.make_title("Quản lý Sự kiện", "📅")
        self._build()

    def _build(self):
        top  = ttk.Frame(self)
        top.pack(fill=tk.X, padx=24, pady=8)
        form = ttk.LabelFrame(top, text="  Thêm sự kiện mới  ", padding=12)
        form.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.v_name  = self.lbl_entry(form, "Tên sự kiện:", 0, width=30)
        self.v_date  = self.lbl_entry(form, "Ngày giờ (YYYY-MM-DD HH:MM):", 1, width=20)
        self.v_venue = self.lbl_entry(form, "Địa điểm:", 2, width=30)
        self.v_sport = self.lbl_entry(form, "Môn thể thao:", 3, width=20)

        btn_f = ttk.Frame(form)
        btn_f.grid(row=4, column=0, columnspan=2, pady=8)
        ttk.Button(btn_f, text="➕  Thêm sự kiện", command=self.add_event).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_f, text="🔄  Làm mới",      command=self.refresh).pack(side=tk.LEFT, padx=4)

        cols = ("ID","Tên sự kiện","Ngày giờ","Địa điểm","Môn","Trạng thái")
        self.tree = self.make_table(self, cols)
        for c, w in zip(cols, [50,220,140,180,100,100]):
            self.tree.heading(c, text=c)
            self.tree.column(c, width=w, anchor="center")

    def add_event(self):
        name  = self.v_name.get().strip()
        date  = self.v_date.get().strip()
        venue = self.v_venue.get().strip()
        sport = self.v_sport.get().strip()
        if not all([name, date, venue, sport]):
            messagebox.showwarning("Thiếu thông tin", "Vui lòng điền đầy đủ các trường!")
            return
        try:
            self.app.db.execute(
                "INSERT INTO Events (EventName,EventDate,Venue,Sport) VALUES (%s,%s,%s,%s)",
                (name, date, venue, sport))
            messagebox.showinfo("Thành công", f"Đã thêm sự kiện: {name}")
            for v in [self.v_name, self.v_date, self.v_venue, self.v_sport]:
                v.set("")
            self.refresh()
        except Error as e:
            messagebox.showerror("Lỗi", str(e))

    def refresh(self):
        try:
            rows = self.app.db.execute(
                "SELECT EventID,EventName,EventDate,Venue,Sport,Status "
                "FROM Events ORDER BY EventDate DESC", fetch=True)
            self.fill_tree(self.tree, rows)
        except Error as e:
            messagebox.showerror("Lỗi", str(e))


# ============================================================
# QUẢN LÝ GHẾ NGỒI
# ============================================================
class SeatsFrame(BaseFrame):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.make_title("Quản lý Ghế ngồi", "💺")
        self._build()

    def _build(self):
        top  = ttk.Frame(self)
        top.pack(fill=tk.X, padx=24, pady=8)
        form = ttk.LabelFrame(top, text="  Thêm ghế cho sự kiện  ", padding=12)
        form.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.v_event_id = self.lbl_entry(form, "Event ID:", 0, width=10)
        self.v_seat_num = self.lbl_entry(form, "Số ghế (vd: A01):", 1, width=10)
        self.v_seat_type, _ = self.lbl_combo(form, "Loại ghế:", 2, ["VIP","Standard","Economy"])

        btn_f = ttk.Frame(form)
        btn_f.grid(row=3, column=0, columnspan=2, pady=8)
        ttk.Button(btn_f, text="➕  Thêm ghế", command=self.add_seat).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_f, text="🔄  Làm mới",  command=self.refresh).pack(side=tk.LEFT, padx=4)

        filter_f = ttk.Frame(self)
        filter_f.pack(fill=tk.X, padx=24, pady=4)
        ttk.Label(filter_f, text="Lọc theo Event ID:").pack(side=tk.LEFT)
        self.v_filter = tk.StringVar()
        ttk.Entry(filter_f, textvariable=self.v_filter, width=8).pack(side=tk.LEFT, padx=6)
        ttk.Button(filter_f, text="🔍 Tìm", command=self.refresh).pack(side=tk.LEFT)

        cols = ("SeatID","EventID","Số ghế","Loại ghế","Trạng thái")
        self.tree = self.make_table(self, cols)
        for c, w in zip(cols,[80,80,120,120,120]):
            self.tree.heading(c, text=c)
            self.tree.column(c, width=w, anchor="center")

    def add_seat(self):
        eid = self.v_event_id.get().strip()
        num = self.v_seat_num.get().strip()
        typ = self.v_seat_type.get()
        if not all([eid, num, typ]):
            messagebox.showwarning("Thiếu thông tin", "Vui lòng điền đầy đủ!")
            return
        try:
            self.app.db.execute(
                "INSERT INTO Seats (EventID,SeatNumber,SeatType) VALUES (%s,%s,%s)",
                (eid, num, typ))
            messagebox.showinfo("Thành công", f"Đã thêm ghế {num} cho Event {eid}")
            self.refresh()
        except Error as e:
            messagebox.showerror("Lỗi", str(e))

    def refresh(self):
        fid = self.v_filter.get().strip()
        try:
            if fid:
                rows = self.app.db.execute(
                    "SELECT SeatID,EventID,SeatNumber,SeatType,Status FROM Seats "
                    "WHERE EventID=%s ORDER BY SeatNumber", (fid,), fetch=True)
            else:
                rows = self.app.db.execute(
                    "SELECT SeatID,EventID,SeatNumber,SeatType,Status FROM Seats "
                    "ORDER BY EventID,SeatNumber", fetch=True)
            self.fill_tree(self.tree, rows)
        except Error as e:
            messagebox.showerror("Lỗi", str(e))


# ============================================================
# QUẢN LÝ KHÁCH HÀNG
# ============================================================
class CustomersFrame(BaseFrame):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.make_title("Quản lý Khách hàng", "👥")
        self._build()

    def _build(self):
        top  = ttk.Frame(self)
        top.pack(fill=tk.X, padx=24, pady=8)
        form = ttk.LabelFrame(top, text="  Thêm khách hàng mới  ", padding=12)
        form.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.v_name    = self.lbl_entry(form, "Họ tên:",        0, width=28)
        self.v_phone   = self.lbl_entry(form, "Số điện thoại:", 1, width=16)
        self.v_email   = self.lbl_entry(form, "Email:",         2, width=28)
        self.v_address = self.lbl_entry(form, "Địa chỉ:",       3, width=28)

        btn_f = ttk.Frame(form)
        btn_f.grid(row=4, column=0, columnspan=2, pady=8)
        ttk.Button(btn_f, text="➕  Thêm KH",   command=self.add_customer).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_f, text="🔍  Tìm kiếm",  command=self.search).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_f, text="🔄  Làm mới",   command=self.refresh).pack(side=tk.LEFT, padx=4)

        cols = ("ID","Họ tên","Số ĐT","Email","Địa chỉ","Ngày tạo")
        self.tree = self.make_table(self, cols)
        for c, w in zip(cols,[60,180,120,200,200,120]):
            self.tree.heading(c, text=c)
            self.tree.column(c, width=w, anchor="center")

    def add_customer(self):
        name    = self.v_name.get().strip()
        phone   = self.v_phone.get().strip()
        email   = self.v_email.get().strip()
        address = self.v_address.get().strip()
        if not all([name, phone]):
            messagebox.showwarning("Thiếu thông tin", "Họ tên và SĐT là bắt buộc!")
            return
        try:
            self.app.db.execute(
                "INSERT INTO Customers (CustomerName,PhoneNumber,Email,Address) VALUES (%s,%s,%s,%s)",
                (name, phone, email or None, address or None))
            messagebox.showinfo("Thành công", f"Đã thêm khách hàng: {name}")
            for v in [self.v_name, self.v_phone, self.v_email, self.v_address]:
                v.set("")
            self.refresh()
        except Error as e:
            messagebox.showerror("Lỗi", str(e))

    def search(self):
        kw = simpledialog.askstring("Tìm kiếm", "Nhập tên hoặc SĐT:")
        if not kw:
            return
        try:
            rows = self.app.db.execute(
                "SELECT CustomerID,CustomerName,PhoneNumber,Email,Address,CreatedAt "
                "FROM Customers WHERE CustomerName LIKE %s OR PhoneNumber LIKE %s",
                (f"%{kw}%", f"%{kw}%"), fetch=True)
            self.fill_tree(self.tree, rows)
        except Error as e:
            messagebox.showerror("Lỗi", str(e))

    def refresh(self):
        try:
            rows = self.app.db.execute(
                "SELECT CustomerID,CustomerName,PhoneNumber,Email,Address,CreatedAt "
                "FROM Customers ORDER BY CustomerID DESC", fetch=True)
            self.fill_tree(self.tree, rows)
        except Error as e:
            messagebox.showerror("Lỗi", str(e))


# ============================================================
# ĐẶT VÉ — PHIÊN BẢN CẢI TIẾN (không nhập ID thủ công)
# ============================================================
# ============================================================
# BOOKING FRAME — CÓ THANH TOÁN ONLINE + EMAIL + QR CODE
# ============================================================
class BookingFrame(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg="#f0f4f8")
        self.app = app
        self._events    = {}
        self._offices   = {}
        self._customers = {}
        self._proof_path = None   # đường dẫn ảnh minh chứng đã chọn
        self._build_ui()

    # ──────────────────────────────────────────────────────────
    # BUILD UI
    # ──────────────────────────────────────────────────────────
    def _build_ui(self):
        tk.Frame(self, bg="#1a3a5c", height=4).pack(fill=tk.X)
        tk.Label(self, text="🎫  Đặt vé", font=("Arial", 16, "bold"),
                 bg="#f0f4f8", fg="#1a3a5c").pack(anchor="w", padx=24, pady=10)

        # Wrapper cuộn nếu cửa sổ nhỏ
        wrapper = tk.Frame(self, bg="#f0f4f8")
        wrapper.pack(fill=tk.BOTH, expand=True, padx=24, pady=4)

        # ── CỘT TRÁI: Thông tin đặt vé ────────────────────────
        left = tk.LabelFrame(wrapper, text="  Thông tin đặt vé  ",
                             font=("Arial", 11, "bold"),
                             bg="#f0f4f8", fg="#1a3a5c", padx=14, pady=10)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 12))

        row = 0
        self._lbl(left, "Sự kiện:", row)
        self.cb_event = self._combo(left, row, width=34, cmd=self._on_event_change)

        row += 1
        self._lbl(left, "Loại vé:", row)
        self.cb_type = self._combo(left, row,
                                   values=["VIP", "Standard", "Economy"],
                                   cmd=self._on_type_change)
        row += 1
        self._lbl(left, "Giá vé:", row)
        self.v_price = tk.StringVar(value="—")
        tk.Label(left, textvariable=self.v_price,
                 font=("Arial", 13, "bold"), fg="#27ae60",
                 bg="#f0f4f8").grid(row=row, column=1, sticky="w", padx=8, pady=4)

        # Divider
        row += 1
        tk.Frame(left, bg="#dce4f0", height=1).grid(
            row=row, column=0, columnspan=2, sticky="ew", pady=8)

        row += 1
        self._lbl(left, "Tìm KH (tên/SĐT):", row)
        self.v_search_kh = tk.StringVar()
        kh_entry = tk.Entry(left, textvariable=self.v_search_kh,
                            font=("Arial", 11), width=24)
        kh_entry.grid(row=row, column=1, sticky="ew", padx=8, pady=4)
        kh_entry.bind("<Return>", lambda e: self._search_customer())

        row += 1
        tk.Button(left, text="🔍 Tìm khách hàng", font=("Arial", 10),
                  bg="#3a7bd5", fg="white", relief="flat",
                  command=self._search_customer, cursor="hand2"
                  ).grid(row=row, column=1, sticky="w", padx=8, pady=2)

        row += 1
        self._lbl(left, "Khách hàng:", row)
        self.cb_customer = self._combo(left, row, width=34)

        row += 1
        self._lbl(left, "Quầy bán vé:", row)
        self.cb_office = self._combo(left, row, width=34)

        # Divider
        row += 1
        tk.Frame(left, bg="#dce4f0", height=1).grid(
            row=row, column=0, columnspan=2, sticky="ew", pady=8)

        # ── THANH TOÁN ONLINE ──────────────────────────────────
        row += 1
        pay_lf = tk.LabelFrame(left, text="  💳 Thanh toán online  ",
                               font=("Arial", 10, "bold"),
                               bg="#f0f4f8", fg="#8e44ad", padx=10, pady=8)
        pay_lf.grid(row=row, column=0, columnspan=2, sticky="ew",
                    padx=0, pady=(0, 6))

        # Thông tin MB Bank
        bank_info = (
            f"🏦  {PAYMENT_INFO['bank_name']}\n"
            f"💳  STK: {PAYMENT_INFO['account_no']}\n"
            f"👤  {PAYMENT_INFO['account_name']}\n"
            f"📍  {PAYMENT_INFO['branch']}"
        )
        tk.Label(pay_lf, text=bank_info,
                 font=("Arial", 10), bg="#eef2f7",
                 fg="#2c3e50", justify="left",
                 relief="groove", padx=10, pady=8
                 ).grid(row=0, column=0, columnspan=2,
                        sticky="ew", padx=0, pady=(0, 8))

        tk.Label(pay_lf, text="Nội dung CK:", font=("Arial", 10),
                 bg="#f0f4f8").grid(row=1, column=0, sticky="w")
        self.v_transfer_note = tk.StringVar(value="Dat ve the thao")
        tk.Entry(pay_lf, textvariable=self.v_transfer_note,
                 font=("Arial", 10), width=22, state="readonly",
                 readonlybackground="#fff8e1"
                 ).grid(row=1, column=1, sticky="ew", padx=6, pady=2)

        tk.Label(pay_lf, text="Email nhận vé *:", font=("Arial", 10),
                 bg="#f0f4f8").grid(row=2, column=0, sticky="w", pady=4)
        self.v_email = tk.StringVar()
        self._email_entry = tk.Entry(pay_lf, textvariable=self.v_email,
                                     font=("Arial", 10), width=22)
        self._email_entry.grid(row=2, column=1, sticky="ew", padx=6, pady=4)

        tk.Label(pay_lf, text="Ảnh minh chứng *:", font=("Arial", 10),
                 bg="#f0f4f8").grid(row=3, column=0, sticky="w", pady=4)
        proof_row = tk.Frame(pay_lf, bg="#f0f4f8")
        proof_row.grid(row=3, column=1, sticky="ew", padx=6, pady=4)
        self.v_proof_name = tk.StringVar(value="Chưa chọn ảnh")
        tk.Label(proof_row, textvariable=self.v_proof_name,
                 font=("Arial", 9), bg="#f0f4f8", fg="#666",
                 width=16, anchor="w").pack(side=tk.LEFT)
        tk.Button(proof_row, text="📂", font=("Arial", 10),
                  bg="#8e44ad", fg="white", relief="flat",
                  cursor="hand2", command=self._pick_proof
                  ).pack(side=tk.LEFT, padx=4)

        # ── NÚT CONFIRM ───────────────────────────────────────
        row += 1
        tk.Button(left, text="✅  XÁC NHẬN ĐẶT VÉ & THANH TOÁN",
                  font=("Arial", 11, "bold"),
                  bg="#1a3a5c", fg="white", relief="flat",
                  padx=12, pady=10, cursor="hand2",
                  command=self._book_ticket
                  ).grid(row=row, column=0, columnspan=2,
                         sticky="ew", pady=4)

        row += 1
        tk.Button(left, text="➕  Thêm khách hàng mới",
                  font=("Arial", 10),
                  bg="#27ae60", fg="white", relief="flat",
                  padx=8, pady=6, cursor="hand2",
                  command=self._add_customer_popup
                  ).grid(row=row, column=0, columnspan=2,
                         sticky="ew", pady=4)

        # ── CỘT PHẢI: Bảng ghế trống ──────────────────────────
        right = tk.LabelFrame(wrapper, text="  Ghế còn trống — Click để chọn  ",
                              font=("Arial", 11, "bold"),
                              bg="#f0f4f8", fg="#1a3a5c")
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        cols = ("SeatID", "Số ghế", "Loại ghế", "Trạng thái")
        self.seat_tree = ttk.Treeview(right, columns=cols,
                                      show="headings", height=20)
        for c, w in zip(cols, [70, 100, 110, 110]):
            self.seat_tree.heading(c, text=c)
            self.seat_tree.column(c, width=w, anchor="center")

        vsb = ttk.Scrollbar(right, orient="vertical",
                            command=self.seat_tree.yview)
        self.seat_tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.seat_tree.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        self.seat_tree.bind("<<TreeviewSelect>>", self._on_seat_select)
        self.seat_tree.tag_configure("VIP",      background="#fef9e7")
        self.seat_tree.tag_configure("Standard", background="#eaf4fb")
        self.seat_tree.tag_configure("Economy",  background="#eafaf1")

    # ──────────────────────────────────────────────────────────
    # HELPERS UI
    # ──────────────────────────────────────────────────────────
    def _lbl(self, parent, text, row):
        tk.Label(parent, text=text, font=("Arial", 11),
                 bg="#f0f4f8").grid(row=row, column=0, sticky="w", padx=8, pady=4)

    def _combo(self, parent, row, values=None, width=22, cmd=None):
        var = tk.StringVar()
        cb  = ttk.Combobox(parent, textvariable=var,
                           values=values or [], width=width, state="readonly")
        cb.grid(row=row, column=1, sticky="ew", padx=8, pady=4)
        if cmd:
            cb.bind("<<ComboboxSelected>>", lambda e: cmd())
        return cb

    def _pick_proof(self):
        path = filedialog.askopenfilename(
            title="Chọn ảnh minh chứng chuyển khoản",
            filetypes=[("Ảnh", "*.png *.jpg *.jpeg *.gif *.bmp"),
                       ("Tất cả", "*.*")]
        )
        if path:
            self._proof_path = path
            self.v_proof_name.set(os.path.basename(path))

    # ──────────────────────────────────────────────────────────
    # DATA LOADERS
    # ──────────────────────────────────────────────────────────
    def refresh(self):
        self._load_events()
        self._load_offices()

    def _load_events(self):
        try:
            rows = self.app.db.execute(
                "SELECT EventID, EventName, EventDate FROM Events "
                "WHERE Status != 'Cancelled' ORDER BY EventDate DESC", fetch=True)
            self._events = {}
            names = []
            for r in rows:
                label = f"{r['EventName']}  ({str(r['EventDate'])[:10]})"
                self._events[label] = r["EventID"]
                names.append(label)
            self.cb_event["values"] = names
        except Error as e:
            messagebox.showerror("Lỗi", str(e))

    def _load_offices(self):
        try:
            rows = self.app.db.execute(
                "SELECT BoxOfficeID, OfficeName FROM BoxOffices ORDER BY OfficeName",
                fetch=True)
            self._offices = {r["OfficeName"]: r["BoxOfficeID"] for r in rows}
            self.cb_office["values"] = list(self._offices.keys())
            if self._offices:
                self.cb_office.current(0)
        except Error as e:
            messagebox.showerror("Lỗi", str(e))

    def _on_event_change(self):
        event_id = self._events.get(self.cb_event.get())
        if not event_id:
            return
        # Cập nhật nội dung chuyển khoản
        event_name = self.cb_event.get().split("  (")[0]
        self.v_transfer_note.set(f"Dat ve {event_name[:20]}")
        try:
            rows = self.app.db.execute(
                "SELECT SeatID, SeatNumber, SeatType, Status FROM Seats "
                "WHERE EventID=%s AND Status='Available' "
                "ORDER BY SeatType, SeatNumber", (event_id,), fetch=True)
            self.seat_tree.delete(*self.seat_tree.get_children())
            for r in rows:
                self.seat_tree.insert("", tk.END,
                    values=(r["SeatID"], r["SeatNumber"],
                            r["SeatType"], r["Status"]),
                    tags=(r["SeatType"],))
        except Error as e:
            messagebox.showerror("Lỗi", str(e))

    def _on_seat_select(self, event):
        selected = self.seat_tree.selection()
        if not selected:
            return
        seat_type = self.seat_tree.item(selected[0], "values")[2]
        self.cb_type.set(seat_type)
        self._on_type_change()

    def _on_type_change(self):
        price = DEFAULT_PRICES.get(self.cb_type.get(), 0)
        self.v_price.set(f"{price:,.0f} VNĐ")

    def _search_customer(self):
        kw = self.v_search_kh.get().strip()
        if not kw:
            messagebox.showwarning("Thiếu thông tin", "Nhập tên hoặc SĐT để tìm!")
            return
        try:
            rows = self.app.db.execute(
                "SELECT CustomerID, CustomerName, PhoneNumber FROM Customers "
                "WHERE CustomerName LIKE %s OR PhoneNumber LIKE %s LIMIT 20",
                (f"%{kw}%", f"%{kw}%"), fetch=True)
            if not rows:
                messagebox.showinfo("Không tìm thấy",
                    "Không có khách hàng nào khớp.\nNhấn 'Thêm khách hàng mới' để tạo.")
                return
            self._customers = {}
            labels = []
            for r in rows:
                label = f"{r['CustomerName']}  ({r['PhoneNumber']})"
                self._customers[label] = r["CustomerID"]
                labels.append(label)
            self.cb_customer["values"] = labels
            self.cb_customer.current(0)
        except Error as e:
            messagebox.showerror("Lỗi", str(e))

    def _add_customer_popup(self):
        popup = tk.Toplevel(self)
        popup.title("Thêm khách hàng mới")
        popup.geometry("380x260")
        popup.configure(bg="#f0f4f8")
        popup.grab_set()
        fields = {}
        for i, (lbl, key) in enumerate([
            ("Họ tên *",        "name"),
            ("Số điện thoại *", "phone"),
            ("Email",           "email"),
            ("Địa chỉ",         "address"),
        ]):
            tk.Label(popup, text=lbl, font=("Arial", 11),
                     bg="#f0f4f8").grid(row=i, column=0, sticky="w", padx=16, pady=6)
            var = tk.StringVar()
            tk.Entry(popup, textvariable=var, font=("Arial", 11),
                     width=24).grid(row=i, column=1, sticky="ew", padx=16, pady=6)
            fields[key] = var

        def save():
            name  = fields["name"].get().strip()
            phone = fields["phone"].get().strip()
            if not name or not phone:
                messagebox.showwarning("Thiếu thông tin",
                    "Họ tên và SĐT là bắt buộc!", parent=popup)
                return
            try:
                self.app.db.execute(
                    "INSERT INTO Customers (CustomerName,PhoneNumber,Email,Address) "
                    "VALUES (%s,%s,%s,%s)",
                    (name, phone,
                     fields["email"].get().strip() or None,
                     fields["address"].get().strip() or None))
                messagebox.showinfo("Thành công", f"Đã thêm: {name}", parent=popup)
                popup.destroy()
                self.v_search_kh.set(phone)
                self._search_customer()
                # Auto điền email nếu có
                if fields["email"].get().strip():
                    self.v_email.set(fields["email"].get().strip())
            except Error as e:
                messagebox.showerror("Lỗi", str(e), parent=popup)

        tk.Button(popup, text="💾  Lưu khách hàng",
                  font=("Arial", 11, "bold"),
                  bg="#1a3a5c", fg="white", relief="flat",
                  padx=10, pady=8, cursor="hand2",
                  command=save).grid(row=4, column=0, columnspan=2,
                                     sticky="ew", padx=16, pady=14)

    # ──────────────────────────────────────────────────────────
    # ĐẶT VÉ CHÍNH
    # ──────────────────────────────────────────────────────────
    def _book_ticket(self):
        event_label  = self.cb_event.get()
        ticket_type  = self.cb_type.get()
        cust_label   = self.cb_customer.get()
        office_label = self.cb_office.get()
        selected     = self.seat_tree.selection()
        to_email     = self.v_email.get().strip()

        # Validate
        if not event_label:
            messagebox.showwarning("Thiếu thông tin", "Vui lòng chọn sự kiện!"); return
        if not selected:
            messagebox.showwarning("Thiếu thông tin", "Vui lòng chọn ghế trong bảng!"); return
        if not ticket_type:
            messagebox.showwarning("Thiếu thông tin", "Vui lòng chọn loại vé!"); return
        if not cust_label:
            messagebox.showwarning("Thiếu thông tin", "Vui lòng tìm và chọn khách hàng!"); return
        if not office_label:
            messagebox.showwarning("Thiếu thông tin", "Vui lòng chọn quầy bán vé!"); return
        if not to_email or "@" not in to_email:
            messagebox.showwarning("Thiếu thông tin",
                "Vui lòng nhập địa chỉ email hợp lệ\nđể nhận vé xác nhận!"); return
        if not self._proof_path:
            messagebox.showwarning("Thiếu minh chứng",
                "Vui lòng đính kèm ảnh minh chứng\nchuyển khoản trước khi đặt vé!"); return

        event_id     = self._events.get(event_label)
        seat_vals    = self.seat_tree.item(selected[0], "values")
        seat_id      = seat_vals[0]
        seat_num     = seat_vals[1]
        cust_id      = self._customers.get(cust_label)
        cust_name    = cust_label.split("  (")[0]
        office_id    = self._offices.get(office_label)
        price        = DEFAULT_PRICES.get(ticket_type, 0)
        event_name   = event_label.split("  (")[0]

        # Lấy EventDate
        try:
            ev_row = self.app.db.execute(
                "SELECT EventDate FROM Events WHERE EventID=%s",
                (event_id,), fetch=True)
            event_date = ev_row[0]["EventDate"] if ev_row else ""
        except Exception:
            event_date = ""

        confirm = messagebox.askyesno(
            "Xác nhận đặt vé & thanh toán",
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"  Sự kiện : {event_name}\n"
            f"  Ghế     : {seat_num}  ({ticket_type})\n"
            f"  Khách   : {cust_name}\n"
            f"  Quầy    : {office_label}\n"
            f"  Giá     : {price:,.0f} VNĐ\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"  Email   : {to_email}\n"
            f"  TT      : {PAYMENT_INFO['bank_name']} — {PAYMENT_INFO['account_no']}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Xác nhận đặt vé?"
        )
        if not confirm:
            return

        # ── Lưu ảnh minh chứng vào thư mục ─────────────────
        import shutil
        ext       = os.path.splitext(self._proof_path)[1]
        proof_dst = os.path.join(PROOF_DIR,
                                 f"proof_{uuid.uuid4().hex[:8]}{ext}")
        shutil.copy2(self._proof_path, proof_dst)

        # ── Gọi stored procedure đặt vé ─────────────────────
        try:
            cursor = self.app.db.conn.cursor()
            cursor.callproc("sp_book_ticket",
                            [event_id, seat_id, cust_id, office_id,
                             ticket_type, price, 0, ""])
            self.app.db.conn.commit()
            cursor.execute("SELECT @_sp_book_ticket_6, @_sp_book_ticket_7")
            out = cursor.fetchone()
            cursor.close()
        except Error as e:
            messagebox.showerror("Lỗi database", str(e))
            return

        ticket_id = out[0]
        message   = out[1]

        if not (ticket_id and int(ticket_id) > 0):
            messagebox.showerror("❌ Đặt vé thất bại", message)
            return

        ticket_id = int(ticket_id)

        # ── Tạo QR Code ─────────────────────────────────────
        qr_path = generate_ticket_qr(ticket_id, event_name,
                                      seat_num, ticket_type, cust_name)

        # ── Hiển thị popup thành công + QR ──────────────────
        self._show_success_popup(ticket_id, event_name, event_date,
                                 seat_num, ticket_type, price,
                                 cust_name, to_email, qr_path)

        # ── Gửi email (background thread, không block UI) ───
        def _send():
            ok = send_confirmation_email(
                to_email, ticket_id, event_name, event_date,
                seat_num, ticket_type, price, cust_name,
                qr_path, proof_dst
            )
            # Thông báo kết quả gửi mail lên UI thread
            self.after(0, lambda: self._notify_email(ok, to_email))

        threading.Thread(target=_send, daemon=True).start()

        # Reset form
        self._proof_path = None
        self.v_proof_name.set("Chưa chọn ảnh")
        self._on_event_change()

    # ──────────────────────────────────────────────────────────
    # POPUP THÀNH CÔNG + QR CODE
    # ──────────────────────────────────────────────────────────
    def _show_success_popup(self, ticket_id, event_name, event_date,
                             seat_num, ticket_type, price,
                             cust_name, to_email, qr_path):
        popup = tk.Toplevel(self)
        popup.title("✅ Đặt vé thành công!")
        popup.geometry("480x600")
        popup.configure(bg="#f0f4f8")
        popup.grab_set()
        popup.resizable(False, False)

        # Header
        hdr = tk.Frame(popup, bg="#1a3a5c", height=60)
        hdr.pack(fill=tk.X)
        tk.Label(hdr, text="✅  ĐẶT VÉ THÀNH CÔNG",
                 font=("Arial", 15, "bold"),
                 bg="#1a3a5c", fg="white").pack(pady=14)

        body = tk.Frame(popup, bg="#f0f4f8")
        body.pack(fill=tk.BOTH, expand=True, padx=24, pady=16)

        # Thông tin vé
        info = [
            ("Mã vé",       f"#{ticket_id}"),
            ("Sự kiện",     event_name),
            ("Ngày",        str(event_date)[:16]),
            ("Ghế",         f"{seat_num}  ({ticket_type})"),
            ("Khách hàng",  cust_name),
            ("Giá vé",      f"{price:,.0f} VNĐ"),
            ("Email",       to_email),
        ]
        for lbl, val in info:
            row_f = tk.Frame(body, bg="#f0f4f8")
            row_f.pack(fill=tk.X, pady=2)
            tk.Label(row_f, text=f"{lbl}:", font=("Arial", 10, "bold"),
                     bg="#f0f4f8", fg="#555", width=14, anchor="w").pack(side=tk.LEFT)
            tk.Label(row_f, text=val, font=("Arial", 10),
                     bg="#f0f4f8", fg="#1a3a5c").pack(side=tk.LEFT)

        tk.Frame(body, bg="#dce4f0", height=1).pack(fill=tk.X, pady=10)

        # QR Code
        tk.Label(body, text="📱 Mã QR vào cổng sự kiện",
                 font=("Arial", 11, "bold"),
                 bg="#f0f4f8", fg="#1a3a5c").pack()

        if qr_path and QR_AVAILABLE and os.path.exists(qr_path):
            try:
                img     = Image.open(qr_path).resize((200, 200))
                tk_img  = ImageTk.PhotoImage(img)
                lbl_qr  = tk.Label(body, image=tk_img, bg="#f0f4f8")
                lbl_qr.image = tk_img   # giữ reference
                lbl_qr.pack(pady=6)
                tk.Label(body,
                         text=f"Lưu tại: {qr_path}",
                         font=("Arial", 8), bg="#f0f4f8", fg="#888",
                         wraplength=400).pack()
            except Exception:
                tk.Label(body, text="(Không thể hiển thị QR)",
                         bg="#f0f4f8", fg="#999").pack()
        elif not QR_AVAILABLE:
            tk.Label(body,
                     text="⚠️  Cài 'qrcode' và 'Pillow' để xem QR\n"
                          "pip install qrcode pillow",
                     font=("Arial", 9), bg="#fff3cd", fg="#856404",
                     relief="groove", padx=10, pady=8).pack(pady=6)
        else:
            tk.Label(body, text="(QR chưa sẵn sàng)",
                     bg="#f0f4f8", fg="#999").pack()

        tk.Label(body,
                 text="📧 Email xác nhận đang được gửi...",
                 font=("Arial", 9, "italic"),
                 bg="#f0f4f8", fg="#3a7bd5").pack(pady=(8, 0))

        tk.Button(popup, text="Đóng", font=("Arial", 11, "bold"),
                  bg="#1a3a5c", fg="white", relief="flat",
                  padx=20, pady=8, cursor="hand2",
                  command=popup.destroy).pack(pady=12)

    def _notify_email(self, success: bool, to_email: str):
        if success:
            messagebox.showinfo("📧 Email đã gửi",
                f"Email xác nhận đặt vé\nđã gửi thành công tới:\n{to_email}")
        else:
            messagebox.showwarning("⚠️ Gửi email thất bại",
                f"Không thể gửi email tới {to_email}.\n\n"
                "Kiểm tra lại:\n"
                "• EMAIL_CONFIG trong code\n"
                "• App Password Gmail\n"
                "• Kết nối internet\n\n"
                "Vé đã đặt thành công trong hệ thống.")


# ============================================================
# HỦY VÉ
# ============================================================
class CancelFrame(BaseFrame):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.make_title("Hủy vé", "❌")
        self._build()

    def _build(self):
        content = ttk.Frame(self)
        content.pack(fill=tk.BOTH, expand=True, padx=24, pady=12)

        search_f = ttk.LabelFrame(content, text="  Tìm vé cần hủy  ", padding=12)
        search_f.pack(fill=tk.X, pady=(0, 12))

        ttk.Label(search_f, text="Tìm theo tên KH hoặc Customer ID:").grid(
            row=0, column=0, padx=8, pady=6, sticky="w")
        self.v_search = tk.StringVar()
        ttk.Entry(search_f, textvariable=self.v_search, width=24).grid(
            row=0, column=1, padx=8, pady=6, sticky="ew")
        ttk.Button(search_f, text="🔍  Tìm vé",
                   command=self.search_tickets).grid(row=0, column=2, padx=8)
        ttk.Button(search_f, text="🔄  Tất cả vé Active",
                   command=self.refresh).grid(row=0, column=3, padx=8)

        cols = ("TicketID","Khách hàng","Sự kiện","Ghế","Loại vé","Giá","Trạng thái","Ngày mua")
        self.tree = self.make_table(content, cols, heights=14)
        for c, w in zip(cols,[80,160,180,80,90,100,90,140]):
            self.tree.heading(c, text=c)
            self.tree.column(c, width=w, anchor="center")

        btn_f = ttk.Frame(content)
        btn_f.pack(fill=tk.X, pady=8)
        ttk.Label(btn_f, text="Chọn vé trong bảng rồi nhấn:").pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_f, text="❌  Hủy vé đã chọn",
                   command=self.cancel_selected,
                   style="Danger.TButton").pack(side=tk.LEFT, padx=8)

    def search_tickets(self):
        kw = self.v_search.get().strip()
        if not kw:
            self.refresh(); return
        try:
            rows = self.app.db.execute("""
                SELECT t.TicketID, c.CustomerName, e.EventName,
                       s.SeatNumber, t.TicketType, t.Price, t.Status,
                       DATE_FORMAT(t.PurchaseDate,'%d/%m/%Y %H:%i') AS PurchaseDate
                FROM Tickets t
                JOIN Customers c ON t.CustomerID = c.CustomerID
                JOIN Events    e ON t.EventID    = e.EventID
                JOIN Seats     s ON t.SeatID     = s.SeatID
                WHERE t.Status = 'Active'
                  AND (c.CustomerName LIKE %s OR CAST(c.CustomerID AS CHAR) = %s)
                ORDER BY t.PurchaseDate DESC
            """, (f"%{kw}%", kw), fetch=True)
            self.fill_tree(self.tree, rows)
        except Error as e:
            messagebox.showerror("Lỗi", str(e))

    def cancel_selected(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Chưa chọn", "Vui lòng chọn một vé trong bảng!")
            return
        ticket_id = self.tree.item(selected[0], "values")[0]
        confirm   = messagebox.askyesno("Xác nhận hủy",
            f"Xác nhận HỦY vé #{ticket_id}?\nHành động này không thể hoàn tác!")
        if not confirm:
            return
        try:
            cursor = self.app.db.conn.cursor()
            cursor.callproc("sp_cancel_ticket", [ticket_id, ""])
            self.app.db.conn.commit()
            cursor.execute("SELECT @_sp_cancel_ticket_1")
            msg = cursor.fetchone()[0]
            cursor.close()
            messagebox.showinfo("Kết quả", msg)
            self.refresh()
        except Error as e:
            messagebox.showerror("Lỗi", str(e))

    def refresh(self):
        try:
            rows = self.app.db.execute("""
                SELECT t.TicketID, c.CustomerName, e.EventName,
                       s.SeatNumber, t.TicketType, t.Price, t.Status,
                       DATE_FORMAT(t.PurchaseDate,'%d/%m/%Y %H:%i') AS PurchaseDate
                FROM Tickets t
                JOIN Customers c ON t.CustomerID = c.CustomerID
                JOIN Events    e ON t.EventID    = e.EventID
                JOIN Seats     s ON t.SeatID     = s.SeatID
                WHERE t.Status = 'Active'
                ORDER BY t.PurchaseDate DESC
            """, fetch=True)
            self.fill_tree(self.tree, rows)
        except Error as e:
            messagebox.showerror("Lỗi", str(e))


# ============================================================
# BÁO CÁO DOANH THU
# ============================================================
class ReportFrame(BaseFrame):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.make_title("Báo cáo Doanh thu", "📊")
        self._build()

    def _build(self):
        content = ttk.Frame(self)
        content.pack(fill=tk.BOTH, expand=True, padx=24, pady=12)

        filter_f = ttk.LabelFrame(content, text="  Bộ lọc báo cáo  ", padding=12)
        filter_f.pack(fill=tk.X, pady=(0, 12))

        ttk.Label(filter_f, text="Từ ngày (YYYY-MM-DD):").grid(row=0, column=0, padx=8, pady=6, sticky="w")
        self.v_start = tk.StringVar(value="2024-01-01")
        ttk.Entry(filter_f, textvariable=self.v_start, width=14).grid(row=0, column=1, padx=8)

        ttk.Label(filter_f, text="Đến ngày:").grid(row=0, column=2, padx=8, sticky="w")
        self.v_end = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        ttk.Entry(filter_f, textvariable=self.v_end, width=14).grid(row=0, column=3, padx=8)

        ttk.Button(filter_f, text="📊  Xem báo cáo",
                   command=self.load_report,
                   style="Primary.TButton").grid(row=0, column=4, padx=12)
        ttk.Button(filter_f, text="💰  Top doanh thu",
                   command=self.load_top).grid(row=0, column=5, padx=4)
        ttk.Button(filter_f, text="🎟️  Vé theo loại",
                   command=self.load_by_type).grid(row=0, column=6, padx=4)

        self.summary_f = ttk.Frame(content)
        self.summary_f.pack(fill=tk.X, pady=(0, 10))

        cols = ("Sự kiện","Ngày tổ chức","Số vé bán","Doanh thu (VNĐ)","Giá TB (VNĐ)")
        self.tree = self.make_table(content, cols, heights=14)
        for c, w in zip(cols,[240,130,100,160,140]):
            self.tree.heading(c, text=c)
            self.tree.column(c, width=w, anchor="center")

    def load_report(self):
        try:
            rows = self.app.db.call_proc("sp_revenue_report",
                [self.v_start.get().strip(), self.v_end.get().strip()])
            self.fill_tree(self.tree, rows)
            self._update_summary(rows)
        except Error as e:
            messagebox.showerror("Lỗi", str(e))

    def load_top(self):
        try:
            rows = self.app.db.execute("""
                SELECT e.EventName, DATE_FORMAT(e.EventDate,'%d/%m/%Y') AS EventDate,
                       COUNT(t.TicketID) AS TicketsSold,
                       SUM(t.Price)      AS TotalRevenue,
                       AVG(t.Price)      AS AvgPrice
                FROM Tickets t JOIN Events e ON t.EventID = e.EventID
                WHERE t.Status = 'Active'
                GROUP BY e.EventID ORDER BY TotalRevenue DESC LIMIT 10
            """, fetch=True)
            self.fill_tree(self.tree, rows)
            self._update_summary(rows)
        except Error as e:
            messagebox.showerror("Lỗi", str(e))

    def load_by_type(self):
        try:
            rows = self.app.db.execute("""
                SELECT TicketType AS `Loại vé`,
                       COUNT(*)   AS `Số vé`,
                       SUM(Price) AS `Doanh thu`,
                       AVG(Price) AS `Giá TB`
                FROM Tickets WHERE Status='Active'
                GROUP BY TicketType ORDER BY SUM(Price) DESC
            """, fetch=True)
            if rows:
                cols = list(rows[0].keys())
                self.tree["columns"] = cols
                for c in cols:
                    self.tree.heading(c, text=c)
                    self.tree.column(c, width=160, anchor="center")
            self.fill_tree(self.tree, rows)
        except Error as e:
            messagebox.showerror("Lỗi", str(e))

    def _update_summary(self, rows):
        for w in self.summary_f.winfo_children():
            w.destroy()
        if not rows:
            return
        try:
            total_rev     = sum(float(r.get("TotalRevenue", r.get("Revenue", 0)) or 0) for r in rows)
            total_tickets = sum(int(r.get("TicketsSold", 0)) for r in rows)
        except:
            return
        for label, value, color in [
            ("Tổng doanh thu",   f"{total_rev:,.0f} VNĐ", "#27ae60"),
            ("Tổng vé bán được", str(total_tickets),        "#3a7bd5"),
            ("Số sự kiện",       str(len(rows)),             "#e67e22"),
        ]:
            card = tk.Frame(self.summary_f, bg=color, padx=16, pady=10)
            card.pack(side=tk.LEFT, padx=8, pady=4)
            tk.Label(card, text=label,  font=("Arial",10,"bold"), bg=color, fg="white").pack(anchor="w")
            tk.Label(card, text=value,  font=("Arial",16,"bold"), bg=color, fg="white").pack(anchor="w")

    def refresh(self):
        self.load_report()


# ============================================================
# ENTRY POINT
# ============================================================
if __name__ == "__main__":
    app = SportTicketingApp()
    app.mainloop()