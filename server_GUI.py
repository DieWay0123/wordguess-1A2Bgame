import tkinter as tk
from tkinter import messagebox
import socket
import threading
import json
import os

RANKING_FILE = "rankings.json"

class ServerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("UDP猜字串-Server")
        self.root.minsize(900, 540)

        # socket變數
        self.server_socket = None # 用於存放server socket的實體
        self.client_address =None
        self.receive_thread = None

        # answer變數
        self.answer = "" # 紀錄目前設定的答案，用於後續猜的時候比對
        self.answer_length = 0 # 紀錄目前設定的答案長度，同樣用於後續猜的時候比對
        self.game_running = False

        # timeout相關參數
        self.timeout_timer = None
        self.TIMEOUT_DURATION = 120  # 2分鐘
        self.socket_running = False

        # ranking變數紀錄排名
        self.rankings = None

        # ===== IP/Port設定區域 =====
        self.IP_frame = tk.Frame(self.root)
        # IP/Port entry
        tk.Label(self.IP_frame, text="IP Address:").pack()
        self.ip_entry = tk.Entry(self.IP_frame)
        self.ip_entry.insert(0, "127.0.0.1")
        self.ip_entry.pack()
        tk.Label(self.IP_frame, text="Port: ").pack()
        self.port_entry = tk.Entry(self.IP_frame)
        self.port_entry.insert(0, "5000")
        self.port_entry.pack()

        # 開始按鈕
        self.start_button = tk.Button(self.IP_frame, text="啟動伺服器", command=self.start_server)
        self.start_button.pack(pady=10)

        # ===== 輸出訊息區GUI =====
        self.text_frame = tk.Frame(self.root)
        self.text_frame.rowconfigure(0, weight=1)
        self.text_frame.columnconfigure(0, weight=1)
        # 用於監控的訊息輸出框
        self.output_text = tk.Text(self.text_frame, state="disabled")
        self.output_text.grid(row=0, column=0, sticky="nsew")
        self.output_text.tag_config("bold", font=("Helvetica", 10, "bold"))
        self.output_text.tag_config("error", foreground="red")
        self.output_text.tag_config("success", foreground="green")
        self.output_text.tag_config("info", foreground="blue", font=("Helvetica", 10, "bold"))
        # 加上scrollbar，可以調整訊息框閱讀範圍
        scrollbar_x = tk.Scrollbar(self.text_frame, orient="horizontal", command=self.output_text.xview)
        scrollbar_y = tk.Scrollbar(self.text_frame, orient='vertical', command=self.output_text.yview)
        scrollbar_x.grid(row=1, column=0, sticky="ew")
        scrollbar_y.grid(row=0, column=1, sticky="ns")
        self.output_text.config(yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set)

        # ===== 答案設定區域GUI =====
        self.answer_input_frame = tk.Frame()
        tk.Label(self.answer_input_frame, text="答案長度(EX: 4): ").pack()
        self.answer_len_entry = tk.Entry(self.answer_input_frame)
        self.answer_len_entry.pack()

        tk.Label(self.answer_input_frame, text="正確答案(0-9A-F，不重複):").pack()
        self.answer_entry = tk.Entry(self.answer_input_frame)
        self.answer_entry.pack()

        self.set_answer_button = tk.Button(self.answer_input_frame, text="設定答案", command=self.set_answer, state='disabled')
        self.set_answer_button.pack(pady=5)

        # GUI排版設定
        self.root.rowconfigure(2, weight=1)
        self.root.columnconfigure(0, weight=1)
        self.IP_frame.grid(column=0, row=0)
        self.answer_input_frame.grid(column=0, row=1, sticky="nsew")
        self.text_frame.grid(column=0, row=2, sticky="nsew", padx=10, pady=10)
        
        # 讀取排行榜
        self.load_rankings()

    def start_server(self):
        ip = self.ip_entry.get()
        port = self.port_entry.get()

        if not ip or not port:
            self.modify_output_text("[Error]: 輸入錯誤，請輸入IP和Port\n", "error")
            return
        
        try:
            port = int(port)
        except ValueError:
            self.modify_output_text("[Error]: 請確認Port輸入為數字\n", "error")
            return

        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) 
            self.server_socket.bind((ip, port))
        except Exception as e:
            self.modify_output_text(f"[Error]: Socket 綁定失敗：{e}\n", "error")
            return

        self.socket_running = True
        self.set_answer_button.config(state="normal")
        self.modify_output_text(f"[Info]: 伺服器已啟動，監聽 {ip}:{port}\n", "info")
        self.receive_thread = threading.Thread(target=self.receive_messages, daemon=True)
        self.receive_thread.start()
        self.reset_timeout_timer() # reset timeout 

    def check_client_guess(self, guess: str):
        # 若猜測位數不正確，則直接結束後續判斷，並回應告知client該問題
        if len(guess) != self.answer_length:
            return f"[Error]: 格式錯誤，請輸入{self.answer_length}位數字"
        # 驗整猜測有幾A幾B
        A = sum(a == b for a, b in zip(guess, self.answer))
        B = sum(min(guess.count(x), self.answer.count(x)) for x in set(guess)) - A
        if A == self.answer_length: # 猜到正確答案回傳答對的封包給client
            return f"恭喜猜對了!{A}A{B}B"
        return f"{A}A{B}B"

    def receive_messages(self):
        while self.socket_running:
            try:
                if self.server_socket:
                    data, addr = self.server_socket.recvfrom(1024)
                self.client_address = addr
                self.reset_timeout_timer()

                msg = data.decode()
                self.modify_output_text(f"[UDP]: 來自 {addr} 的訊息：{msg}\n")
                
                # 第一次client向server發送封包確認
                if msg.startswith("[Connecting]:"):
                    self.modify_output_text(f"[Success]: 收到來自{addr}的連接訊息\n", "success")
                    self.client_address = addr  # 確保儲存位址
                    self.game_running = True
                    self.set_answer_button.config(state='normal')
                    self.server_socket.sendto("[Ack]: Server已啟動".encode(), addr)       
                # 當client發送packet為guess相關時，進行答案判斷
                elif msg.startswith("[Guess]:"):
                    if not self.answer: # 防止若server還未設定好答案client就開始猜
                        server_reply = "[Error]: 伺服器尚未設定好答案"
                    else:
                        guess = msg.split(":")[1].strip()
                        server_reply = self.check_client_guess(guess) # 檢查猜測和答案，回應幾A幾B
                    
                    self.modify_output_text(f"[Info]: 來自{addr}的猜測：{guess}→{server_reply}\n", "info")
                    
                    self.server_socket.sendto(f"[Guess Reply]: {server_reply}".encode(), self.client_address)
                # 猜對後，處理client遊戲資料:
                elif msg.startswith("[USERINFO]"):
                    data = msg.split("->")[1].split(",")
                    username = data[0]
                    guess_count = int(data[1])
                    duration = float(data[2])
                    finish_time_str = data[3]
                    
                    self.add_user_rankings(username, guess_count, duration, finish_time_str)
                    rank = self.get_rank(username, duration, finish_time_str)
                    self.server_socket.sendto(f"[Congratulations!]: {username}！你是第 {rank}名!\n".encode(), self.client_address)
                    # server端show出目前ranking狀態
                    self.show_rankings(highlight_username=username, highlight_time=duration, highlight_finish=finish_time_str)
                elif msg.startswith("[Replay]:"):
                    self.modify_output_text(f"[Info]: client端要求重新開始遊戲，請再次設定答案\n", "info")
                    self.answer = ""
                    self.answer_length = 0
                    self.set_answer_button.config(state='normal')
                    self.client_address = addr
                elif msg.startswith("[Timeout]:"):
                    self.modify_output_text(f"{msg}\n", "error")
                    self.answer = ""
                    self.answer_length = 0
                    self.client_address = None
                    self.socket_running = False
                    self.game_running = False
                    self.set_answer_button.config(state="normal")
                    self.modify_output_text(f"[Info]: 伺服器socket已關閉\n", "info")
                    self.server_socket.close()
                elif msg == "QUIT":
                    self.stop_server()
            except OSError:
                break  # socket 關閉，跳出迴圈結束 thread
            except Exception as e:
                self.modify_output_text(f"[Error]: {e}", "error")
                continue
        
        if not self.socket_running:
            self.server_socket.close()
            self.server_socket = None
    
    def stop_server(self):
        self.socket_running = False
        self.game_running = False
        if self.server_socket:
            self.server_socket.close()
        self.server_socket = None

        root.destroy()
        # 開新 thread 來接收 client 訊息
        # threading.Thread(target=self.receive_messages, daemon=True).start()

    def set_answer(self):
        self.reset_timeout_timer()
        answer = self.answer_entry.get().upper()
        length = 0
        
        if not self.game_running:
            self.modify_output_text("[Info]: 目前無已連接之client，請再次確認是否已有連線\n", "info")
            self.set_answer_button.config(state="disabled")
            return
        
        try:
            length = int(self.answer_len_entry.get())
        except ValueError:
            self.modify_output_text("[Error]: 請確認答案長度為一整數\n")
            return
        
        allowed_input_char = set("0123456789ABCDEF")
        if len(answer) != length:
            self.modify_output_text(f"[Error]: 答案長度應為 {length} 位\n", "error")
            return
        if any(c not in allowed_input_char for c in answer):
            self.modify_output_text("[Error]: 請確認答案僅包含0~9或A~F\n", "error")
            return
        if len(set(answer)) != length:
            self.modify_output_text("[Error]: 答案中有重複字元)\n", "error")
            return
        
        self.answer = answer
        self.answer_length = length
        self.set_answer_button.config(state='disabled')
        self.modify_output_text(f"[Success]: ✅正確答案已設定為：{answer}\n", "success")

        # 若答案設定完成，傳送ready的UDP封包告知client可以開始進行猜字串遊戲
        if self.client_address:
            self.server_socket.sendto(f"[Ready]: {length}，開始猜數字遊戲，請輸入{length}個數字/文字".encode(), self.client_address)
            print(self.client_address)

    def modify_output_text(self, text, tag=None):
        self.output_text.config(state="normal")
        if tag:
            self.output_text.insert(tk.END, text, tag)
        else:
            self.output_text.insert(tk.END, text)
        self.output_text.config(state="disabled")
        self.output_text.see(tk.END)
        
    def load_rankings(self):
        if os.path.exists(RANKING_FILE):
            with open(RANKING_FILE, "r") as f:
                try:
                    self.rankings = json.load(f)
                except json.JSONDecodeError:
                    self.rankings = []
        else:
            self.rankings = []
        
    def save_rankings(self):
        with open(RANKING_FILE, "w") as f:
            json.dump(self.rankings, f, indent=2)
            
    def add_user_rankings(self, username, guess_count, duration, finish_time_str):
        self.rankings.append({
            "name": username,
            "guesses": guess_count,
            "time": duration,
            "finish_time": finish_time_str
        })
        self.rankings.sort(key=lambda x: x["time"])
        self.save_rankings() 

    # 用來獲取目前遊戲使用者為第幾名
    def get_rank(self, username, time_used, finish_time_str):
        for i, rec in enumerate(self.rankings):
            if rec["name"] == username and rec["time"] == time_used and rec["finish_time"] == finish_time_str:
                return i + 1
        return -1  # 找不到
    
    # 參數用以指定要粗體顯示的目前使用者!
    def show_rankings(self, highlight_username=None, highlight_time=None, highlight_finish=None):
        self.modify_output_text("[Ranking]:\n", "bold")

        for i, rec in enumerate(self.rankings, 1):
            is_highlight = (
                rec["name"] == highlight_username and
                rec["time"] == highlight_time and
                rec["finish_time"] == highlight_finish
            )
            line = f"{i}. {rec['name']} - {rec['guesses']} 次, {rec['time']} 秒, 完成時間：{rec['finish_time']}\n"
            if is_highlight:
                self.output_text.config(state="normal")
                self.modify_output_text(line, "bold")
                self.output_text.config(state="disabled")
            else:
                self.modify_output_text(line)
    
    # 當有動作時，重製timeout timer
    def reset_timeout_timer(self):
        # 由於是threading，需要先把舊的thread給取消掉再開新的timer
        print("timeout reset")
        if self.timeout_timer:
            self.timeout_timer.cancel()
        self.timeout_timer = threading.Timer(self.TIMEOUT_DURATION, self.handle_timeout)
        self.timeout_timer.start()
        
    def handle_timeout(self):
        self.modify_output_text(f"[Timeout]: {self.TIMEOUT_DURATION}秒內沒有互動，遊戲已自動結束!\n", "error")
        # 同時也中斷client端的socket監聽
        if self.client_address:
            try:
                self.server_socket.sendto(f"[Timeout]: Server已閒置過久，自動中止遊戲".encode(), self.client_address)
            except Exception as e:
                self.modify_output_text(f"[Error]: 傳送timeout通知失敗: {e}\n", "error")
            finally:
                self.client_address = None
        # 關閉socket並解除綁定
        if self.server_socket:
            try:
                self.server_socket.close()
                self.modify_output_text("[Info]: 伺服器socket已關閉\n", "info")
            except Exception as e:
                self.modify_output_text(f"[Error]: 關閉socket時發生錯誤：{e}\n", "error")
            finally:
                self.server_socket = None
        
        # 重製各個參數
        self.socket_running = False
        self.game_running = False
        self.answer = ""
        self.answer_length = 0
        
        # 將設定答案按鈕設為 disabled
        self.set_answer_button.config(state="disabled")

if __name__ == "__main__":
    root = tk.Tk()
    app = ServerGUI(root)
    root.protocol("WM_DELETE_WINDOW", app.stop_server)  # 點右上角關閉安全關閉socket
    root.mainloop()
