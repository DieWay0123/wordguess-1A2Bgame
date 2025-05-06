import tkinter as tk
import socket
import threading
from datetime import datetime

class ClientGUI:
    def __init__(self, root):
        """初始化GUI與變數"""
        # socket 連線參數
        self.socket = None
        self.server_address = None
        self.client_address = ('0.0.0.0', 12345)
        self.receive_thread = None

        # 猜數字相關參數
        self.ready_to_guess = None
        self.answer_length = 0
        self.username = None
        self.guess_count = 0
        self.start_time = None
        
        # timeout計時器相關
        self.timeout_timer = None
        self.TIMEOUT_DURATION = 120  # 玩家若 120 秒內沒動作就 timeout
        self.game_running = False
        
        # Tkinter GUI 初始化
        self.root = root
        self.root.title("UDP猜字串-Client")
        self.root.minsize(900, 540)

        # === 連線資訊輸入區 ===
        self.input_entry_frame = tk.Frame(self.root)
        tk.Label(self.input_entry_frame, text="使用者名稱: ").pack()
        self.name_entry = tk.Entry(self.input_entry_frame)
        self.name_entry.pack()
        
        tk.Label(self.input_entry_frame, text="Server IP: ").pack()
        self.ip_entry = tk.Entry(self.input_entry_frame)
        self.ip_entry.pack()

        tk.Label(self.input_entry_frame, text="伺服器 Port: ").pack()
        self.port_entry = tk.Entry(self.input_entry_frame)
        self.port_entry.pack()
        
        self.start_button = tk.Button(self.input_entry_frame, text="連線並開始遊戲", command=self.start_game)
        self.start_button.pack(pady=5)
        
        # === 訊息輸出區（帶捲軸） ===
        self.text_frame = tk.Frame(self.root)
        self.text_frame.rowconfigure(0, weight=1)
        self.text_frame.columnconfigure(0, weight=1)

        self.output_text = tk.Text(self.text_frame, state="disabled")
        self.output_text.grid(row=0, column=0, sticky="nsew")
        self.output_text.tag_config("bold", font=("Helvetica", 10, "bold"))
        self.output_text.tag_config("error", foreground="red")
        self.output_text.tag_config("success", foreground="green")
        self.output_text.tag_config("info", foreground="blue", font=("Helvetica", 10, "bold"))

        scrollbar_x = tk.Scrollbar(self.text_frame, orient="horizontal", command=self.output_text.xview)
        scrollbar_y = tk.Scrollbar(self.text_frame, orient='vertical', command=self.output_text.yview)
        scrollbar_x.grid(row=1, column=0, sticky="ew")
        scrollbar_y.grid(row=0, column=1, sticky="ns")
        self.output_text.config(yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set)

        # === 猜測輸入區 ===
        self.guess_frame = tk.Frame(self.root)
        tk.Label(self.guess_frame, text="輸入猜測字串: ").pack()
        self.guess_entry = tk.Entry(self.guess_frame)
        self.guess_entry.pack()
        
        self.guess_button = tk.Button(self.guess_frame, text="送出猜測", command=self.send_guess, state='disabled')
        self.guess_button.pack(pady=5)

        self.replay_button = tk.Button(self.guess_frame, text="再玩一次", command=self.replay_game, state="disabled")
        self.replay_button.pack()

        self.quit_button = tk.Button(self.guess_frame, text="結束遊戲", command=self.quit_game, state='disabled')
        self.quit_button.pack()

        # === GUI版面配置 ===
        self.root.rowconfigure(1, weight=1)
        self.root.columnconfigure(0, weight=1)
        self.input_entry_frame.grid(row=0, column=0)
        self.text_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        self.guess_frame.grid(row=2, column=0)

    def quit_game(self):
        """結束遊戲，傳送QUIT給伺服器並關閉視窗"""
        try:
            quit_message = "QUIT"
            self.socket.sendto(quit_message.encode(), self.server_address)
        except Exception as e:
            print(f"Error sending quit message: {e}")
        finally:
            self.socket.close()
            self.root.destroy()

    def replay_game(self):
        """重新開始遊戲流程"""
        self.reset_timeout_timer()
        if self.socket:
            self.socket.sendto(f"[Replay]:{self.client_address}".encode(), self.server_address)
            self.replay_button.config(state="disabled")
            self.quit_button.config(state="disabled")
            self.guess_entry.delete(0, tk.END)
            self.modify_output_text("[Replay Requesting]已請求重新開始，請稍候Server設定新答案...\n", "info")

    def test_server_connection(self, server_address):
        """測試連線用，發出測試封包並回傳是否成功"""
        ip = server_address[0]
        port = server_address[1]
        try:
            self.modify_output_text(f"[Info]: 正在確認連線{self.client_address[0]}:{self.client_address[1]}->{ip}:{port}\n")
            self.socket.sendto(f"[Connecting]: client->{ip}:{port}".encode(), self.server_address)
            data, addr = self.socket.recvfrom(1024)
            self.modify_output_text(f"[Connection Success!]: 伺服器回應為: {data.decode()}\n", "success")
            return True
        except socket.timeout:
            return False
        except Exception as e:
            self.modify_output_text(f"[Error]: {e}\n", "error")
            return False
        finally:
            self.socket.settimeout(None)

    def start_game(self):
        """啟動遊戲流程：建立socket，發出初始訊息並啟動接收執行緒"""
        ip = self.ip_entry.get()
        port = self.port_entry.get()
        username = self.name_entry.get()
        
        if not ip or not port or not username:
            self.modify_output_text("[Error]: 請填寫完整IP、Port和username\n", "error")
            return
        
        try:
            port = int(port)
        except ValueError:
            self.modify_output_text("[Error]: 請確認填寫之port為整數數字\n", "error")
            return

        self.server_address = (ip, port)
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind(self.client_address)
        self.socket.settimeout(3)
        
        if not self.test_server_connection(self.server_address):
            self.modify_output_text("[Error]: 連線失敗，請確認伺服器是否啟動\n", "error")
            self.socket.close()
            return

        self.modify_output_text(f"[Success]: 已連線到伺服器{ip}:{port}，等待Server設定答案...\n", "success")
        self.game_running = True
        self.username = username
        self.guess_count = 0
        self.start_button.config(state="disabled")
        self.receive_thread = threading.Thread(target=self.receive_response, daemon=True)
        self.receive_thread.start()
        self.reset_timeout_timer()

    def send_guess(self):
        """送出猜測值至伺服器"""
        guess = self.guess_entry.get().strip().upper()
        self.reset_timeout_timer()

        if not self.ready_to_guess:
            self.modify_output_text("[Waiting...]: 等待Server設定答案\n")
            return
        
        if any(c not in "0123456789ABCDEF" for c in guess):
            self.modify_output_text("[Error]: 請只輸入0-9或A-F的字元\n", "error")
            return
        if len(set(guess)) != len(guess):
            self.modify_output_text("[Error]: 請確認輸入字元皆不重複\n", "error")
            return
        if len(guess) != self.answer_length:
            self.modify_output_text(f"[Error]: 請輸入{self.answer_length}個字元\n", "error")
            return

        self.guess_count += 1
        try:
            self.socket.sendto(f"[Guess]: {guess}".encode(), self.server_address)
            self.modify_output_text(f"[Info]: 已送出猜測({guess})\n", "info")
        except Exception as e:
            self.modify_output_text(f"[Error]: 傳送失敗({e})\n", "error")

    def receive_response(self):
        """接收伺服器的所有訊息並處理各種回應"""
        while self.game_running:
            try:
                data, _ = self.socket.recvfrom(1024)
                response = data.decode()
                self.reset_timeout_timer()

                if response.startswith("[Ready]:"):
                    self.ready_to_guess = True
                    self.answer_length = int(response.split(":")[1].split("，")[0])
                    self.modify_output_text(f"[Info]: Server已設定答案(長度{self.answer_length})，可開始猜測\n", "info")
                    self.guess_button.config(state='normal')
                    self.start_time = datetime.now()
                    self.guess_count = 0
                elif response.startswith("[Guess Reply]:") and "恭喜猜對" in response:
                    duration = (datetime.now() - self.start_time).total_seconds()
                    finish_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    self.modify_output_text(f"[Game Finish!]: 共猜{self.guess_count}次，用時{duration:.2f}秒\n", "bold")
                    self.modify_output_text("若要再次遊玩請點下方「再玩一次」或按「結束遊戲」離開\n", "success")
                    self.guess_button.config(state="disabled")
                    self.replay_button.config(state="normal")
                    self.quit_button.config(state="normal")
                    userinfo_msg = f"[USERINFO]->{self.username},{self.guess_count},{duration},{finish_time_str}"
                    self.socket.sendto(userinfo_msg.encode(), self.server_address)
                elif response.startswith("[Guess Reply]"):
                    self.modify_output_text(f"{response}\n", 'bold')
                elif response.startswith("[Congratulations!]:"):
                    txt = response.split(":")[1].strip()
                    self.modify_output_text(f"{txt}\n", 'bold')
                elif response.startswith("[Timeout]:"):
                    self.modify_output_text(f"{response}\n", "error")
                    self.guess_button.config(state="disabled")
                    self.replay_button.config(state="disabled")
                    self.quit_button.config(state='disabled')
                    self.game_running = False
                    self.start_button.config(state="normal")
                    self.modify_output_text("[Info]: 客戶端socket已關閉\n", "info")
                    self.socket.close()
            except OSError:
                break
            except Exception:
                continue

    def modify_output_text(self, text, tag=None):
        """更新輸出訊息框"""
        self.output_text.config(state="normal")
        if tag:
            self.output_text.insert(tk.END, text, tag)
        else:
            self.output_text.insert(tk.END, text)
        self.output_text.config(state="disabled")
        self.output_text.see(tk.END)

    def reset_timeout_timer(self):
        """重設閒置計時器（用於遊戲自動 timeout）"""
        if self.timeout_timer:
            self.timeout_timer.cancel()
        self.timeout_timer = threading.Timer(self.TIMEOUT_DURATION, self.handle_timeout)
        self.timeout_timer.start()

    def handle_timeout(self):
        """處理 timeout（玩家太久沒動作自動結束）"""
        self.modify_output_text(f"[Timeout]: {self.TIMEOUT_DURATION}秒內無操作，遊戲自動結束\n", "error")
        self.game_running = False
        try:
            self.socket.sendto("[Timeout]: Client已閒置過久，自動中止遊戲".encode(), self.server_address)
        except Exception as e:
            self.modify_output_text(f"[Error]: 傳送timeout通知失敗: {e}\n", "error")
        if self.socket:
            try:
                self.socket.close()
                self.modify_output_text("[Info]: 客戶端socket已關閉\n", "info")
            except Exception as e:
                self.modify_output_text(f"[Error]: 關閉socket時錯誤：{e}\n", "error")
            finally:
                self.socket = None

        # 重設所有狀態
        self.answer_length = 0
        self.guess_count = 0
        self.server_address = None
        self.start_button.config(state="normal")
        self.guess_button.config(state="disabled")
        self.replay_button.config(state="disabled")
        self.quit_button.config(state='disabled')

# 啟動 GUI
if __name__ == "__main__":
    root = tk.Tk()
    app = ClientGUI(root)
    root.mainloop()